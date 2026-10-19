"""Run through scripts/test.ps1 against its temporary MySQL database."""
import os
import unittest
import uuid
from unittest.mock import patch

import mysql.connector

from app import app
from db import execute, fetch_all
from scripts.init_database import main as initialize


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('MYSQL_DATABASE', '').startswith('fitnut_test_'):
            raise RuntimeError('Use scripts/test.ps1 with an isolated database.')
        assert initialize() == 0
        app.config['TESTING'] = True

    def setUp(self):
        self.password = 'Local-profile-test-42'
        self.client, self.headers, self.email = self.new_account()

    def new_account(self):
        client = app.test_client()
        email = uuid.uuid4().hex + '@example.test'
        response = client.post('/register', json={'first_name': 'Test', 'last_name': 'User',
            'email': email, 'password': self.password, 'password_confirmation': self.password})
        self.assertEqual(response.status_code, 201, response.json)
        login = client.post('/login', json={'email': email, 'password': self.password})
        self.assertEqual(login.status_code, 200, login.json)
        return client, {'X-CSRF-Token': login.json['csrf_token']}, email

    def save(self, **changes):
        return self.client.post('/profile-data', json=changes, headers=self.headers)

    def current(self):
        response = self.client.get('/profile-data')
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['profile']

    def test_new_profile_has_unknown_allergies_and_requires_login(self):
        result = self.client.get('/profile-data').json
        self.assertFalse(result['exists'])
        self.assertEqual(result['profile']['allergy_status'], 'not_provided')
        self.assertEqual(result['profile']['allergens'], [])
        self.assertIsNone(result['profile']['weight_kg'])
        anonymous = app.test_client()
        self.assertEqual(anonymous.get('/profile').status_code, 302)
        self.assertEqual(anonymous.get('/profile-data').status_code, 401)
        self.assertEqual(anonymous.post('/profile-data', json={}).status_code, 401)

    def test_full_profile_persists_after_new_login(self):
        response = self.save(age='25', height_cm='175.25', weight_kg='70', fitness_goal='improve_fitness',
            fitness_level='beginner', dietary_pattern='vegetarian', daily_calorie_target='2000',
            weekly_activity_minutes='150', allergy_status='listed', allergens=['milk', 'peanut'],
            other_allergies=['Kiwi'], intolerances=['Lactose'], preferences=['No spicy food'])
        self.assertEqual(response.status_code, 201, response.json)
        client = app.test_client()
        client.post('/login', json={'email': self.email, 'password': self.password})
        saved = client.get('/profile-data').json['profile']
        self.assertEqual(saved['age'], 25)
        self.assertEqual(saved['height_cm'], 175.25)
        self.assertEqual(saved['weight_kg'], 70)
        self.assertEqual(saved['daily_calorie_target'], 2000)
        self.assertEqual(saved['allergens'], ['milk', 'peanut'])
        self.assertEqual(saved['other_allergies'], ['Kiwi'])
        self.assertEqual(saved['intolerances'], ['Lactose'])
        self.assertEqual(saved['preferences'], ['No spicy food'])
        self.assertEqual(saved['dietary_pattern'], 'vegetarian')
        page = client.get('/profile')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Kiwi', page.data)
        self.assertIn(b'value="milk" checked', page.data)

    def test_partial_update_preserves_existing_fields_and_can_remove_items(self):
        self.save(weight_kg='70', daily_calorie_target='2000', allergy_status='listed',
                  allergens=['milk', 'peanut'], preferences=['No spicy food'])
        response = self.save(allergens=['peanut'], preferences=[])
        self.assertEqual(response.status_code, 200, response.json)
        profile = self.current()
        self.assertEqual(profile['weight_kg'], 70)
        self.assertEqual(profile['daily_calorie_target'], 2000)
        self.assertEqual(profile['allergens'], ['peanut'])
        self.assertEqual(profile['preferences'], [])
        self.assertEqual(self.save(weight_kg='', fitness_goal='').status_code, 200)
        self.assertIsNone(self.current()['weight_kg'])

    def test_allergy_states_are_distinct_and_conflicting_values_are_rejected(self):
        self.assertEqual(self.save(allergy_status='none_reported').status_code, 201)
        self.assertEqual(self.current()['allergy_status'], 'none_reported')
        self.assertEqual(self.save(allergy_status='listed').status_code, 400)
        self.assertEqual(self.save(allergy_status='not_provided', allergens=['peanut']).status_code, 400)
        self.assertEqual(self.save(allergy_status='listed', allergens=['peanut']).status_code, 200)
        self.assertEqual(self.save(allergy_status='none_reported').status_code, 400)
        self.assertEqual(self.save(allergy_status='none_reported', allergens=[], other_allergies=[]).status_code, 200)
        self.assertEqual(self.current()['allergens'], [])
        self.assertEqual(self.save(allergy_status='not_provided').status_code, 200)
        self.assertEqual(self.current()['allergy_status'], 'not_provided')

    def test_invalid_fields_leave_saved_profile_unchanged(self):
        self.save(weight_kg='70', allergy_status='listed', allergens=['sesame'])
        before = self.current()
        for changes in ({'age': '1.5'}, {'age': 0}, {'age': 121}, {'age': True},
                        {'height_cm': '-1'}, {'height_cm': 301}, {'height_cm': '1.001'},
                        {'weight_kg': 'NaN'}, {'weight_kg': '1000'}, {'daily_calorie_target': 0},
                        {'weekly_activity_minutes': -1}, {'fitness_goal': 'unknown'},
                        {'fitness_level': []}, {'dietary_pattern': 'random'},
                        {'allergy_status': 'unknown'}, {'allergens': 'milk'}, {'allergens': [True]},
                        {'allergens': ['unknown']}, {'preferences': ['']}, {'intolerances': None},
                        {'preferences': ['x' * 101]}, {'other_allergies': ['x'] * 21}):
            with self.subTest(changes=changes):
                response = self.save(**changes)
                self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(self.current(), before)

    def test_restrictions_are_normalized_without_mixing_categories(self):
        response = self.save(allergy_status='listed', allergens=['milk', 'milk'],
            other_allergies=['Milk', ' Kiwi ', 'kiwi'], intolerances=['Lactose', 'lactose'],
            preferences=['Less salt', 'Less   salt'])
        self.assertEqual(response.status_code, 201, response.json)
        profile = self.current()
        self.assertEqual(profile['allergens'], ['milk'])
        self.assertEqual(profile['other_allergies'], ['Kiwi'])
        self.assertEqual(profile['intolerances'], ['Lactose'])
        self.assertEqual(profile['preferences'], ['Less salt'])
        with app.app_context():
            rows = fetch_all('SELECT kind,code FROM user_restrictions WHERE user_id=%s',
                             (profile['user_id'],))
            self.assertEqual(len(rows), 4)
            self.assertTrue(any(row['kind'] == 'allergy' and row['code'] == 'milk' for row in rows))

    def test_profile_ownership_and_csrf(self):
        self.save(allergy_status='listed', allergens=['peanut'], weight_kg=70)
        owner = self.current()['user_id']
        other, headers, _ = self.new_account()
        self.assertEqual(other.get('/profile-data').json['profile']['allergens'], [])
        self.assertNotIn(b'value="peanut" checked', other.get('/profile').data)
        response = other.post('/profile-data', headers=headers, json={'user_id': owner, 'weight_kg': 80})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.current()['weight_kg'], 70)
        response = self.client.post('/profile-data', json={'weight_kg': 80})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.current()['weight_kg'], 70)
        self.assertEqual(other.get('/profile-data?user_id=' + str(owner)).json['profile']['allergens'], [])

    def test_failed_restriction_save_rolls_back_profile_and_restrictions(self):
        self.save(weight_kg=70, allergy_status='listed', allergens=['milk'], preferences=['Less salt'])
        before = self.current()
        real_execute = execute
        def fail_insert(sql, values=()):
            if sql.startswith('INSERT INTO user_restrictions'):
                raise mysql.connector.OperationalError('Simulated profile failure', errno=1213)
            return real_execute(sql, values)
        with patch('profiles.execute', side_effect=fail_insert):
            response = self.save(weight_kg=80, allergens=['peanut'])
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.current(), before)

    def test_logging_goals_and_activity_weight_preserve_restrictions(self):
        self.client.post('/logging-goal', headers=self.headers, json={'kind': 'food', 'target': 2000})
        response = self.save(age=25, allergy_status='listed', allergens=['wheat'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.current()['daily_calorie_target'], 2000)
        self.client.post('/logging-goal', headers=self.headers, json={'kind': 'food', 'target': 2100})
        response = self.client.post('/activity-logs', headers=self.headers, json={
            'activity_name': 'Walking', 'duration_minutes': 30, 'intensity': 'moderate',
            'calorie_source': 'estimated', 'body_weight_kg': 72, 'performed_at': '2026-10-20T12:00:00Z'})
        self.assertEqual(response.status_code, 201, response.json)
        profile = self.current()
        self.assertEqual(profile['weight_kg'], 72)
        self.assertEqual(profile['daily_calorie_target'], 2100)
        self.assertEqual(profile['age'], 25)
        self.assertEqual(profile['allergens'], ['wheat'])

    def test_html_in_custom_entries_is_escaped(self):
        self.save(allergy_status='listed', other_allergies=['<script>alert(1)</script>'])
        page = self.client.get('/profile')
        self.assertIn(b'&lt;script&gt;', page.data)
        self.assertNotIn(b'<script>alert(1)</script>', page.data)

    def test_reinitializing_preserves_profile_and_restrictions(self):
        self.save(weight_kg=70, allergy_status='listed', allergens=['fish'], preferences=['Less salt'])
        before = self.current()
        self.assertEqual(initialize(), 0)
        self.assertEqual(self.current(), before)
