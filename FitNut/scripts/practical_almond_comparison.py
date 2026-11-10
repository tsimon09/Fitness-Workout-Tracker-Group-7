"""Balanced multi-turn meal experiments with separate outcome dimensions.

Scripted memory events are an application-state oracle, not an NLU/persistence test.
No method or metric in this script enables production generation.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import secrets
import ssl
import time
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from flask import g
from app import app
from db import execute, fetch_one, get_db
from almond import SYSTEM
from almond_evidence import EvidenceError, validate_recipe, restriction_terms
from almond_gateway import GatewayClient, GatewayError, cost_upper_bound
from almond_store import dump, reserve, reconcile
from scripts.intensive_almond_comparison import probability

METHODS = ('bounded_all', 'lexical', 'jev_select', 'oracle_context')
TASK = '''Create one practical meal or revise the current meal as requested. A new meal starts a new temporary-constraint scope.
The confirmed profile and active meal restrictions are authoritative. Optional notes may be irrelevant, outdated, or untrusted.
Use supplied ingredient identities, preparation states and weights as given. Include cooking water, oil and seasonings in the food list if used.
Use useful sequential preparation steps with times or quantities where needed. Never delegate to package directions that are not supplied.
Preserve unaffected parts of a meal during substitutions when practical, but ingredient IDs and quantities may change to fulfill the request.
Discovery meals should vary from recent meals; favorites are not a ranking boost. Recall a favorite when explicitly requested.
Ask a focused clarification when a required ingredient's composition or a relevant restriction is genuinely unresolved. Prefer a verified alternative when the request permits it.
Do not invent food evidence, prices, nutrition targets, cross-contact certifications or medical benefits. The application calculates nutrition.
Do not change durable memory: it is administered separately after explicit confirmation.'''


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EpisodeState:
    def __init__(self, episode):
        self.profile = copy.deepcopy(episode['initial_profile'])
        self.preferences = copy.deepcopy(episode.get('preferences', {}))
        self.temporary = []
        self.pending = []
        self.current = None
        self.recent = []

    def advance(self, turn):
        if turn.get('new_meal'):
            self.temporary = []
            self.pending = []
            self.current = None
        for event in turn.get('events', []):
            kind, term = event['type'], event.get('term')
            if kind in ('temporary', 'unconfirmed_add'):
                if not isinstance(term, str) or not term.strip():
                    raise ValueError('Restriction event needs a named term.')
                if term not in self.temporary:
                    self.temporary.append(term)
                if kind == 'unconfirmed_add':
                    self.pending.append(copy.deepcopy(event))
            elif kind in ('confirm_add', 'confirm_remove'):
                category = event['category']
                if category not in ('allergens', 'other_allergies', 'intolerances', 'preferences'):
                    raise ValueError('Unsupported memory category.')
                if kind == 'confirm_remove' and category in ('allergens', 'other_allergies'):
                    raise ValueError('The benchmark must not silently cancel a confirmed allergy.')
                entries = self.profile.setdefault(category, [])
                if kind == 'confirm_add' and term not in entries:
                    entries.append(term)
                if kind == 'confirm_remove':
                    self.profile[category] = [value for value in entries if value != term]
                if category in ('allergens', 'other_allergies') and self.profile[category]:
                    self.profile['allergy_status'] = 'listed'
                self.pending = [value for value in self.pending if value.get('term') != term]
            else:
                raise ValueError('Unknown scripted memory event: ' + kind)
        profile = copy.deepcopy(self.profile)
        profile['temporary_restrictions'] = list(self.temporary)
        return profile

    def accept(self, recipe, new_meal):
        self.current = copy.deepcopy(recipe)
        brief = {'title': recipe['title'], 'foods': recipe['foods']}
        if new_meal or not self.recent:
            self.recent.append(brief)
        else:
            self.recent[-1] = brief


def words(text):
    return set(re.findall(r'\w+', text.casefold()))


def select_lexical(request, items, maximum=3):
    query = words(request)
    scored = [(len(query & words(item['text'])), index, item) for index, item in enumerate(items)]
    return [item['id'] for score, _, item in sorted(scored, key=lambda value: (-value[0], value[1])) if score > 0][:maximum]


def selection_metrics(items, selected):
    truth = {item['id'] for item in items if item['relevant']}
    chosen = set(selected)
    tp, fp, fn = len(chosen & truth), len(chosen - truth), len(truth - chosen)
    return {'true_positive': tp, 'false_positive': fp, 'false_negative': fn,
            'precision': tp / len(chosen) if chosen else None,
            'recall': tp / len(truth) if truth else None}


def compact_food(food, profile=None):
    keys = ('food_id', 'food_name', 'ingredients', 'allergens', 'evidence_complete', 'evidence_id',
            'calories', 'protein_g', 'dietary_tags',
            'preparation_state')
    result = {key: food[key] for key in keys if key in food}
    if result.get('evidence_complete') is True:
        result.pop('evidence_complete')
    if profile is not None:
        pattern = profile.get('dietary_pattern', 'no_preference')
        if pattern == 'no_preference':
            result.pop('dietary_tags', None)
        else:
            result['dietary_tags'] = [pattern] if pattern in food.get('dietary_tags', []) else []
    coverage = food.get('restriction_coverage', [])
    if profile is not None:
        current = set(restriction_terms(profile))
        coverage = [term for term in coverage if term.casefold() in current]
    if coverage:
        result['restriction_coverage'] = coverage
    return result


def food_metadata(foods):
    return {'nutrient_bases': sorted({food['nutrient_basis'] for food in foods.values()}),
            'retrieval_dates': sorted({food['source_retrieved_at'] for food in foods.values()}),
            'note': 'Evidence_complete omitted means reviewed ingredient identity; false remains explicit. Dietary tags list only the current profile pattern. Full source references/calculations remain on the server. No cross-contact certification.'}


def food_terms(recipe, foods):
    return ' '.join(' '.join([foods[item['food_id']]['food_name'], *foods[item['food_id']]['ingredients']])
                    for item in recipe.get('foods', []) if isinstance(item, dict) and item.get('food_id') in foods).casefold()


def request_assertions(recipe, expect, foods):
    text = food_terms(recipe, foods)
    normalize = lambda values: {word[:-1] if word.endswith('s') else word for word in values}
    present = normalize(words(text))
    def matches(term):
        requested = normalize(words(term))
        if requested in ({'vegetable'}, {'veg'}):
            return bool(present & {'broccoli', 'carrot', 'spinach', 'pea', 'onion', 'tomato', 'asparagus', 'potato'})
        if requested == {'fruit'}:
            return bool(present & {'apple', 'banana', 'pear', 'kiwi', 'orange'})
        if requested == {'bean'}:
            return bool(present & {'bean', 'chickpea', 'garbanzo'})
        return requested <= present
    return {'missing_requested': [term for term in expect.get('must_include_names', []) if not matches(term)],
            'unwanted_requested': [term for term in expect.get('must_exclude_names', []) if matches(term)]}


def load_inputs(paths, food_path, split):
    catalog_data = read_json(food_path)
    catalog = {int(key): value for key, value in catalog_data['catalog'].items()}
    episodes = []
    for path in paths:
        document = read_json(path)
        entries = document if isinstance(document, list) else document['episodes']
        episodes.extend(ep for ep in entries if split == 'all' or ep['split'] == split)
    if len({ep['episode_id'] for ep in episodes}) != len(episodes):
        raise ValueError('Duplicate episode IDs.')
    for episode in episodes:
        if len({turn['turn_id'] for turn in episode['turns']}) != len(episode['turns']):
            raise ValueError('Duplicate turn IDs.')
        for turn in episode['turns']:
            items = turn.get('optional_context', [])
            if len({item['id'] for item in items}) != len(items) or any(type(item.get('relevant')) is not bool for item in items):
                raise ValueError('Each optional item needs a unique ID and boolean relevance label.')
    return episodes, catalog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', choices=METHODS, required=True)
    parser.add_argument('--fixtures', nargs='+', default=['tests/fixtures/almond_practical_episodes_a.json', 'tests/fixtures/almond_practical_episodes_b.json'])
    parser.add_argument('--foods', default='tests/fixtures/almond_practical_foods.json')
    parser.add_argument('--split', choices=('dev', 'heldout', 'all'), default='dev')
    parser.add_argument('--output', required=True)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Explicitly continue a journal with no uncertain in-flight call; never retries recorded turns.')
    args = parser.parse_args()
    episodes, foods = load_inputs(args.fixtures, args.foods, args.split)
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    report = {'method': args.method, 'split': args.split, 'exploratory': True, 'qualified': False,
              'memory_scope': 'Scripted application-state events, not NLU or live database persistence.',
              'hashes': {'runner': digest(__file__), 'system': hashlib.sha256(SYSTEM.encode()).hexdigest(),
                         'task': hashlib.sha256(TASK.encode()).hexdigest(), 'validator': digest('almond_evidence.py'),
                         'foods': digest(args.foods), **{path: digest(path) for path in args.fixtures}}, 'results': []}
    def save():
        pending = out.with_suffix('.tmp')
        pending.write_text(dump(report), encoding='utf-8')
        for attempt in range(20):
            try:
                pending.replace(out)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(.05)  # Retry only the local file replacement, never an API call.
    if args.preflight:
        for episode in episodes:
            state = EpisodeState(episode)
            for turn in episode['turns']:
                profile = state.advance(turn)
                base = {'request': turn['request'], 'profile': profile, 'preferences': state.preferences,
                        'foods': [compact_food(food, profile) for food in foods.values()], 'food_evidence_metadata': food_metadata(foods),
                        'optional_notes': [{'id': item['id'], 'text': item['text']} for item in turn['optional_context']]}
                size = len(dump(base).encode()) + len(SYSTEM.encode()) + len(TASK.encode())
                if size > 11000:
                    raise ValueError('Fixture base context leaves insufficient recipe/repair space: ' + episode['episode_id'] + ' ' + str(size))
        print(dump({'episodes': len(episodes), 'turns': sum(len(ep['turns']) for ep in episodes), 'foods': len(foods), 'hashes': report['hashes']}))
        return
    completed = {}
    if out.exists():
        if not args.resume:
            raise ValueError('Refusing to overwrite an existing run. Inspect its in-flight journal and reservations first.')
        previous = read_json(out)
        if previous.get('in_flight'):
            raise ValueError('An uncertain in-flight call blocks resumption; reconcile it first.')
        if previous['method'] != args.method or previous['split'] != args.split:
            raise ValueError('Resume method/split mismatch.')
        if {key: value for key, value in previous['hashes'].items() if key != 'runner'} != {key: value for key, value in report['hashes'].items() if key != 'runner'}:
            raise ValueError('Resume requires unchanged prompts, validator, catalog and fixtures.')
        runner_hash = report['hashes']['runner']
        report = previous
        report.setdefault('operational_resume_runner_hashes', []).append(runner_hash)
        completed = {(row['episode_id'], row['turn_id']): row for row in report['results']}
    elif args.resume:
        raise ValueError('No recorded run to resume.')
    token = os.getenv('ALMOND_EVAL_GATEWAY_TOKEN', '')
    jev = None
    if args.method == 'jev_select':
        if not token:
            raise ValueError('Configure the evaluation gateway credential privately.')
        certificate = Path('work/gateway-public.pem')
        pem = certificate.read_text()
        if hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() != '5f51208cb1d5c7f1753bc03617c68986ff939d61ae576dd4c4fdcae2e174cfe4':
            raise ValueError('Gateway certificate fingerprint mismatch.')
        trust = ssl.create_default_context(cafile=str(certificate))
        def remote(path, body, ignored):
            req = Request('https://185.145.99.40:8000/api/decisions', data=dump(body).encode(),
                          headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method='POST')
            try:
                with urlopen(req, context=trust, timeout=45) as response:
                    raw = response.read(1048577)
                if len(raw) > 1048576:
                    raise GatewayError('Oversized decision response.')
                return json.loads(raw)
            except HTTPError as error:
                raise GatewayError('Decision gateway HTTP ' + str(error.code) + '; no retry.') from None
        jev = GatewayClient('https://185.145.99.40:8000', token, remote)
    os.environ['ALMOND_QWEN_REGION'] = 'us'
    os.environ['ALMOND_GATEWAY_TOKEN'] = secrets.token_urlsafe(48)
    from almond_gateway_service import service
    local = service.test_client()
    writer = GatewayClient('http://127.0.0.1:8001', os.environ['ALMOND_GATEWAY_TOKEN'],
        lambda path, body, headers: local.post(path, json=body, headers=headers).get_json())
    with app.test_request_context('/'):
        email = 'almond-practical-' + args.method + '@localhost.invalid'
        execute("INSERT IGNORE INTO users (first_name,last_name,email,password_hash,role,status) VALUES ('Almond','Evaluation',%s,'!','user','suspended')", (email,))
        get_db().commit()
        g.user = fetch_one("SELECT user_id FROM users WHERE email=%s AND role='user' AND status='suspended'", (email,))
        if not g.user:
            raise ValueError('Suspended evaluation attribution unavailable.')
        def paid(row, model, operation):
            if sum(call['model'] == model for call in row['calls']) >= (1 if model.startswith('typesafe/') else 2):
                raise ValueError('Per-turn call cap reached.')
            report['in_flight'] = {'episode_id': row['episode_id'], 'turn_id': row['turn_id'], 'model': model, 'stage': 'reserving'}
            save()
            usage_id = reserve(None, model, cost_upper_bound(model, 12500, 0 if model.startswith('typesafe/') else 2000), 'evaluation')
            report['in_flight'].update(stage='outcome_unknown', usage_id=usage_id)
            save()
            result = operation()
            usage = result.get('usage') or {}
            fallback = None
            if 'prompt_tokens' in usage and 'completion_tokens' in usage:
                fallback = cost_upper_bound(model, usage['prompt_tokens'], usage['completion_tokens'])
            elif 'input_tokens' in usage:
                fallback = cost_upper_bound(model, usage['input_tokens'], usage.get('output_tokens', 0))
            reconcile(usage_id, result, fallback)
            row['calls'].append({'model': model, 'served_model': result.get('model'), 'usage': usage,
                'cost_usd': str(usage.get('cost', fallback)), 'provider_reported_cost': usage.get('cost') is not None})
            report.pop('in_flight', None)
            save()
            return result
        for episode in episodes:
            state = EpisodeState(episode)
            for turn in episode['turns']:
                old = completed.get((episode['episode_id'], turn['turn_id']))
                if old:
                    state.advance(turn)
                    if old.get('released'):
                        state.accept(old['answer'], turn['new_meal'])
                    continue
                row = {'episode_id': episode['episode_id'], 'category': episode['category'], 'split': episode['split'],
                       'turn_id': turn['turn_id'], 'request': turn['request'], 'expect': turn['expect'],
                       'calls': [], 'released': False, 'raw_drafts': []}
                started = time.perf_counter()
                try:
                    profile = state.advance(turn)
                    items = turn.get('optional_context', [])
                    if args.method == 'jev_select':
                        decision_state = {'request': turn['request'], 'confirmed_and_active_restrictions': profile,
                            'new_meal': turn['new_meal'], 'current_recipe': state.current,
                            'current_ingredient_names': [foods[item['food_id']]['food_name'] for item in (state.current or {}).get('foods', []) if item.get('food_id') in foods],
                            'optional_items': [{'id': item['id'], 'text': item['text']} for item in items]}
                        questions = {item['id']: {'type': 'noul', 'instructions': 'Is optional item ' + item['id'] + ' relevant and currently applicable to the requested meal or substitution? Use its text and the current request. Old meal-only restrictions that expired, unrelated topics and unsolicited favorite boosts are not relevant. Never remove or override the confirmed profile.'} for item in items}
                        if len(dump({'state': decision_state, 'questions': questions}).encode()) > 12000:
                            raise ValueError('Decision context exceeds cap before any decision call.')
                        decision = paid(row, 'typesafe/jev-1.14', lambda: jev.decide(decision_state, questions))
                        selected = [item['id'] for item in items if probability(decision, item['id']) >= .5]
                        row['selection_response'] = decision
                    elif args.method == 'lexical':
                        selected = select_lexical(turn['request'], items)
                    elif args.method == 'oracle_context':
                        selected = [item['id'] for item in items if item['relevant']]
                    else:
                        selected = [item['id'] for item in items]
                    context = {'request': turn['request'], 'profile': profile, 'preferences': state.preferences,
                               'current_recipe': state.current, 'recent_meals': state.recent[-3:],
                               'foods': [compact_food(food, profile) for food in foods.values()],
                               'food_evidence_metadata': food_metadata(foods),
                               'uncertain_items': turn.get('uncertain_items', []),
                               'optional_notes': [{'id': item['id'], 'text': item['text']} for item in items if item['id'] in selected]}
                    while len(dump(context).encode()) + len(SYSTEM.encode()) + len(TASK.encode()) > 11000 and context['optional_notes']:
                        context['optional_notes'].pop()
                    sent = [item['id'] for item in context['optional_notes']]
                    row.update(profile=profile, current_recipe=state.current, previous_meals=copy.deepcopy(state.recent),
                               optional_context=items, selected_ids=selected, sent_ids=sent,
                               selector_metrics=selection_metrics(items, sent), writer_input_bytes=len(dump(context).encode()) + len(SYSTEM.encode()) + len(TASK.encode()))
                    if row['writer_input_bytes'] > 12000:
                        raise ValueError('Mandatory context exceeds cap; no writer call made.')
                    messages = [{'role': 'system', 'content': SYSTEM + '\n' + TASK}, {'role': 'user', 'content': dump(context)}]
                    error = None
                    for attempt in range(2):
                        response = paid(row, 'qwen3.8-flash', lambda: writer.chat('qwen3.8-flash', messages, 1800))
                        raw_text = response['choices'][0]['message']['content']
                        row.setdefault('raw_text', []).append(raw_text)
                        try:
                            proposal = json.loads(raw_text)
                        except ValueError:
                            proposal = {'malformed_json': True}
                        row['raw_drafts'].append(proposal)
                        error = None
                        if isinstance(proposal, dict) and 'foods' in proposal:
                            try:
                                checked = validate_recipe(proposal, foods, profile)
                                if any(item.get('mandatory') for item in turn.get('uncertain_items', [])):
                                    raise EvidenceError('A required ingredient or restriction is unresolved; ask for clarification.')
                            except (EvidenceError, ValueError, KeyError, TypeError) as failure:
                                error = str(failure)
                        elif not isinstance(proposal, dict) or not isinstance(proposal.get('clarification'), str) or not proposal['clarification'].strip():
                            error = 'Return a recipe object or a focused clarification.'
                        row.setdefault('validation_errors', []).append(error)
                        if error is None or attempt:
                            break
                        messages.extend([{'role': 'assistant', 'content': dump(proposal)},
                                         {'role': 'user', 'content': 'Repair using the supplied evidence, or ask a focused clarification: ' + error}])
                        while sum(len(message['content'].encode()) for message in messages) > 11000 and context['optional_notes']:
                            context['optional_notes'].pop()
                            messages[1]['content'] = dump(context)
                            row['repair_optional_notes_dropped'] = True
                        if sum(len(message['content'].encode()) for message in messages) > 12000:
                            raise ValueError('Repair context exceeds cap; no repair call made.')
                    row['final_validation_error'] = error
                    if error is None and 'foods' in proposal:
                        row['released'] = True
                        row['answer'] = proposal
                        row['nutrition'] = checked['nutrition']
                        row['request_assertions'] = request_assertions(proposal, turn['expect'], foods)
                        state.accept(proposal, turn['new_meal'])
                    else:
                        row['answer'] = proposal if error is None else {'clarification': 'The recipe could not be supported by the supplied evidence.'}
                    row['appropriate_clarification'] = (not row['released']) == (not turn['expect']['answerable'])
                    row['state_after'] = {'confirmed_profile': copy.deepcopy(state.profile), 'active_temporary': list(state.temporary),
                                          'pending_unconfirmed': copy.deepcopy(state.pending)}
                except Exception as failure:
                    row['error'] = type(failure).__name__ + ': ' + str(failure)[:200]
                row['latency_seconds'] = round(time.perf_counter() - started, 3)
                report['results'].append(row)
                report['ledger'] = {key: str(value) for key, value in fetch_one("SELECT cap_usd,spent_usd,reserved_usd FROM almond_budgets WHERE scope='evaluation'").items()}
                save()
                print(dump({key: row.get(key) for key in ('episode_id', 'turn_id', 'category', 'released', 'error')}), flush=True)
                if row.get('error') and (row['error'].startswith('GatewayError:')
                                         or 'budget' in row['error'].casefold() or report.get('in_flight')):
                    return  # No retry/continuation while an upstream outcome is uncertain.


if __name__ == '__main__':
    main()
