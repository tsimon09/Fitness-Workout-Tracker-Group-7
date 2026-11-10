"""Integration tests for atomic Almond budget reservations; run with scripts/test.ps1."""
import os
import threading
import unittest
import uuid
from decimal import Decimal
from unittest.mock import patch

from flask import g

from app import app
from db import execute, fetch_one, get_db
from scripts.init_database import main as initialize
import almond_store
import almond


class AlmondBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('MYSQL_DATABASE', '').startswith('fitnut_test_'):
            raise RuntimeError('Use scripts/test.ps1 with an isolated database.')
        assert initialize() == 0
        app.config['TESTING'] = True

    def setUp(self):
        self.client = app.test_client()
        self.email = uuid.uuid4().hex + '@example.test'
        self.password = 'Local-almond-budget-42'
        response = self.client.post('/register', json={'first_name': 'Budget', 'last_name': 'Test',
            'email': self.email, 'password': self.password, 'password_confirmation': self.password})
        self.assertEqual(response.status_code, 201, response.json)
        login = self.client.post('/login', json={'email': self.email, 'password': self.password})
        self.assertEqual(login.status_code, 200, login.json)
        self.headers = {'X-CSRF-Token': login.json['csrf_token']}
        with app.app_context():
            self.user_id = fetch_one('SELECT user_id FROM users WHERE email=%s', (self.email,))['user_id']
            execute('DELETE FROM almond_usage')
            execute('DELETE FROM almond_budgets')
            get_db().commit()

    def reserve(self, request_id, amount, scope='evaluation'):
        with app.test_request_context('/'):
            g.user = {'user_id': self.user_id}
            # Current schema stores the optional request reference as INT.
            return almond_store.reserve(int(uuid.uuid4().hex[:7], 16), 'qwen3.7-flash', Decimal(amount), scope)

    def reconcile(self, usage_id, result, fallback_cost=None):
        with app.test_request_context('/'):
            g.user = {'user_id': self.user_id}
            return almond_store.reconcile(usage_id, result, fallback_cost)

    def usage_state(self, scope):
        with app.app_context():
            return fetch_one('SELECT * FROM almond_budgets WHERE scope=%s', (scope,))

    def test_repeated_parallel_reserve_and_reconcile_without_lock_upgrade_deadlock(self):
        errors = []
        barrier = threading.Barrier(6)

        def spend(worker):
            try:
                barrier.wait(timeout=10)
                for turn in range(10):
                    usage_id = self.reserve(f'stress-{worker}-{turn}', '0.001')
                    self.reconcile(usage_id, {'usage': {'cost': '0.0001'}})
            except Exception as error:
                errors.append(str(error))

        threads = [threading.Thread(target=spend, args=(worker,)) for worker in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        state = self.usage_state('evaluation')
        self.assertEqual(state['spent_usd'], Decimal('0.006000000'))
        self.assertEqual(state['reserved_usd'], Decimal('0'))

    def test_reservations_atomically_enforce_evaluation_and_team_caps(self):
        self.reserve('eval-a', '1.25')
        self.reserve('eval-b', '0.75')
        before = self.usage_state('evaluation')
        self.assertEqual(before['reserved_usd'], Decimal('2.000000000'))
        with self.assertRaisesRegex(ValueError, 'budget is exhausted'):
            self.reserve('eval-over', '0.01')
        self.assertEqual(self.usage_state('evaluation')['reserved_usd'], before['reserved_usd'])

        self.reserve('team-a', '2.50', 'team')
        self.assertEqual(self.usage_state('team')['reserved_usd'], Decimal('2.500000000'))
        with self.assertRaisesRegex(ValueError, 'budget is exhausted'):
            self.reserve('team-over', '0.51', 'team')

    def test_timeout_or_unknown_cost_remains_reserved_until_known(self):
        usage_id = self.reserve('unknown-cost', '0.40')
        self.reconcile(usage_id, {'usage': {}})
        state = self.usage_state('evaluation')
        self.assertEqual(state['reserved_usd'], Decimal('0.400000000'))
        self.assertEqual(state['spent_usd'], Decimal('0E-9'))
        with app.app_context():
            row = fetch_one('SELECT status,actual_usd FROM almond_usage WHERE usage_id=%s', (usage_id,))
        self.assertEqual(row['status'], 'reserved')
        self.assertIsNone(row['actual_usd'])

        self.reconcile(usage_id, {'usage': {'cost': '0.12'}, 'id': 'late-report'})
        state = self.usage_state('evaluation')
        self.assertEqual(state['reserved_usd'], Decimal('0E-9'))
        self.assertEqual(state['spent_usd'], Decimal('0.120000000'))

    def test_duplicate_reconciliation_settles_and_charges_only_once(self):
        usage_id = self.reserve('duplicate-reconcile', '0.50')
        result = {'usage': {'cost': '0.23'}, 'id': 'provider-request-1'}
        self.reconcile(usage_id, result)
        self.reconcile(usage_id, result)
        state = self.usage_state('evaluation')
        self.assertEqual(state['reserved_usd'], Decimal('0E-9'))
        self.assertEqual(state['spent_usd'], Decimal('0.230000000'))
        with app.app_context():
            row = fetch_one('SELECT status,actual_usd,upstream_id FROM almond_usage WHERE usage_id=%s', (usage_id,))
        self.assertEqual(row['status'], 'settled')
        self.assertEqual(row['actual_usd'], Decimal('0.230000000'))
        self.assertEqual(row['upstream_id'], 'provider-request-1')

    def test_concurrent_reservations_cannot_overbook_evaluation_cap(self):
        # Create the locked budget row first; the concurrent sessions contend on its FOR UPDATE lock.
        self.reserve('concurrency-seed', '0.01')
        barrier = threading.Barrier(2)
        outcomes = []

        def attempt(request_id):
            barrier.wait()
            try:
                self.reserve(request_id, '1.25')
                outcomes.append('reserved')
            except ValueError:
                outcomes.append('rejected')

        threads = [threading.Thread(target=attempt, args=(f'parallel-{i}',)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertTrue(all(not thread.is_alive() for thread in threads), 'reservation threads timed out')
        self.assertCountEqual(outcomes, ['reserved', 'rejected'])
        self.assertEqual(self.usage_state('evaluation')['reserved_usd'], Decimal('1.260000000'))

    def test_message_request_id_replays_result_and_rejects_changed_payload(self):
        conversation = self.client.post('/almond/conversations', headers=self.headers, json={})
        self.assertEqual(conversation.status_code, 201, conversation.json)
        body = {'conversation_id': conversation.json['conversation_id'],
                'request_id': 'idempotent-request-1', 'text': 'Suggest a meal'}
        mocked = {'reply': 'A test response'}
        with patch.object(almond, 'enabled', return_value=True), patch.object(almond, 'generate', return_value=mocked) as generate:
            first = self.client.post('/almond/messages', headers=self.headers, json=body)
            replay = self.client.post('/almond/messages', headers=self.headers, json=body)
            changed = self.client.post('/almond/messages', headers=self.headers,
                json={**body, 'text': 'Different text'})
        self.assertEqual(first.status_code, 200, first.json)
        self.assertEqual(replay.status_code, 200, replay.json)
        self.assertEqual(replay.json, first.json)
        self.assertEqual(changed.status_code, 409, changed.json)
        generate.assert_called_once()

    def test_second_inflight_message_for_user_is_rejected(self):
        conversation = self.client.post('/almond/conversations', headers=self.headers, json={})
        self.assertEqual(conversation.status_code, 201, conversation.json)
        body = {'conversation_id': conversation.json['conversation_id'],
                'request_id': 'concurrent-request-1', 'text': 'Suggest a meal'}
        entered_generate = threading.Event()
        release_generate = threading.Event()
        result = {}

        def slow_generate(*_args, **_kwargs):
            entered_generate.set()
            if not release_generate.wait(timeout=15):
                raise TimeoutError('mock generation was not released')
            return {'reply': 'A test response'}

        def first_request():
            client = app.test_client()
            login = client.post('/login', json={'email': self.email, 'password': self.password})
            headers = {'X-CSRF-Token': login.json['csrf_token']}
            result['first'] = client.post('/almond/messages', headers=headers, json=body)

        with patch.object(almond, 'enabled', return_value=True), patch.object(almond, 'generate', side_effect=slow_generate):
            thread = threading.Thread(target=first_request)
            thread.start()
            self.assertTrue(entered_generate.wait(timeout=10), 'first request did not enter generation')
            second = self.client.post('/almond/messages', headers=self.headers,
                json={**body, 'request_id': 'concurrent-request-2'})
            release_generate.set()
            thread.join(timeout=20)
        self.assertFalse(thread.is_alive(), 'first request did not finish')
        self.assertEqual(second.status_code, 429, second.json)
        self.assertEqual(result['first'].status_code, 200, result['first'].json)


if __name__ == '__main__':
    unittest.main()
