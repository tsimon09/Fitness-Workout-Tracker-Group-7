"""Use scripts/test.ps1: real MySQL, isolated from saved application records."""
import os
import unittest
import uuid
from decimal import Decimal
from unittest.mock import patch

import mysql.connector

from app import app
from db import execute, fetch_all, fetch_one, get_db
from scripts.init_database import main as initialize
from nutrition import FoodServiceUnavailable


class LoggingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('MYSQL_DATABASE', '').startswith('fitnut_test_'):
            raise RuntimeError('Refusing to test against an application database. Use scripts/test.ps1.')
        assert initialize() == 0
        app.config['TESTING'] = True

    def setUp(self):
        self.client = app.test_client()
        self.email = uuid.uuid4().hex + '@example.test'
        self.password = 'Demo-only-password-42'
        response = self.client.post('/register', json={'first_name': 'Test', 'last_name': 'User',
            'email': self.email, 'password': self.password, 'password_confirmation': self.password})
        self.assertEqual(response.status_code, 201, response.json)
        self.user_id = response.json['user_id']
        self.headers = self.login(self.client)

    def login(self, client):
        response = client.post('/login', json={'email': self.email, 'password': self.password})
        self.assertEqual(response.status_code, 200, response.json)
        return {'X-CSRF-Token': response.json['csrf_token']}

    def food(self, **changes):
        return {'food_name': 'Oatmeal', 'quantity': '1.25', 'quantity_unit': 'cup',
                'meal_type': 'breakfast', 'logged_at': '2026-10-20T12:00:00Z',
                'calories': '150', 'protein_g': '5', 'carbs_g': '27', 'fat_g': '3', 'fiber_g': '4',
                'meal_notes': 'Before class', **changes}

    def activity(self, **changes):
        return {'activity_name': 'Walking', 'duration_minutes': '30', 'intensity': 'moderate',
                'calorie_source': 'estimated', 'body_weight_kg': '70',
                'performed_at': '2026-10-20T13:00:00Z', 'notes': 'Campus walk', **changes}

    def post(self, path, body):
        return self.client.post(path, json=body, headers=self.headers)

    def rows(self, kind):
        response = self.client.get('/' + kind + '-logs')
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['items']

    def test_manual_food_persists_after_new_login_and_page_reload(self):
        self.assertEqual(self.post('/food-logs', self.food()).status_code, 201)
        client = app.test_client()
        self.login(client)
        self.assertEqual(client.get('/food-logs').json['items'][0]['food_name'], 'Oatmeal')
        self.assertIn(b'Oatmeal', client.get('/food').data)
        self.assertEqual(self.rows('food')[0]['quantity'], 1.25)

    def test_food_invalid_numbers_and_missing_fields(self):
        for changes in ({'quantity': '0'}, {'quantity': '-1'}, {'quantity': '0.0001'},
                        {'calories': 'NaN'}, {'protein_g': 'Infinity'}, {'fat_g': '-1'},
                        {'quantity': True}, {'calories': '1.001'}, {'quantity': '10000000'},
                        {'food_name': ' '}, {'quantity_unit': ''}, {'meal_type': 'brunch'},
                        {'logged_at': ''}, {'logged_at': '2026-10-20'}, {'logged_at': 'nonsense'}):
            with self.subTest(changes=changes):
                response = self.post('/food-logs', self.food(**changes))
                self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(self.rows('food'), [])

    def test_food_preview_does_not_create_a_meal(self):
        self.assertEqual(self.post('/food-preview', self.food()).status_code, 200)
        self.assertEqual(self.rows('food'), [])
        with app.app_context():
            self.assertEqual(fetch_one('SELECT COUNT(*) n FROM eating_events WHERE user_id=%s', (self.user_id,))['n'], 0)

    def test_meal_saves_multiple_foods_and_invalid_item_saves_nothing(self):
        body = {**self.food(), 'items': [self.food(), self.food(food_name='Apple', calories='80')]}
        bad = {**body, 'items': [self.food(), self.food(quantity=0)]}
        self.assertEqual(self.post('/meals', bad).status_code, 400)
        self.assertEqual(self.rows('food'), [])
        response = self.post('/meals', body)
        self.assertEqual(response.status_code, 201, response.json)
        rows = self.rows('food')
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row['eating_event_id'] for row in rows}), 1)

    def test_mid_meal_database_failure_rolls_back_every_food(self):
        import logs
        real_execute = logs.execute
        calls = 0
        def fail_second_food(sql, values=()):
            nonlocal calls
            if sql.startswith('INSERT INTO food_entries'):
                calls += 1
                if calls == 2:
                    raise mysql.connector.OperationalError('Simulated failure', errno=1213)
            return real_execute(sql, values)
        with patch('logs.execute', side_effect=fail_second_food):
            response = self.post('/meals', {**self.food(), 'items': [self.food(), self.food(food_name='Apple')]})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.rows('food'), [])
        with app.app_context():
            self.assertEqual(fetch_one('SELECT COUNT(*) n FROM eating_events WHERE user_id=%s', (self.user_id,))['n'], 0)

    def test_food_edit_updates_shared_meal_metadata_and_delete_cleans_empty_meal(self):
        self.post('/meals', {**self.food(), 'items': [self.food(), self.food(food_name='Apple')]})
        row = self.rows('food')[0]
        response = self.client.put('/food-logs/' + str(row['food_log_id']), headers=self.headers,
            json=self.food(eating_event_id=row['eating_event_id'], meal_type='lunch',
                           logged_at='2026-10-20T16:00:00Z', meal_notes='Changed meal'))
        self.assertEqual(response.status_code, 200, response.json)
        for item in self.rows('food'):
            self.assertEqual(item['meal_type'], 'lunch')
            self.assertEqual(item['meal_notes'], 'Changed meal')
            self.assertEqual(item['logged_at'], '2026-10-20T16:00:00Z')
            self.assertEqual(self.client.delete('/food-logs/' + str(item['food_log_id']), headers=self.headers).status_code, 200)
        with app.app_context():
            self.assertIsNone(fetch_one('SELECT eating_event_id FROM eating_events WHERE eating_event_id=%s', (row['eating_event_id'],)))

    def test_zero_and_unknown_nutrition_are_distinct(self):
        self.post('/food-logs', self.food(calories='0', protein_g=None, carbs_g='', fat_g=None, fiber_g=None))
        row = self.rows('food')[0]
        self.assertEqual(row['calories'], 0)
        self.assertIsNone(row['protein_g'])

    def seed_food(self):
        with app.app_context():
            food_id, _ = execute('''INSERT INTO food_catalog (fdc_id,food_name,calories,protein_g,carbs_g,fat_g,fiber_g)
                VALUES (%s,'Bananas, raw',89,1.09,22.84,0.33,2.6)''', (uuid.uuid4().int % 2000000000,))
            get_db().commit()
            return food_id

    def test_searched_food_scales_grams_and_servings_and_ignores_client_calories(self):
        food_id = self.seed_food()
        for quantity, unit, grams in [('150', 'g', None), ('1.5', 'serving', '100')]:
            response = self.post('/food-preview', self.food(food_id=food_id, quantity=quantity,
                quantity_unit=unit, serving_grams=grams, calories='999'))
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(response.json['item']['calories'], 133.5)
            self.assertEqual(response.json['item']['protein_g'], 1.64)
        self.assertEqual(self.post('/food-logs', self.food(food_id=food_id, quantity='150', quantity_unit='g')).status_code, 201)
        self.assertEqual(self.rows('food')[0]['calories'], 133.5)

    def test_searched_food_requires_known_id_and_mass_units(self):
        food_id = self.seed_food()
        for changes in ({'food_id': 2147483647}, {'food_id': True}, {'food_id': food_id},
                        {'food_id': food_id, 'quantity_unit': 'serving'}):
            self.assertEqual(self.post('/food-logs', self.food(**changes)).status_code, 400)

    def test_food_search_handles_results_empty_failure_and_cache(self):
        food = {'fdcId': uuid.uuid4().int % 2000000000, 'description': 'Test mango', 'foodNutrients': [
            {'nutrientId': 1008, 'unitName': 'KCAL', 'value': 60},
            {'nutrientId': 1062, 'unitName': 'KJ', 'value': 251}]}
        with patch('nutrition.usda_search', return_value=[food]):
            response = self.client.get('/food-search?q=Test+mango')
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['items'][0]['calories'], 60)
        self.assertIsNone(response.json['items'][0]['protein_g'])
        with patch('nutrition.usda_search', return_value=[]):
            self.assertEqual(self.client.get('/food-search?q=NoSuchFood').json['items'], [])
        with patch('nutrition.usda_search', side_effect=FoodServiceUnavailable):
            self.assertEqual(self.client.get('/food-search?q=Test+mango').json['source'], 'cached')
            self.assertEqual(self.client.get('/food-search?q=NoSuchFood').status_code, 503)

    def test_activity_estimate_preview_save_and_profile_reuse(self):
        response = self.post('/activity-preview', self.activity(calories_burned='9999'))
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['item']['calories_burned'], 139.65)
        self.assertEqual(self.rows('activity'), [])
        self.assertEqual(self.post('/activity-logs', self.activity()).status_code, 201)
        row = self.rows('activity')[0]
        self.assertEqual(row['calories_burned'], 139.65)
        self.assertEqual(row['calorie_source'], 'estimated')
        self.assertEqual(row['time_finished'], '2026-10-20T13:30:00Z')
        self.assertEqual(self.post('/activity-preview', self.activity(body_weight_kg=None)).json['item']['calories_burned'], 139.65)

    def test_activity_invalid_input_and_unsupported_estimate(self):
        for changes in ({'duration_minutes': 0}, {'duration_minutes': '0.001'}, {'intensity': ''},
                        {'intensity': 'extreme'}, {'body_weight_kg': 0}, {'body_weight_kg': None},
                        {'activity_name': 'Custom'}, {'performed_at': ''}, {'distance_km': -1},
                        {'set_count': '1.5'}, {'rep_count': 0}, {'calorie_source': 'made-up'},
                        {'performed_at': '9999-12-31T23:59:00', 'duration_minutes': 100}):
            with self.subTest(changes=changes):
                response = self.post('/activity-logs', self.activity(**changes))
                self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(self.rows('activity'), [])

    def test_custom_activity_manual_calories_and_optional_details_persist(self):
        data = self.activity(activity_name='Rowing club', calorie_source='manual', calories_burned='125.5',
                             distance_km='2.345', set_count='3', rep_count='8')
        response = self.post('/activity-logs', data)
        self.assertEqual(response.status_code, 201, response.json)
        row = self.rows('activity')[0]
        self.assertEqual(row['activity_name'], 'Rowing club')
        self.assertEqual(row['set_count'], 3)
        self.assertEqual(row['distance_km'], 2.345)
        self.assertEqual(row['calories_burned'], 125.5)

    def test_overlapping_activity_requires_explicit_confirmation(self):
        self.post('/activity-logs', self.activity())
        self.assertEqual(self.post('/activity-logs', self.activity()).status_code, 409)
        self.assertEqual(len(self.rows('activity')), 1)
        self.assertEqual(self.post('/activity-logs', self.activity(confirm_overlap='true')).status_code, 409)
        self.assertEqual(self.post('/activity-logs', self.activity(confirm_overlap=True)).status_code, 201)
        self.assertEqual(len(self.rows('activity')), 2)

    def test_activity_edit_delete_and_persistence_in_fresh_client(self):
        self.post('/activity-logs', self.activity())
        row = self.rows('activity')[0]
        url = '/activity-logs/' + str(row['activity_log_id'])
        response = self.client.put(url, headers=self.headers, json=self.activity(duration_minutes='45'))
        self.assertEqual(response.status_code, 200, response.json)
        client = app.test_client()
        self.login(client)
        self.assertEqual(client.get('/activity-logs').json['items'][0]['duration_minutes'], 45)
        self.assertIn(b'estimate', client.get('/activity').data)
        self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 200)
        self.assertEqual(self.rows('activity'), [])

    def test_user_ownership_and_csrf(self):
        self.post('/food-logs', self.food())
        food = self.rows('food')[0]
        self.post('/activity-logs', self.activity())
        activity = self.rows('activity')[0]
        anonymous = app.test_client()
        self.assertEqual(anonymous.get('/food-logs').status_code, 401)
        self.assertEqual(self.client.post('/food-logs', json=self.food()).status_code, 403)
        other_email = uuid.uuid4().hex + '@example.test'
        anonymous.post('/register', json={'first_name': 'Other', 'last_name': 'User', 'email': other_email,
            'password': self.password, 'password_confirmation': self.password})
        login = anonymous.post('/login', json={'email': other_email, 'password': self.password})
        headers = {'X-CSRF-Token': login.json['csrf_token']}
        self.assertEqual(anonymous.get('/food-logs').json['items'], [])
        for kind, row_id in [('food', food['food_log_id']), ('activity', activity['activity_log_id'])]:
            self.assertEqual(anonymous.delete(f'/{kind}-logs/{row_id}', headers=headers).status_code, 404)
        response = anonymous.post('/food-logs', headers=headers, json=self.food(eating_event_id=food['eating_event_id']))
        self.assertEqual(response.status_code, 400)

    def test_summary_totals_update_after_delete(self):
        self.post('/meals', {**self.food(), 'items': [self.food(), self.food(food_name='Apple', calories='80')]})
        self.post('/activity-logs', self.activity())
        query = '?start=2026-10-20T00:00:00Z&end=2026-10-21T00:00:00Z'
        totals = self.client.get('/food-logs/summary' + query).json['totals']
        self.assertEqual(totals['calories'], 230)
        self.assertEqual(totals['entries'], 2)
        self.assertEqual(self.client.get('/activity-logs/summary' + query).json['totals']['duration_minutes'], 30)
        item = self.rows('food')[0]
        self.client.delete('/food-logs/' + str(item['food_log_id']), headers=self.headers)
        self.assertEqual(self.client.get('/food-logs/summary' + query).json['totals']['entries'], 1)

    def test_summary_includes_entries_beyond_the_history_limit(self):
        response = self.post('/food-logs', self.food())
        event_id = response.json['eating_event_id']
        with app.app_context():
            unit_id = fetch_one("SELECT unit_id FROM units_of_measure WHERE unit_name='g'")['unit_id']
            for _ in range(100):
                execute('INSERT INTO food_entries (eating_event_id,unit_id,food_name,quantity,calories) VALUES (%s,%s,%s,1,1)',
                        (event_id, unit_id, 'Extra food'))
            get_db().commit()
        self.assertEqual(len(self.rows('food')), 100)
        totals = self.client.get('/food-logs/summary?start=2026-10-20T00:00:00Z&end=2026-10-21T00:00:00Z').json['totals']
        self.assertEqual(totals['entries'], 101)
        self.assertEqual(totals['calories'], 250)

    def test_goals_save_without_weight_and_show_owned_progress(self):
        self.assertEqual(self.post('/logging-goal', {'kind': 'food', 'target': '2000'}).status_code, 200)
        self.assertEqual(self.post('/logging-goal', {'kind': 'activity', 'target': '150'}).status_code, 200)
        query = '?start=2026-10-20T00:00:00Z&end=2026-10-21T00:00:00Z'
        goals = self.client.get('/food-logs/summary' + query).json['goals']
        self.assertEqual(goals, {'daily_calorie_target': 2000, 'weekly_activity_minutes': 150})
        self.assertEqual(self.post('/logging-goal', {'kind': 'food', 'target': ''}).status_code, 200)
        self.assertIsNone(self.client.get('/food-logs/summary' + query).json['goals']['daily_calorie_target'])
        self.assertEqual(self.post('/logging-goal', {'kind': 'activity', 'target': '-1'}).status_code, 400)
        self.assertEqual(self.post('/logging-goal', {'kind': ['bad'], 'target': '1'}).status_code, 400)

    def test_initializer_rerun_preserves_saved_records(self):
        self.post('/food-logs', self.food())
        before = self.rows('food')
        self.assertEqual(initialize(), 0)
        self.assertEqual(self.rows('food'), before)

    def test_existing_sleep_flow_still_works(self):
        response = self.post('/sleep-logs', {'sleep_start': '2026-10-19T22:00:00Z',
                              'sleep_end': '2026-10-20T06:00:00Z', 'sleep_quality': '4'})
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(len(self.rows('sleep')), 1)


if __name__ == '__main__':
    unittest.main()
