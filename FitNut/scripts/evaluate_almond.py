"""Budgeted writer benchmark. No model is qualified without two independent reviews.

Examples (on the gateway server, with .env.local configured):
 python -m scripts.evaluate_almond --dry-run
 python -m scripts.evaluate_almond --split dev --user-id 1 --output work/almond-dev.json
 python -m scripts.evaluate_almond --split heldout --user-id 1 --output work/almond-heldout.json
 python -m scripts.evaluate_almond --finalize work/almond-heldout.json --reviews work/reviews.json

Reviews: list of {model,case_id,reviewer,critical_failure,useful,coherence,reference_ids}.
Two distinct reviewers must agree on critical_failure/useful and cite supplied evidence.
Never feed held-out outputs or review feedback back into writer prompt development.
"""
import argparse
import copy
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from decimal import Decimal
from flask import g
from app import app
from db import fetch_one, execute, get_db
from almond import SYSTEM
from almond_evidence import validate_recipe, EvidenceError
from almond_gateway import GatewayClient, WRITERS, cost_upper_bound
from almond_store import dump, reserve, reconcile


def case_inputs(data, case):
    foods = {int(key): copy.deepcopy(value) for key, value in data['catalog'].items()}
    recipe = copy.deepcopy(case['recipe'])
    mutation = recipe.pop('fixture_mutation', None)
    target = foods.get(101, {})
    mutations = {'missing_evidence': ('evidence_complete', False), 'wrong_food_name': ('food_name', 'Apples, raw, with skin'),
        'wrong_ingredients': ('ingredients', ['apple']), 'missing_allergen': ('allergens', []),
        'negative_calories': ('calories', -1), 'nan_macro': ('protein_g', 'NaN')}
    if mutation in mutations:
        key, value = mutations[mutation]
        target[key] = value
    elif mutation == 'foreign_evidence': recipe['evidence_ids'] = ['foreign-source']
    elif mutation == 'boolean_food_id': recipe['foods'][0]['food_id'] = True
    elif mutation == 'boolean_grams': recipe['foods'][0]['grams'] = True
    elif mutation == 'empty_title': recipe['title'] = ''
    return recipe, foods


def finalize(report_path, reviews_path):
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    reviews = json.loads(Path(reviews_path).read_text(encoding='utf-8'))
    if report.get('regression_only', True):
        raise ValueError('The known regression fixtures cannot qualify a writer. Supply a separately frozen, independently labeled benchmark.')
    if report.get('split') != 'heldout' or report.get('prompt_sha256') != hashlib.sha256(SYSTEM.encode()).hexdigest():
        raise ValueError('Only held-out results for the current frozen prompt may qualify.')
    summary = []
    for model in sorted({row['model'] for row in report['results']}):
        rows = [row for row in report['results'] if row['model'] == model]
        complete = len(rows) == 60 and len({row['case_id'] for row in rows}) == 60 and all(row.get('cost_known', False) for row in rows)
        critical, useful, coherence = 0, 0, []
        eligible = sum(row['expected'] == 'accept' for row in rows)
        for row in rows:
            grades = [v for v in reviews if v.get('model') == model and v.get('case_id') == row['case_id']]
            unique = {v.get('reviewer') for v in grades if v.get('reviewer')}
            valid = len(unique) >= 2 and len(grades) == 2 and all(
                isinstance(v.get('critical_failure'), bool) and isinstance(v.get('useful'), bool)
                and isinstance(v.get('coherence'), int) and 1 <= v['coherence'] <= 5
                and v.get('reference_ids') and set(v['reference_ids']) <= set(row['reference_ids']) for v in grades)
            agree = valid and grades[0]['critical_failure'] == grades[1]['critical_failure'] and grades[0]['useful'] == grades[1]['useful']
            if not agree:
                complete = False
                continue
            critical += bool(grades[0]['critical_failure']) or row.get('critical_failure', False)
            useful += row['expected'] == 'accept' and row.get('validated', False) and all(v['useful'] for v in grades)
            coherence.extend(v['coherence'] for v in grades)
        structured = sum(row.get('structured', False) for row in rows) / max(len(rows), 1)
        completion = useful / max(eligible, 1)
        qualified = complete and critical == 0 and structured >= .95 and completion >= .8
        item = {'model': model, 'qualified': qualified, 'critical_failures': critical, 'structured_rate': structured,
                'useful_completion_rate': completion, 'coherence': sum(coherence) / max(len(coherence), 1),
                'cost_usd': str(sum(Decimal(str(row.get('cost_usd', 0))) for row in rows)),
                'prompt_sha256': report['prompt_sha256'], 'fixture_sha256': report['fixture_sha256']}
        summary.append(item)
        execute('INSERT INTO almond_evaluations (model,qualified,report) VALUES (%s,%s,%s)', (model, qualified, dump(item)))
    get_db().commit()
    passing = sorted([s for s in summary if s['qualified']], key=lambda s: (-s['useful_completion_rate'], -s['coherence'], Decimal(s['cost_usd'])))
    print(dump({'summary': summary, 'selected_writer': passing[0]['model'] if passing else None,
                'generation_enabled': False}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--split', choices=['dev', 'heldout'], default='dev')
    parser.add_argument('--user-id', type=int)
    parser.add_argument('--model', choices=sorted(WRITERS), action='append')
    parser.add_argument('--output', default='work/almond-evaluation.json')
    parser.add_argument('--fixtures', default=str(Path(__file__).resolve().parents[1] / 'tests/fixtures/almond_writer_benchmark.json'))
    parser.add_argument('--finalize')
    parser.add_argument('--reviews')
    parser.add_argument('--local-qwen-us', action='store_true', help='Use the local sidecar adapter in-process with the inherited US DashScope key; no server credential is needed.')
    parser.add_argument('--service-account', action='store_true', help='Attribute evaluation to a suspended, non-login local service user instead of an administrator.')
    args = parser.parse_args()
    if args.finalize:
        if not args.reviews:
            parser.error('--finalize requires --reviews')
        with app.app_context(): finalize(args.finalize, args.reviews)
        return
    fixture_bytes = Path(args.fixtures).read_bytes()
    data = json.loads(fixture_bytes)
    if data.get('metadata', {}).get('frozen_prompt_sha256', data.get('frozen_prompt_sha256')) not in (None, hashlib.sha256(SYSTEM.encode()).hexdigest()):
        raise ValueError('Benchmark was frozen for a different writer prompt. Do not silently tune against held-out cases.')
    cases = [case for case in data['cases'] if case['split'] == args.split]
    models = args.model or (['qwen3.7-flash', 'qwen3.8-flash'] if args.local_qwen_us else sorted(WRITERS))
    if args.local_qwen_us and any(model not in ('qwen3.7-flash', 'qwen3.8-flash') for model in models):
        parser.error('--local-qwen-us supports only the two Qwen candidates')
    if args.dry_run:
        ceiling = sum(cost_upper_bound(model, 12500, 2000) * len(cases) for model in models)
        print(dump({'models': models, 'cases_per_model': len(cases), 'split': args.split,
            'maximum_reservation_usd': str(ceiling), 'evaluation_cap_usd': '2.00',
            'note': 'No API calls. Run dev first; held-out labels are for grading only. These fixtures test supplied evidence, not clinical safety.'}))
        return
    if args.local_qwen_us:
        os.environ['ALMOND_QWEN_REGION'] = 'us'
        os.environ['ALMOND_GATEWAY_TOKEN'] = secrets.token_urlsafe(48)
        from almond_gateway_service import service
        local_service = service.test_client()
        def transport(path, body, headers):
            response = local_service.post(path, json=body, headers=headers)
            return response.get_json() or {'error': 'Invalid sidecar response'}
        client = GatewayClient('http://127.0.0.1:8001', os.environ['ALMOND_GATEWAY_TOKEN'], transport)
    else:
        client = GatewayClient(os.getenv('ALMOND_GATEWAY_URL', 'http://127.0.0.1:8001'), os.getenv('ALMOND_GATEWAY_TOKEN', ''))
    report = {'split': args.split, 'regression_only': Path(args.fixtures).resolve() == (Path(__file__).resolve().parents[1] / 'tests/fixtures/almond_cases.json').resolve(),
              'prompt_sha256': hashlib.sha256(SYSTEM.encode()).hexdigest(),
              'fixture_sha256': hashlib.sha256(fixture_bytes).hexdigest(), 'results': []}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    with app.test_request_context('/'):
        if args.service_account:
            execute("""INSERT IGNORE INTO users (first_name,last_name,email,password_hash,role,status)
                VALUES ('Almond','Evaluation','almond-evaluation@localhost.invalid','!','user','suspended')""")
            get_db().commit()
            user = fetch_one("SELECT user_id FROM users WHERE email='almond-evaluation@localhost.invalid' AND role='user' AND status='suspended'")
        else:
            user = fetch_one("SELECT user_id FROM users WHERE user_id=%s AND role='admin' AND status='active'", (args.user_id,))
        if not user: raise ValueError('Supply an existing active administrator --user-id for evaluation attribution.')
        g.user = user
        for model in models:
            for case in cases:
                recipe, foods = case_inputs(data, case)
                context = {'request': 'Assess this proposed meal. If the proposal or its evidence is invalid, ask for clarification. Otherwise preserve its ingredient IDs and quantities and provide coherent instructions.',
                           'profile': case['profile'], 'current_recipe': recipe, 'foods': list(foods.values())}
                row = {'model': model, 'case_id': case['case_id'], 'expected': case['expected'],
                       'reference_ids': [food['evidence_id'] for food in foods.values()]}
                usage_id = reserve(None, model, cost_upper_bound(model, 12500, 2000), 'evaluation')
                started = time.perf_counter()
                try:
                    response = client.chat(model, [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': dump(context)}], 2000)
                    usage = response.get('usage') or {}
                    fallback = cost_upper_bound(model, usage['prompt_tokens'], usage['completion_tokens']) if 'prompt_tokens' in usage and 'completion_tokens' in usage else None
                    reconcile(usage_id, response, fallback)
                    known_cost = usage.get('cost', fallback)
                    row.update(response=response, cost_usd=str(known_cost or 0), cost_known=known_cost is not None, structured=False, validated=False, critical_failure=False)
                    answer = json.loads(response['choices'][0]['message']['content'])
                    row['structured'] = isinstance(answer, dict) and ('clarification' in answer or 'foods' in answer)
                    if 'foods' in answer:
                        try:
                            validate_recipe(answer, foods, case['profile'])
                            row['validated'] = True
                            row['critical_failure'] = case['expected'] == 'reject'
                        except EvidenceError as error:
                            row['critical_failure'] = True; row['validation_error'] = str(error)
                except ValueError as error:
                    row['error'] = str(error)
                row['latency_seconds'] = round(time.perf_counter() - started, 3)
                report['results'].append(row)
                output.write_text(dump(report), encoding='utf-8')
                print(dump({'model': model, 'case': case['case_id'], 'structured': row.get('structured', False),
                    'validated': row.get('validated', False), 'error': row.get('error'), 'cost_usd': row.get('cost_usd'),
                    'latency_seconds': row['latency_seconds']}), flush=True)
                if row.get('error') and 'Gateway' in row['error']:
                    print('Stopping this model after a gateway failure; its reservation remains held.', flush=True)
                    break
    print('Evaluation saved; independent review is required before qualification. Generation stays disabled.')


if __name__ == '__main__': main()
