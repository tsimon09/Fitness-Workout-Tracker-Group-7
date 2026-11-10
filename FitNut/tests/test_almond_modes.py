"""Ask Almond's Default and Fitness modes keep separate chat histories; run with scripts/test.ps1."""
import os
import unittest
import uuid

from app import app
from scripts.init_database import main as initialize


class AlmondModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('MYSQL_DATABASE', '').startswith('fitnut_test_'):
            raise RuntimeError('Use scripts/test.ps1 with an isolated database.')
        assert initialize() == 0
        app.config['TESTING'] = True

    def new_account(self):
        client = app.test_client()
        email = uuid.uuid4().hex + '@example.test'
        password = 'Local-almond-test-42'
        client.post('/register', json={'first_name': 'Test', 'last_name': 'Modes', 'email': email,
                                       'password': password, 'password_confirmation': password})
        login = client.post('/login', json={'email': email, 'password': password})
        return client, {'X-CSRF-Token': login.json['csrf_token']}

    def test_each_mode_lists_only_its_own_conversations(self):
        client, headers = self.new_account()
        default = client.post('/almond/conversations', headers=headers, json={}).json['conversation_id']
        named = client.post('/almond/conversations', headers=headers, json={'mode': 'default'}).json['conversation_id']
        fitness = client.post('/almond/conversations', headers=headers, json={'mode': 'fitness'}).json['conversation_id']
        modes = {row['conversation_id']: row['mode'] for row in client.get('/almond/state').json['conversations']}
        self.assertEqual(modes, {default: 'default', named: 'default', fitness: 'fitness'})

    def test_unknown_mode_is_rejected(self):
        client, headers = self.new_account()
        response = client.post('/almond/conversations', headers=headers, json={'mode': 'other'})
        self.assertEqual(response.status_code, 400, response.json)
        self.assertEqual(client.get('/almond/state').json['conversations'], [])

    def test_mode_does_not_expose_another_account(self):
        client, headers = self.new_account()
        other, _ = self.new_account()
        fitness = client.post('/almond/conversations', headers=headers, json={'mode': 'fitness'}).json['conversation_id']
        self.assertEqual(other.get(f'/almond/conversations/{fitness}').status_code, 404)
        self.assertEqual(other.get('/almond/state').json['conversations'], [])

    def test_allergy_answer_merges_without_changing_measurements(self):
        client, headers = self.new_account()
        client.post('/profile-data', headers=headers, json={'height_cm': 175.25, 'weight_kg': 70.13, 'fitness_goal': 'gain_weight', 'daily_calorie_target': 2200})
        self.assertFalse(client.get('/almond/state').json['dietary_confirmed'])
        saved = client.post('/profile-data', headers=headers, json={'allergy_status': 'none_reported'})
        self.assertEqual(saved.status_code, 200, saved.json)
        profile = client.get('/profile-data').json['profile']
        self.assertEqual((float(profile['height_cm']), float(profile['weight_kg'])), (175.25, 70.13))
        self.assertEqual(profile['fitness_goal'], 'gain_weight')
        self.assertEqual(float(profile['daily_calorie_target']), 2200)
        self.assertTrue(client.get('/almond/state').json['dietary_confirmed'])


if __name__ == '__main__':
    unittest.main()
