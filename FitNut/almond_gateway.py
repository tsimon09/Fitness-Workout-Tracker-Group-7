"""Small authenticated gateway client. No hidden retries or provider selection."""
import ipaddress
import json
import os
import re
from decimal import Decimal
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

RATES = {'qwen3.7-flash': ('.03', '.13'), 'qwen3.8-flash': ('.15', '.47'),
         'deepseek-flash': ('.30', '1.20'), 'glm-5.3-flash': ('.15', '.50'),
         'typesafe/jev-1.14': ('.042', '0')}


def load_openrouter_registry(raw):
    """Operator-approved real provider/model IDs with explicit uncached price ceilings."""
    try:
        registry = json.loads(raw)
        if not isinstance(registry, dict) or len(registry) > 10:
            raise ValueError()
        for model, rates in registry.items():
            if not re.fullmatch(r'[a-z0-9_-]+/[a-z0-9_.:-]+', model) or 'gemini' in model or model.startswith(('google/', 'openrouter/', 'typesafe/')):
                raise ValueError()
            if not isinstance(rates, list) or len(rates) != 2:
                raise ValueError()
            for rate in rates:
                value = Decimal(str(rate))
                if isinstance(rate, bool) or not value.is_finite() or not 0 <= value <= 100:
                    raise ValueError()
        return registry
    except (ValueError, TypeError, ArithmeticError):
        raise GatewayError('Invalid approved OpenRouter registry.') from None


class GatewayError(ValueError):
    pass


OPENROUTER_MODELS = load_openrouter_registry(os.getenv('ALMOND_OPENROUTER_MODELS', '{}'))
RATES.update({'openrouter/' + model: rates for model, rates in OPENROUTER_MODELS.items()})
WRITERS = frozenset(RATES) - {'typesafe/jev-1.14'}


def cost_upper_bound(model, input_tokens, output_tokens):
    if model not in RATES:
        raise GatewayError('Model has no approved rate card.')
    values = []
    for value in (input_tokens, output_tokens):
        if isinstance(value, bool):
            raise GatewayError('Invalid token count.')
        try:
            value = Decimal(str(value))
        except Exception:
            raise GatewayError('Invalid token count.') from None
        if not value.is_finite() or value < 0 or value > 1000000 or value != int(value):
            raise GatewayError('Invalid token count.')
        values.append(value)
    # Qwen 3.7 pricing rises above 32k input. Normal Almond calls are capped below it.
    rates = ('.10', '.40') if model == 'qwen3.7-flash' and values[0] > 32000 else RATES[model]
    return sum(value * Decimal(rate) for value, rate in zip(values, rates)) / 1000000


class GatewayClient:
    def __init__(self, base_url, token, transport=None):
        parsed = urlsplit(base_url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise GatewayError('Invalid gateway URL.')
        loopback = parsed.hostname == 'localhost'
        try:
            loopback = loopback or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            pass
        if parsed.scheme == 'http' and not loopback:
            raise GatewayError('HTTP gateway connections must use loopback.')
        if parsed.path.rstrip('/') not in ('', '/v1'):
            raise GatewayError('Gateway URL must end at the host or /v1.')
        if not isinstance(token, str) or not token.strip():
            raise GatewayError('Gateway credential is missing.')
        self.base = base_url.rstrip('/').removesuffix('/v1')
        self.token = token
        self.transport = transport or self._transport

    def _transport(self, path, payload, headers):
        request = Request(self.base + path, data=json.dumps(payload, allow_nan=False).encode(), headers=headers, method='POST')
        try:
            with urlopen(request, timeout=45) as response:
                raw = response.read(1048577)
            if len(raw) > 1048576:
                raise GatewayError('Gateway response is too large.')
            return json.loads(raw)
        except (URLError, HTTPError, OSError, ValueError):
            raise GatewayError('Gateway request failed; its cost reservation is retained until reconciled.') from None

    def _call(self, path, payload):
        try:
            result = self.transport(path, payload, {'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        except GatewayError:
            raise
        except Exception:
            raise GatewayError('Gateway request failed; no automatic retry was made.') from None
        if not isinstance(result, dict) or result.get('error'):
            raise GatewayError('Invalid gateway response.')
        return result

    def chat(self, model, messages, max_tokens=1500):
        if model not in WRITERS:
            raise GatewayError('Writer model is not approved.')
        if not isinstance(messages, list) or not messages or any(not isinstance(m, dict) or m.get('role') not in ('system', 'user', 'assistant') or not isinstance(m.get('content'), str) for m in messages):
            raise GatewayError('Invalid writer messages.')
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= 2000:
            raise GatewayError('Output token limit must be between 1 and 2000.')
        if sum(len(m['content'].encode()) for m in messages) > 12000:
            raise GatewayError('Writer context exceeds the conservative 12000-token input budget.')
        result = self._call('/v1/chat/completions', {'model': model, 'messages': messages,
            'max_tokens': max_tokens, 'stream': False, 'temperature': 0,
            'response_format': {'type': 'json_object'}, 'reasoning_effort': 'none'})
        try:
            if not isinstance(result['choices'][0]['message']['content'], str):
                raise KeyError('content')
        except (KeyError, IndexError, TypeError):
            raise GatewayError('Writer returned no content.') from None
        return result

    def decide(self, state, questions):
        if not isinstance(questions, dict) or not questions:
            raise GatewayError('Decision questions are required.')
        if len(json.dumps({'state': state, 'questions': questions}, ensure_ascii=False).encode()) > 12000:
            raise GatewayError('Decision context is too large.')
        result = self._call('/v1/decisions', {'model': 'typesafe/jev-1.14', 'state': state, 'questions': questions})
        if not isinstance(result.get('answers'), dict):
            raise GatewayError('Decision response has no answers.')
        return result
