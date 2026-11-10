"""Loopback-only Almond gateway sidecar; leaves the older pipeline untouched.

Run on the gateway host with: python almond_gateway_service.py
Credentials come from ALMOND_VENDOR_ENV and process environment, never the browser.
"""
import hmac
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name('.env.local'))
if os.getenv('ALMOND_VENDOR_ENV'):
    load_dotenv(os.environ['ALMOND_VENDOR_ENV'], override=False)
from almond_gateway import OPENROUTER_MODELS

QWEN_HOSTS = {'international': 'dashscope-intl.aliyuncs.com', 'us': 'dashscope-us.aliyuncs.com',
              'china': 'dashscope.aliyuncs.com', 'eu': 'dashscope-eu.aliyuncs.com'}
QWEN_REGION = os.getenv('ALMOND_QWEN_REGION', 'international')
if QWEN_REGION not in QWEN_HOSTS:
    raise ValueError('Choose a documented ALMOND_QWEN_REGION.')
QWEN_URL = 'https://' + QWEN_HOSTS[QWEN_REGION] + '/compatible-mode/v1/chat/completions'

service = Flask(__name__)
service.config.update(MAX_CONTENT_LENGTH=65536)
ROUTES = {
    'qwen3.7-flash': (QWEN_URL, 'DASHSCOPE_API_KEY'),
    'qwen3.8-flash': (QWEN_URL, 'DASHSCOPE_API_KEY'),
    'deepseek-flash': ('https://api.deepseek.com/chat/completions', 'DEEPSEEK_API_KEY'),
    'glm-5.3-flash': ('https://api.z.ai/api/paas/v4/chat/completions', 'ZAI_API_KEY'),
}


@service.before_request
def authenticate():
    token = os.getenv('ALMOND_GATEWAY_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    if len(token) < 32 or not hmac.compare_digest(supplied, 'Bearer ' + token):
        return {'error': 'Unauthorized'}, 401


@service.get('/health')
def health():
    return {'status': 'online', 'role': 'almond-private-gateway'}


def forward(url, key_name, body):
    key = os.getenv(key_name, '')
    if not key:
        return {'error': 'Provider credential is not configured'}, 503
    outgoing = Request(url, data=json.dumps(body, allow_nan=False).encode(),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
    try:
        with urlopen(outgoing, timeout=40) as response:
            raw = response.read(1048577)
        if len(raw) > 1048576:
            return {'error': 'Upstream response exceeded the limit'}, 502
        result = json.loads(raw)
        return result
    except HTTPError as error:
        # Don't echo vendor bodies, request headers, keys, or profile text.
        return {'error': 'Provider rejected the request', 'upstream_status': error.code}, 502
    except (URLError, OSError, ValueError):
        return {'error': 'Provider outcome is unknown; no retry performed'}, 502


@service.post('/v1/chat/completions')
def chat():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get('model'), str):
        return {'error': 'Unapproved writer'}, 400
    external = body.get('model', '').removeprefix('openrouter/') if isinstance(body.get('model'), str) else ''
    is_external = body.get('model', '').startswith('openrouter/') and external in OPENROUTER_MODELS
    if body.get('model') not in ROUTES and not is_external:
        return {'error': 'Unapproved writer'}, 400
    if set(body) - {'model', 'messages', 'max_tokens', 'stream', 'temperature', 'response_format', 'reasoning_effort'}:
        return {'error': 'Unsupported request field'}, 400
    messages = body.get('messages')
    limit = body.get('max_tokens', 1800)
    if not isinstance(messages, list) or not messages or len(json.dumps(messages).encode()) > 14000:
        return {'error': 'Invalid context'}, 400
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 2000 or body.get('stream'):
        return {'error': 'Invalid output limit'}, 400
    outgoing = {key: body[key] for key in ('model', 'messages', 'max_tokens', 'temperature', 'response_format') if key in body}
    if is_external:
        rates = OPENROUTER_MODELS[external]
        outgoing.update(model=external, reasoning={'effort': 'none'},
            provider={'require_parameters': True, 'max_price': {'prompt': float(rates[0]), 'completion': float(rates[1])}})
        return forward('https://openrouter.ai/api/v1/chat/completions', 'OPENROUTER_API_KEY', outgoing)
    # Provider-specific non-thinking switches prevent hidden, unbounded reasoning spend.
    if body['model'].startswith('qwen'):
        outgoing['enable_thinking'] = False
    else:
        outgoing['thinking'] = {'type': 'disabled'}
    url, key = ROUTES[body['model']]
    return forward(url, key, outgoing)


@service.post('/v1/decisions')
def decisions():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or set(body) - {'model', 'state', 'questions'} or body.get('model') != 'typesafe/jev-1.14':
        return {'error': 'Unapproved decision request'}, 400
    if not isinstance(body.get('questions'), dict) or not body['questions'] or len(json.dumps(body).encode()) > 12500:
        return {'error': 'Invalid decision context'}, 400
    return forward('https://openrouter.ai/api/alpha/decisions', 'OPENROUTER_API_KEY', body)


if __name__ == '__main__':
    from waitress import serve
    if len(os.getenv('ALMOND_GATEWAY_TOKEN', '')) < 32:
        raise SystemExit('Set a separate ALMOND_GATEWAY_TOKEN of at least 32 characters before starting.')
    serve(service, host='127.0.0.1', port=8001, threads=4)
