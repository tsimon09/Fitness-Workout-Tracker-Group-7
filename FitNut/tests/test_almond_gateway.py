"""Pure contract tests for the Almond gateway client; no network calls."""
import os
import unittest
from decimal import Decimal
from unittest.mock import patch

from almond_gateway import GatewayClient, GatewayError, cost_upper_bound, load_openrouter_registry
import almond_gateway_service


class GatewayClientTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def transport(path, payload, headers):
            self.calls.append((path, payload, headers))
            if path == '/v1/decisions':
                return {'answers': {'choice': 'safe'}}
            return {'choices': [{'message': {'content': '{"ok":true}'}}],
                    'usage': {'prompt_tokens': 12, 'completion_tokens': 4},
                    'cost': '0.000004'}

        self.client = GatewayClient('http://127.0.0.1:8000', 'test-token', transport)

    def test_chat_uses_gateway_path_auth_and_pinned_safe_payload(self):
        result = self.client.chat('qwen3.7-flash', [{'role': 'user', 'content': 'hello'}])
        self.assertEqual(result['usage']['prompt_tokens'], 12)
        self.assertEqual(result['cost'], '0.000004')
        path, payload, headers = self.calls[0]
        self.assertEqual(path, '/v1/chat/completions')
        self.assertEqual(headers['Authorization'], 'Bearer test-token')
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(payload['model'], 'qwen3.7-flash')
        self.assertEqual(payload['max_tokens'], 1500)
        self.assertFalse(payload['stream'])

    def test_decide_pins_jev_and_preserves_usage_and_cost(self):
        result = self.client.decide({'mode': 'test'}, {'question': 'choose'})
        self.assertEqual(result['answers'], {'choice': 'safe'})
        path, payload, _ = self.calls[0]
        self.assertEqual(path, '/v1/decisions')
        self.assertEqual(payload['model'], 'typesafe/jev-1.14')

    def test_rejects_unapproved_models_and_provider_url_injection(self):
        for model in ('gemini-2.5-flash', 'openrouter/unknown', 'https://evil.test/model',
                      'qwen3.7-flash;https://evil.test'):
            with self.subTest(model=model):
                with self.assertRaises(GatewayError):
                    self.client.chat(model, [{'role': 'user', 'content': 'hello'}])
        self.assertEqual(self.calls, [])

    def test_all_approved_direct_writer_ids_are_accepted(self):
        allowed = ('qwen3.7-flash', 'qwen3.8-flash', 'deepseek-flash', 'glm-5.3-flash')
        for model in allowed:
            with self.subTest(model=model):
                result = self.client.chat(model, [{'role': 'user', 'content': 'hello'}])
                self.assertIn('choices', result)
        self.assertEqual([call[1]['model'] for call in self.calls], list(allowed))

    def test_unverified_openrouter_aliases_are_rejected(self):
        for model in ('openrouter/qwen3.7-flash', 'openrouter/qwen3.8-flash',
                      'openrouter/deepseek-flash', 'openrouter/glm-5.3-flash',
                      'openrouter/google/gemini-2.5-flash'):
            with self.subTest(model=model):
                with self.assertRaises(GatewayError):
                    self.client.chat(model, [{'role': 'user', 'content': 'hello'}])
        self.assertEqual(self.calls, [])

    def test_invalid_gateway_urls_rejected(self):
        for url in ('http://gateway.example:8000', 'http://192.168.1.8:8000',
                    'http://127.0.0.1.evil.test:8000', 'http://user:pass@127.0.0.1:8000',
                    'http://127.0.0.1:8000/other', 'http://127.0.0.1:8000/?x=1',
                    'ftp://127.0.0.1:8000'):
            with self.subTest(url=url):
                with self.assertRaises(GatewayError):
                    GatewayClient(url, 'token', lambda *_: {})

    def test_accepts_loopback_http_and_verified_https(self):
        for url in ('http://127.0.0.1:8000', 'http://localhost:8000', 'http://[::1]:8000',
                    'https://gateway.example:8000'):
            with self.subTest(url=url):
                GatewayClient(url, 'token', lambda *_: {})

    def test_transport_failure_is_not_retried_and_is_reported_as_unknown_outcome(self):
        attempts = []

        def fail(*_):
            attempts.append(1)
            raise TimeoutError()

        client = GatewayClient('http://localhost:8000', 'token', fail)
        with self.assertRaisesRegex(GatewayError, 'no automatic retry'):
            client.chat('deepseek-flash', [{'role': 'user', 'content': 'hello'}])
        self.assertEqual(attempts, [1])

    def test_invalid_gateway_responses_raise_gateway_error(self):
        for value in ({'error': 'upstream'}, [], {'choices': []},
                      {'choices': [{'message': {'content': None}}]}):
            with self.subTest(value=value):
                client = GatewayClient('http://localhost:8000', 'token', lambda *_: value)
                with self.assertRaises(GatewayError):
                    client.chat('glm-5.3-flash', [{'role': 'user', 'content': 'hello'}])


class CostUpperBoundTests(unittest.TestCase):
    def test_uncached_rate_cards_are_conservative_and_decimal(self):
        self.assertEqual(cost_upper_bound('qwen3.7-flash', 1000, 1000), Decimal('.00016'))
        self.assertEqual(cost_upper_bound('qwen3.8-flash', 1000000, 1000000), Decimal('.62'))
        self.assertEqual(cost_upper_bound('deepseek-flash', 1000000, 1000000), Decimal('1.50'))
        self.assertEqual(cost_upper_bound('glm-5.3-flash', 1000000, 1000000), Decimal('.65'))
        self.assertEqual(cost_upper_bound('typesafe/jev-1.14', 1000000, 1000000), Decimal('.042'))
        self.assertEqual(cost_upper_bound('qwen3.7-flash', 32001, 0), Decimal('.0032001'))

    def test_rejects_unknown_negative_nonfinite_fractional_and_unbounded_counts(self):
        bad = (-1, float('nan'), float('inf'), 1.5, True, 1000001, 'not-a-number')
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(GatewayError):
                    cost_upper_bound('qwen3.8-flash', value, 0)
        with self.assertRaises(GatewayError):
            cost_upper_bound('gemini-2.5-flash', 1, 1)


class OpenRouterRegistryTests(unittest.TestCase):
    def test_accepts_explicit_provider_model_and_two_nonnegative_rate_caps(self):
        registry = load_openrouter_registry(
            '{"anthropic/claude-3-5-haiku":[0.8,4.0],"qwen/qwen3.5-flash":[0,0.2]}')
        self.assertEqual(registry['anthropic/claude-3-5-haiku'], [0.8, 4.0])
        self.assertEqual(registry['qwen/qwen3.5-flash'], [0, 0.2])

    def test_rejects_malformed_registry_and_invalid_prices_or_model_ids(self):
        invalid = (
            '{',
            '[]',
            '"anthropic/claude-3-5-haiku"',
            '{"anthropic/claude-3-5-haiku":[NaN,1]}',
            '{"anthropic/claude-3-5-haiku":[-0.1,1]}',
            '{"anthropic/claude-3-5-haiku":[1]}',
            '{"anthropic/claude-3-5-haiku":[true,1]}',
            '{"google/gemini-2.5-flash":[0.1,0.2]}',
            '{"anthropic/gemini-2.5-flash":[0.1,0.2]}',
            '{"fake-model-without-provider":[0.1,0.2]}',
            '{"openrouter/anthropic/claude-3-5-haiku":[0.1,0.2]}',
        )
        for raw in invalid:
            with self.subTest(raw=raw):
                with self.assertRaises(GatewayError):
                    load_openrouter_registry(raw)


class GatewaySidecarTests(unittest.TestCase):
    def test_sidecar_requires_strong_bearer_token_and_rejects_unapproved_models(self):
        token = 'test-gateway-token-' + ('x' * 40)
        client = almond_gateway_service.service.test_client()
        with patch.dict(os.environ, {'ALMOND_GATEWAY_TOKEN': token}):
            unauthenticated = client.post('/v1/chat/completions', json={'model': 'qwen3.7-flash'})
            rejected = client.post('/v1/chat/completions', headers={'Authorization': 'Bearer ' + token},
                                   json={'model': 'openrouter/qwen3.7-flash', 'messages': [{'role': 'user', 'content': 'x'}]})
            short = patch.dict(os.environ, {'ALMOND_GATEWAY_TOKEN': 'tiny'})
            with short:
                weak_config = client.get('/health', headers={'Authorization': 'Bearer tiny'})
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(weak_config.status_code, 401)
        self.assertNotIn(token, unauthenticated.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
