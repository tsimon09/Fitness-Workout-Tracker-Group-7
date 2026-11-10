"""Almond account memory and API boundaries; run with scripts/test.ps1."""
import os
import unittest
import uuid
import json
from unittest.mock import patch

from app import app
from db import execute, fetch_one, get_db
from scripts.init_database import main as initialize


class AlmondMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('MYSQL_DATABASE', '').startswith('fitnut_test_'):
            raise RuntimeError('Use scripts/test.ps1 with an isolated database.')
        assert initialize() == 0
        app.config['TESTING'] = True

    def setUp(self):
        self.password = 'Local-almond-test-42'
        self.client, self.headers, self.email = self.new_account()

    def new_account(self):
        client = app.test_client()
        email = uuid.uuid4().hex + '@example.test'
        response = client.post('/register', json={'first_name': 'Test', 'last_name': 'Almond',
            'email': email, 'password': self.password, 'password_confirmation': self.password})
        self.assertEqual(response.status_code, 201, response.json)
        login = client.post('/login', json={'email': email, 'password': self.password})
        self.assertEqual(login.status_code, 200, login.json)
        return client, {'X-CSRF-Token': login.json['csrf_token']}, email

    def profile(self, **changes):
        return self.client.post('/profile-data', json=changes, headers=self.headers)

    def test_one_hundred_custom_allergies_are_accepted_and_101_rejected(self):
        restrictions = [f'custom ingredient {index}' for index in range(100)]
        saved = self.profile(allergy_status='listed', other_allergies=restrictions)
        self.assertIn(saved.status_code, (200, 201), saved.json)
        self.assertEqual(len(self.client.get('/profile-data').json['profile']['other_allergies']), 100)

        before = self.client.get('/profile-data').json['profile']
        rejected = self.profile(other_allergies=restrictions + ['custom ingredient 100'])
        self.assertEqual(rejected.status_code, 400, rejected.json)
        self.assertEqual(self.client.get('/profile-data').json['profile'], before)

    def test_almond_state_and_conversations_require_authentication(self):
        anonymous = app.test_client()
        self.assertEqual(anonymous.get('/almond/state').status_code, 401)
        self.assertEqual(anonymous.post('/almond/conversations', json={}).status_code, 401)
        self.assertEqual(anonymous.post('/almond/memory', json={'confirmed': True}).status_code, 401)

    def test_almond_mutations_require_csrf(self):
        response = self.client.post('/almond/conversations', json={})
        self.assertEqual(response.status_code, 403, response.json)
        response = self.client.post('/almond/memory', json={
            'confirmed': True, 'cuisines': ['Thai'], 'cooking_minutes': 20, 'food_budget': 'low'})
        self.assertEqual(response.status_code, 403, response.json)

    def test_unconfirmed_optional_memory_is_rejected_and_does_not_change_state(self):
        before = self.client.get('/almond/state')
        self.assertEqual(before.status_code, 200, before.json)
        response = self.client.post('/almond/memory', headers=self.headers, json={
            'confirmed': False, 'cuisines': ['Thai'], 'cooking_minutes': 20, 'food_budget': 'low'})
        self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(self.client.get('/almond/state').json['memory'], before.json['memory'])

    def test_optional_memory_is_validated_and_saved_only_when_confirmed(self):
        valid = self.client.post('/almond/memory', headers=self.headers, json={
            'confirmed': True, 'cuisines': ['Thai', 'Japanese'],
            'cooking_minutes': 25, 'food_budget': 'low'})
        self.assertIn(valid.status_code, (200, 201), valid.json)
        memory = self.client.get('/almond/state').json['memory']
        self.assertEqual(memory['cuisines'], ['Thai', 'Japanese'])
        self.assertEqual(memory['cooking_minutes'], 25)
        self.assertEqual(memory['food_budget'], 'low')

        before = memory
        for invalid in (
            {'cuisines': 'Thai'}, {'cuisines': [True]}, {'cuisines': ['x' * 101]},
            {'cooking_minutes': True}, {'cooking_minutes': 0}, {'cooking_minutes': 1000},
            {'food_budget': 'x' * 101}, {'unrecognized': 'value'},
        ):
            with self.subTest(invalid=invalid):
                response = self.client.post('/almond/memory', headers=self.headers,
                    json={'confirmed': True, **invalid})
                self.assertEqual(response.status_code, 400, response.json)
                self.assertEqual(self.client.get('/almond/state').json['memory'], before)

    def test_conversation_reads_and_deletes_are_owner_scoped(self):
        created = self.client.post('/almond/conversations', headers=self.headers, json={})
        self.assertEqual(created.status_code, 201, created.json)
        conversation_id = created.json['conversation_id']
        self.assertEqual(self.client.get(f'/almond/conversations/{conversation_id}').status_code, 200)

        other, headers, _ = self.new_account()
        state = other.get('/almond/state').json
        self.assertNotIn(conversation_id, [item['conversation_id'] for item in state['conversations']])
        self.assertEqual(other.get(f'/almond/conversations/{conversation_id}').status_code, 404)
        self.assertEqual(other.delete(f'/almond/conversations/{conversation_id}', headers=headers).status_code, 404)
        self.assertEqual(self.client.get(f'/almond/conversations/{conversation_id}').status_code, 200)
        self.assertEqual(self.client.delete(f'/almond/conversations/{conversation_id}', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(f'/almond/conversations/{conversation_id}').status_code, 404)

    def test_optional_context_and_conversations_are_isolated_between_accounts(self):
        saved = self.client.post('/almond/memory', headers=self.headers, json={
            'confirmed': True, 'cuisines': ['PrivateCuisine'], 'cooking_minutes': 17,
            'food_budget': 'low'})
        self.assertIn(saved.status_code, (200, 201), saved.json)
        created = self.client.post('/almond/conversations', headers=self.headers, json={})
        self.assertEqual(created.status_code, 201, created.json)

        other, _, _ = self.new_account()
        other_state = other.get('/almond/state')
        self.assertEqual(other_state.status_code, 200, other_state.json)
        self.assertEqual(other_state.json['memory'], {
            'cuisines': [], 'cooking_minutes': None, 'food_budget': None})
        self.assertEqual(other_state.json['conversations'], [])
        self.assertEqual(self.client.get('/almond/state').json['memory']['cuisines'], ['PrivateCuisine'])

    def test_suggestions_have_four_slots_and_at_most_one_favorite(self):
        state = self.client.get('/almond/state')
        self.assertEqual(state.status_code, 200, state.json)
        self.assertEqual(len(state.json['suggestions']), 4)
        self.assertLessEqual(sum(item['kind'] == 'favorite' for item in state.json['suggestions']), 1)

        with app.app_context():
            user_id = fetch_one('SELECT user_id FROM users WHERE email=%s', (self.email,))['user_id']
            for title in ('Saved one', 'Saved two'):
                execute('INSERT INTO almond_favorites (user_id,recipe) VALUES (%s,%s)',
                        (user_id, '{"title":"' + title + '"}'))
            get_db().commit()

        state = self.client.get('/almond/state')
        self.assertEqual(len(state.json['favorites']), 2)
        self.assertEqual(len(state.json['suggestions']), 4)
        self.assertEqual(sum(item['kind'] == 'favorite' for item in state.json['suggestions']), 1)

    def test_favorites_are_isolated_and_delete_is_owner_scoped(self):
        with app.app_context():
            user_id = fetch_one('SELECT user_id FROM users WHERE email=%s', (self.email,))['user_id']
            favorite_id, _ = execute('INSERT INTO almond_favorites (user_id,recipe) VALUES (%s,%s)',
                                     (user_id, '{"title":"Owner favorite"}'))
            get_db().commit()
        other, headers, _ = self.new_account()
        self.assertEqual(other.get('/almond/state').json['favorites'], [])
        self.assertEqual(other.delete(f'/almond/favorites/{favorite_id}', headers=headers).status_code, 404)
        self.assertEqual(len(self.client.get('/almond/state').json['favorites']), 1)
        self.assertEqual(self.client.delete(f'/almond/favorites/{favorite_id}', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get('/almond/state').json['favorites'], [])

    def test_disabled_generation_returns_service_unavailable_without_model_call(self):
        self.assertFalse(self.client.get('/almond/state').json['enabled'])
        created = self.client.post('/almond/conversations', headers=self.headers, json={})
        self.assertEqual(created.status_code, 201, created.json)
        response = self.client.post('/almond/messages', headers=self.headers, json={
            'conversation_id': created.json['conversation_id'], 'text': 'Suggest a meal',
            'request_id': str(uuid.uuid4())})
        self.assertEqual(response.status_code, 503, response.json)

    def test_profile_change_during_generation_blocks_the_recipe_before_delivery(self):
        self.client.post('/profile-data', headers=self.headers, json={'allergy_status': 'none_reported'})
        chat = self.client.post('/almond/conversations', headers=self.headers, json={}).json['conversation_id']
        with app.app_context():
            user_id = fetch_one('SELECT user_id FROM users WHERE email=%s', (self.email,))['user_id']
            food_id, _ = execute('INSERT INTO food_catalog (fdc_id,food_name,calories) VALUES (%s,%s,%s)',
                (int(uuid.uuid4().hex[:7], 16) + 1000000000, 'Apple', 52))
            evidence = {'ingredients': ['apple'], 'allergens': [], 'dietary_tags': ['vegan'],
                'evidence_complete': True, 'evidence_id': 'test-apple-record', 'source_url': 'https://fdc.nal.usda.gov/'}
            execute('INSERT INTO almond_food_evidence (food_id,evidence) VALUES (%s,%s)', (food_id, json.dumps(evidence)))
            get_db().commit()
        def changed_profile(*args):
            execute("UPDATE user_profiles SET allergy_status='listed' WHERE user_id=%s", (user_id,))
            execute("INSERT INTO user_restrictions (user_id,kind,code,label) VALUES (%s,'allergy','custom-apple','Apple')", (user_id,))
            get_db().commit()
            return {'reply': 'Proposed meal', 'recipe': {'title': 'Apple snack', 'foods': [{'food_id': food_id, 'grams': 100}],
                'instructions': ['Slice the apple.'], 'evidence_ids': ['test-apple-record']}}
        with patch('almond.enabled', return_value=True), patch('almond.generate', side_effect=changed_profile):
            response = self.client.post('/almond/messages', headers=self.headers, json={
                'conversation_id': chat, 'text': 'Make a snack', 'request_id': str(uuid.uuid4())})
        self.assertEqual(response.status_code, 422, response.json)
        self.assertIn('conflict', response.json['error'].lower())
        self.assertEqual(self.client.get(f'/almond/conversations/{chat}').json['recipes'], [])


if __name__ == '__main__':
    unittest.main()
