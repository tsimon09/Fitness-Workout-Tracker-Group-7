"""Food, activity, and sleep records belong to the logged-in user."""
from flask import Blueprint, g, request
from accounts import login_required
from db import execute, fetch_all, fetch_one, get_db, to_json
from validation import date_time, number, payload, text
from log_data import LOG_TYPES, read_items, stored_values, remove_empty_meal
from nutrition import calculate_food, search_foods, FoodServiceUnavailable
from estimates import calculate_activity

logs = Blueprint("logs", __name__)


def checked_values(kind, data):
    if kind == "food":
        event_id = data.get('eating_event_id')
        if event_id not in (None, ''):
            if isinstance(event_id, bool) or not str(event_id).isdigit() or not 0 < int(event_id) <= 2147483647:
                raise ValueError('Choose a valid meal')
            event_id = int(event_id)
        else:
            event_id = None
        meal = data.get("meal_type")
        if meal not in ("breakfast", "lunch", "dinner", "snack"):
            raise ValueError("Choose breakfast, lunch, dinner, or snack")
        values = {"food_name": text(data, "food_name", 150),
                "quantity": number(data, "quantity", positive=True, maximum="9999999.999", places=3),
                "quantity_unit": text(data, "quantity_unit", 30), "meal_type": meal,
                "calories": number(data, "calories", optional=True),
                "protein_g": number(data, "protein_g", optional=True),
                "carbs_g": number(data, "carbs_g", optional=True),
                "fat_g": number(data, "fat_g", optional=True), "fiber_g": number(data, "fiber_g", optional=True),
                "logged_at": date_time(data, "logged_at", required=True), "eating_event_id": event_id,
                "meal_notes": text(data, "meal_notes", 2000, required=False)}
        return calculate_food(data, values)
    if kind == "activity":
        if data.get("intensity") not in ("low", "moderate", "high"):
            raise ValueError("Choose low, moderate, or high intensity")
        values = {"activity_name": text(data, "activity_name", 100),
                "intensity": data["intensity"],
                "duration_minutes": number(data, "duration_minutes", positive=True),
                "calories_burned": number(data, "calories_burned", optional=True),
                "distance_km": number(data, "distance_km", optional=True, maximum="9999999.999", places=3),
                "set_count": number(data, "set_count", positive=True, optional=True, maximum="2147483647", places=0),
                "rep_count": number(data, "rep_count", positive=True, optional=True, maximum="2147483647", places=0),
                "performed_at": date_time(data, "performed_at", required=True),
                "notes": text(data, "notes", 2000, required=False)}
        return calculate_activity(data, values)
    start, end = date_time(data, "sleep_start", required=True), date_time(data, "sleep_end", required=True)
    if end <= start:
        raise ValueError("Sleep end must be after sleep start")
    quality = data.get("sleep_quality")
    if quality is not None and quality != "":
        if isinstance(quality, bool) or str(quality) not in ("1", "2", "3", "4", "5"):
            raise ValueError("Sleep quality must be from 1 to 5")
        quality = int(quality)
    else:
        quality = None
    return {"sleep_start": start, "sleep_end": end, "sleep_quality": quality,
            "notes": text(data, "notes", 2000, required=False)}


def kind_for_request():
    return request.path.split("/")[1].removesuffix("-logs")


@logs.route("/food-logs", methods=["GET", "POST"])
@logs.route("/activity-logs", methods=["GET", "POST"])
@logs.route("/sleep-logs", methods=["GET", "POST"])
@login_required()
def collection():
    kind = kind_for_request()
    setting = LOG_TYPES[kind]
    if request.method == "GET":
        rows = read_items(kind)
        return {"items": to_json(rows)}
    data = payload()
    checked = checked_values(kind, data)
    lock_account()
    values = stored_values(kind, checked)
    conflict = activity_conflict(kind, values, data)
    if conflict:
        return conflict
    columns = list(values)
    sql = "INSERT INTO " + setting["table"] + " (" + ", ".join(columns) + ") VALUES (" + ", ".join(["%s"] * len(columns)) + ")"
    log_id, _ = execute(sql, tuple(values.values()))
    save_weight(kind, values)
    get_db().commit()
    response = {"message": "Record saved", "id": log_id}
    if kind == 'food':
        response['eating_event_id'] = values['eating_event_id']
    return response, 201


@logs.route("/food-logs/<int:log_id>", methods=["PUT", "DELETE"])
@logs.route("/activity-logs/<int:log_id>", methods=["PUT", "DELETE"])
@logs.route("/sleep-logs/<int:log_id>", methods=["PUT", "DELETE"])
@login_required()
def record(log_id):
    kind = kind_for_request()
    setting = LOG_TYPES[kind]
    # Lock the account before reading ownership or meal state. This also makes
    # overlap checks and empty-meal cleanup consistent across concurrent saves.
    lock_account()
    old = read_items(kind, log_id)
    if not old:
        return {"error": "Record not found"}, 404
    primary_key = setting['key'].split('.')[-1]
    where = ' WHERE ' + primary_key + ' = %s'
    fetch_one('SELECT ' + primary_key + ' FROM ' + setting['table'] + where + ' FOR UPDATE', (log_id,))
    if request.method == "DELETE":
        execute("DELETE FROM " + setting["table"] + where, (log_id,))
        message = "Record deleted"
    else:
        data = payload()
        values = stored_values(kind, checked_values(kind, data), old=old)
        conflict = activity_conflict(kind, values, data, log_id)
        if conflict:
            return conflict
        execute("UPDATE " + setting["table"] + " SET " + ", ".join(key + " = %s" for key in values) + where,
                (*values.values(), log_id))
        save_weight(kind, values)
        message = "Record updated"
    if kind == 'food':
        remove_empty_meal(old['eating_event_id'])
    get_db().commit()
    return {"message": message}


def activity_conflict(kind, values, data, log_id=0):
    if kind != 'activity':
        return None
    overlap = fetch_one('''SELECT activity_event_id FROM activity_events
        WHERE user_id=%s AND activity_event_id<>%s
        AND time_started < %s AND time_finished > %s LIMIT 1''',
        (g.user['user_id'], log_id, values['time_finished'], values['time_started']))
    if overlap and data.get('confirm_overlap') is not True:
        return {"error": "This activity overlaps a saved activity. Keep it anyway?",
                "confirmation_required": "overlap"}, 409
    return None


def lock_account():
    fetch_one('SELECT user_id FROM users WHERE user_id=%s FOR UPDATE', (g.user['user_id'],))


def save_weight(kind, values):
    if kind == 'activity' and values['body_weight_kg'] is not None:
        execute('''INSERT INTO user_profiles (user_id, weight_kg) VALUES (%s,%s)
            ON DUPLICATE KEY UPDATE weight_kg=VALUES(weight_kg), updated_at=UTC_TIMESTAMP(6)''',
            (g.user['user_id'], values['body_weight_kg']))


@logs.get('/food-search')
@login_required()
def food_search():
    query = text(request.args, 'q', 100)
    if len(query) < 2:
        raise ValueError('Enter at least two letters to search')
    try:
        items, source = search_foods(query)
    except FoodServiceUnavailable:
        return {'error': 'Food search is unavailable. Try again or enter nutrition manually.'}, 503
    return {'items': to_json(items), 'source': source}


@logs.post('/food-preview')
@logs.post('/activity-preview')
@login_required()
def preview():
    kind = 'food' if request.path == '/food-preview' else 'activity'
    values = checked_values(kind, payload())
    if kind == 'activity':
        values = stored_values(kind, values)
    return {'item': to_json(values)}


@logs.post('/meals')
@login_required()
def save_meal():
    data = payload()
    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 50 or any(not isinstance(item, dict) for item in items):
        raise ValueError('Add between 1 and 50 foods before saving a meal')
    # Validate the entire draft before making any changes; commit only once.
    metadata = {key: data.get(key) for key in ('eating_event_id', 'meal_type', 'logged_at', 'meal_notes')}
    checked = [checked_values('food', {**item, **metadata}) for item in items]
    lock_account()
    ids = []
    event_id = checked[0]['eating_event_id']
    for item in checked:
        item['eating_event_id'] = event_id
        values = stored_values('food', item)
        event_id = values['eating_event_id']
        log_id, _ = execute('INSERT INTO food_entries (' + ','.join(values) + ') VALUES (' +
                            ','.join(['%s'] * len(values)) + ')', tuple(values.values()))
        ids.append(log_id)
    get_db().commit()
    return {'message': 'Meal logged successfully', 'eating_event_id': event_id, 'food_log_ids': ids}, 201


@logs.get('/food-logs/summary')
@logs.get('/activity-logs/summary')
@login_required()
def summary():
    start = date_time(request.args, 'start', required=True)
    end = date_time(request.args, 'end', required=True)
    if end <= start or (end - start).total_seconds() > 366 * 86400:
        raise ValueError('Choose a time range of up to 366 days')
    args = (g.user['user_id'], start, end)
    if request.path.startswith('/food'):
        aggregates = ','.join('SUM(f.' + key + ') AS ' + key + ',COUNT(f.' + key + ') AS ' + key + '_entered'
                              for key in ('calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g'))
        row = fetch_one('SELECT COUNT(*) AS entries,' + aggregates + ''' FROM food_entries f
            JOIN eating_events e ON e.eating_event_id=f.eating_event_id
            WHERE e.user_id=%s AND e.event_datetime>=%s AND e.event_datetime<%s''', args)
    else:
        row = fetch_one('''SELECT COUNT(*) AS entries,
            SUM(TIMESTAMPDIFF(MICROSECOND,time_started,time_finished)/60000000) AS duration_minutes,
            SUM(calories_burned) AS calories_burned, COUNT(calories_burned) AS calories_burned_entered
            FROM activity_events WHERE user_id=%s AND time_started>=%s AND time_started<%s''', args)
    profile = fetch_one('SELECT daily_calorie_target, weekly_activity_minutes FROM user_profiles WHERE user_id=%s',
                        (g.user['user_id'],))
    return {'totals': to_json(row), 'goals': to_json(profile or {})}


@logs.post('/logging-goal')
@login_required()
def save_goal():
    data = payload()
    key = data.get('kind')
    column = {'food': 'daily_calorie_target', 'activity': 'weekly_activity_minutes'}.get(key) if isinstance(key, str) else None
    if not column:
        raise ValueError('Choose food or activity goal')
    value = number(data, 'target', positive=True, optional=True)
    lock_account()
    execute('INSERT INTO user_profiles (user_id,' + column + ') VALUES (%s,%s) ON DUPLICATE KEY UPDATE ' +
            column + '=VALUES(' + column + '),updated_at=UTC_TIMESTAMP(6)', (g.user['user_id'], value))
    get_db().commit()
    return {'message': 'Goal saved'}
