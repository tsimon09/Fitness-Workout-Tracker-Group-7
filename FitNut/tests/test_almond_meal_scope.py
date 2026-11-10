"""Integration coverage for Almond's conversation-scoped meal restrictions."""
import json
import os
import unittest
import uuid
from unittest.mock import patch

from app import app
from db import execute, fetch_one, get_db
from scripts.init_database import main as initialize


class ScriptedGateway:
    """Deterministic local model double; callbacks still pass through paid_call."""
    def __init__(self, intents, food_id, evidence_id):
        self.intents = iter(intents)
        self.food_id = food_id
        self.evidence_id = evidence_id
        self.contexts = []
        self.decisions = []

    def decide(self, state, questions):
        self.decisions.append((state, questions))
        if 'intent' in questions:
            return {'answers': {'intent': {'choice': next(self.intents)}}}
        return {'answers': {'supported': {'noul': 1.0}, 'coherent': {'noul': 1.0}}}

    def chat(self, model, messages, max_tokens=1500):
        context = json.loads(messages[1]['content'])
        self.contexts.append(context)
        recipe = {
            'title': 'Simple apple snack',
            'foods': [{'food_id': self.food_id, 'grams': 100}],
            'instructions': ['Wash and slice the apple.'],
            'substitutions': [],
            'evidence_ids': [self.evidence_id],
        }
        return {'choices': [{'message': {'content': json.dumps(recipe)}}], 'usage': {}}


class AlmondMealScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('MYSQL_DATABASE', '').startswith('fitnut_test_'):
            raise RuntimeError('Use scripts/test.ps1 with an isolated database.')
        assert initialize() == 0
        app.config['TESTING'] = True

    def setUp(self):
        self.password = 'Local-almond-test-42'
        self.client = app.test_client()
        self.email = uuid.uuid4().hex + '@example.test'
        response = self.client.post('/register', json={
            'first_name': 'Test', 'last_name': 'MealScope', 'email': self.email,
            'password': self.password, 'password_confirmation': self.password,
        })
        self.assertEqual(response.status_code, 201, response.json)
        login = self.client.post('/login', json={'email': self.email, 'password': self.password})
        self.assertEqual(login.status_code, 200, login.json)
        self.headers = {'X-CSRF-Token': login.json['csrf_token']}
        profile = self.client.post('/profile-data', headers=self.headers, json={
            'allergy_status': 'none_reported', 'intolerances': [],
        })
        self.assertIn(profile.status_code, (200, 201), profile.json)

        self.evidence_id = 'test-apple-scope-' + uuid.uuid4().hex
        with app.app_context():
            self.user_id = fetch_one('SELECT user_id FROM users WHERE email=%s', (self.email,))['user_id']
            self.food_id, _ = execute(
                'INSERT INTO food_catalog (fdc_id,food_name,calories) VALUES (%s,%s,%s)',
                (int(uuid.uuid4().hex[:7], 16) + 1000000000, 'Apple', 52),
            )
            evidence = {
                'ingredients': ['apple'], 'allergens': [], 'dietary_tags': ['vegan'],
                'evidence_complete': True, 'evidence_id': self.evidence_id,
                'source_url': 'https://fdc.nal.usda.gov/',
            }
            execute('INSERT INTO almond_food_evidence (food_id,evidence) VALUES (%s,%s)',
                    (self.food_id, json.dumps(evidence)))
            get_db().commit()

    def current_profile(self):
        response = self.client.get('/profile-data')
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['profile']

    def send(self, conversation_id, request):
        return self.client.post('/almond/messages', headers=self.headers, json={
            'conversation_id': conversation_id, 'text': request,
            'request_id': uuid.uuid4().hex,
        })

    def test_greeting_bypasses_gateway_and_goal_requires_confirmation(self):
        conversation_id = self.client.post('/almond/conversations', headers=self.headers, json={}).json['conversation_id']
        fake = ScriptedGateway(['goal', 'goal'], self.food_id, self.evidence_id)

        def local_call(client, request_id, model, callback, writer=False):
            return callback()

        def propose(text):
            key = uuid.uuid4().hex
            result = self.client.post('/almond/messages', headers=self.headers, json={
                'conversation_id': conversation_id, 'request_id': key, 'text': text,
            })
            self.assertEqual(result.status_code, 200, result.json)
            return key, result.json['goal_proposal']

        def confirm(key):
            return self.client.post('/almond/goals/confirm', headers=self.headers, json={
                'request_id': key, 'confirmed': True,
            })

        with patch('almond.enabled', return_value=True), patch('almond.GatewayClient', return_value=fake) as gateway, \
                patch('almond.paid_call', side_effect=local_call), patch.dict(os.environ, {'ALMOND_WRITER_MODEL': 'qwen3.8-flash'}):
            greeting = self.send(conversation_id, 'Hello!')
            self.assertEqual(greeting.status_code, 200, greeting.json)
            self.assertIn('Almond here', greeting.json['reply'])
            gateway.assert_not_called()

            old, _ = propose('I want to build muscle.')
            key, goal = propose("I'm trying to gain some pounds so I can look good in this dress.")
            self.assertEqual(goal['proposed'], 'gain_weight')
            self.assertIsNone(self.current_profile()['fitness_goal'])
            self.assertEqual(confirm(old).status_code, 409)
            for _ in range(2):
                saved = confirm(key)
                self.assertEqual(saved.status_code, 200, saved.json)
                self.assertTrue(saved.json['saved'])
            self.assertEqual(self.current_profile()['fitness_goal'], 'gain_weight')
            history = self.client.get(f'/almond/conversations/{conversation_id}')
            self.assertEqual(history.json['goal_actions'][0]['request_id'], key)
            self.assertTrue(history.json['goal_actions'][0]['saved'])

    def test_temporary_restriction_scopes_to_current_meal_and_confirmed_profile_persists(self):
        created = self.client.post('/almond/conversations', headers=self.headers, json={})
        self.assertEqual(created.status_code, 201, created.json)
        conversation_id = created.json['conversation_id']
        fake = ScriptedGateway(['new_meal', 'modify', 'new_meal', 'new_meal'],
                               self.food_id, self.evidence_id)

        def local_paid_call(client, request_id, model, callback, writer=False):
            # Preserve the real production callback boundary while avoiding reservations/network calls.
            return callback()

        with patch.dict(os.environ, {'ALMOND_WRITER_MODEL': 'qwen3.8-flash'}), \
             patch('almond.enabled', return_value=True), \
             patch('almond.GatewayClient', return_value=fake), \
             patch('almond.paid_call', side_effect=local_paid_call):
            first = self.send(conversation_id, 'Make an apple snack without oats for this meal.')
            self.assertEqual(first.status_code, 200, first.json)
            second = self.send(conversation_id, 'Modify this meal to make the apple easier to pack.')
            self.assertEqual(second.status_code, 200, second.json)
            third = self.send(conversation_id, 'New meal: make a simple apple snack for later.')
            self.assertEqual(third.status_code, 200, third.json)

            # A durable restriction is saved explicitly in Profile; it is independent of chat scope.
            saved = self.client.post('/profile-data', headers=self.headers,
                                     json={'intolerances': ['oats']})
            self.assertEqual(saved.status_code, 200, saved.json)
            fourth = self.send(conversation_id, 'New meal: suggest a quick apple snack.')
            self.assertEqual(fourth.status_code, 200, fourth.json)

        self.assertEqual(len(fake.contexts), 4)
        profile1 = fake.contexts[0]['profile']
        profile2 = fake.contexts[1]['profile']
        profile3 = fake.contexts[2]['profile']
        profile4 = fake.contexts[3]['profile']
        self.assertEqual(profile1['temporary_restrictions'], ['oats'])
        self.assertEqual(profile2['temporary_restrictions'], ['oats'])
        self.assertIsNotNone(fake.contexts[1]['current_recipe'])
        self.assertEqual(profile3['temporary_restrictions'], [])
        self.assertIsNone(fake.contexts[2]['current_recipe'])
        self.assertEqual(profile4['temporary_restrictions'], [])
        self.assertEqual(profile4['intolerances'], ['oats'])

        with app.app_context():
            conversation = fetch_one(
                'SELECT constraints_json FROM almond_conversations WHERE conversation_id=%s AND user_id=%s',
                (conversation_id, self.user_id),
            )
            db_profile = fetch_one('SELECT allergy_status FROM user_profiles WHERE user_id=%s', (self.user_id,))
            db_intolerance = fetch_one(
                "SELECT label FROM user_restrictions WHERE user_id=%s AND kind='intolerance'",
                (self.user_id,),
            )
        self.assertEqual(json.loads(conversation['constraints_json']), [])
        self.assertEqual(db_profile['allergy_status'], 'none_reported')
        self.assertEqual(db_intolerance['label'], 'oats')
        self.assertEqual(self.current_profile()['intolerances'], ['oats'])

        history = self.client.get(f'/almond/conversations/{conversation_id}')
        self.assertEqual(history.status_code, 200, history.json)
        self.assertEqual(len(history.json['recipes']), 4)


if __name__ == '__main__':
    unittest.main()
