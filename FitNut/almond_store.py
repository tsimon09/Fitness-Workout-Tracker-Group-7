"""User-owned Almond persistence and atomic, project-specific cost reservations."""
import json
from decimal import Decimal
from flask import g
from db import execute, fetch_all, fetch_one, get_db


def unpack(value, default=None):
    if value is None:
        return default
    return json.loads(value) if isinstance(value, (str, bytes)) else value


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, default=str)


def own_conversation(conversation_id):
    if isinstance(conversation_id, bool) or not isinstance(conversation_id, int):
        raise ValueError('Choose a conversation.')
    row = fetch_one('SELECT * FROM almond_conversations WHERE conversation_id=%s AND user_id=%s',
                    (conversation_id, g.user['user_id']))
    if not row:
        raise LookupError('Conversation not found')
    return row


def memory():
    row = fetch_one('SELECT * FROM almond_memory WHERE user_id=%s', (g.user['user_id'],))
    return {'cuisines': unpack(row['cuisines'], []) if row else [],
            'cooking_minutes': row['cooking_minutes'] if row else None,
            'food_budget': row['food_budget'] if row else None}


def catalog():
    rows = fetch_all('''SELECT f.*, e.evidence, e.reviewed_at FROM food_catalog f
        JOIN almond_food_evidence e ON e.food_id=f.food_id
        WHERE e.reviewed_at >= UTC_TIMESTAMP() - INTERVAL 30 DAY ORDER BY f.food_id LIMIT 200''')
    result = {}
    for row in rows:
        evidence = unpack(row.pop('evidence'))
        result[row['food_id']] = {**row, **evidence, 'food_id': row['food_id'],
            'food_name': row['food_name'], 'reviewed_at': str(row['reviewed_at'])}
    return result


def reserve(request_id, model, amount, scope='team'):
    amount = Decimal(str(amount))
    if scope not in ('team', 'evaluation') or not amount.is_finite() or amount <= 0:
        raise ValueError('Invalid budget reservation.')
    cap = '2.00' if scope == 'evaluation' else '3.00'
    # Acquire an exclusive duplicate-row lock immediately. INSERT IGNORE takes
    # shared locks that can deadlock when concurrent callers upgrade FOR UPDATE.
    # Preserve the existing cap, including any operator-imposed lower ceiling.
    execute('''INSERT INTO almond_budgets (scope, cap_usd) VALUES (%s,%s)
        ON DUPLICATE KEY UPDATE cap_usd=almond_budgets.cap_usd''', (scope, cap))
    budget = fetch_one('SELECT * FROM almond_budgets WHERE scope=%s FOR UPDATE', (scope,))
    if budget['spent_usd'] + budget['reserved_usd'] + amount > budget['cap_usd']:
        get_db().rollback()
        raise ValueError('Almond ' + scope + ' budget is exhausted.')
    execute('UPDATE almond_budgets SET reserved_usd=reserved_usd+%s WHERE scope=%s', (amount, scope))
    usage_id, _ = execute('''INSERT INTO almond_usage (request_id, user_id, scope, model, reserved_usd)
        VALUES (%s,%s,%s,%s,%s)''', (request_id, g.user['user_id'], scope, model, amount))
    get_db().commit()
    return usage_id


def reconcile(usage_id, result, fallback_cost=None):
    usage = result.get('usage') or {}
    cost = usage.get('cost', fallback_cost)
    if cost is None:
        return  # Unknown outcome remains reserved until an administrator reconciles it.
    cost = Decimal(str(cost))
    if not cost.is_finite() or cost < 0:
        return
    row = fetch_one('SELECT * FROM almond_usage WHERE usage_id=%s FOR UPDATE', (usage_id,))
    if not row or row['status'] != 'reserved':
        get_db().rollback()
        return
    # An upstream reporting more than the maximum cannot be undone. Record it and disable further spending.
    execute('''UPDATE almond_budgets SET reserved_usd=reserved_usd-%s, spent_usd=spent_usd+%s
        WHERE scope=%s''', (row['reserved_usd'], cost, row['scope']))
    execute('''UPDATE almond_usage SET status='settled', actual_usd=%s, upstream_id=%s, usage_json=%s
        WHERE usage_id=%s''', (cost, str(result.get('id', ''))[:150], dump(usage), usage_id))
    get_db().commit()
