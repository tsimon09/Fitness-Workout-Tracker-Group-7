"""Food, activity, and sleep records belong to the logged-in user."""
from flask import Blueprint, g, request
from accounts import login_required
from db import execute, fetch_all, fetch_one, get_db, to_json
from validation import date_time, number, payload, text
from log_data import LOG_TYPES, read_items, stored_values, remove_empty_meal

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
        return {"food_name": text(data, "food_name", 150),
                "quantity": number(data, "quantity", positive=True, maximum="9999999.999"),
                "quantity_unit": text(data, "quantity_unit", 30), "meal_type": meal,
                "calories": number(data, "calories", optional=True),
                "protein_g": number(data, "protein_g", optional=True),
                "carbs_g": number(data, "carbs_g", optional=True),
                "fat_g": number(data, "fat_g", optional=True), "fiber_g": number(data, "fiber_g", optional=True),
                "logged_at": date_time(data, "logged_at"), "eating_event_id": event_id,
                "meal_notes": text(data, "meal_notes", 2000, required=False)}
    if kind == "activity":
        return {"activity_name": text(data, "activity_name", 100),
                "duration_minutes": number(data, "duration_minutes", positive=True),
                "calories_burned": number(data, "calories_burned", optional=True),
                "performed_at": date_time(data, "performed_at"), "notes": text(data, "notes", 2000, required=False)}
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
    values = stored_values(kind, checked_values(kind, payload()))
    columns = list(values)
    sql = "INSERT INTO " + setting["table"] + " (" + ", ".join(columns) + ") VALUES (" + ", ".join(["%s"] * len(columns)) + ")"
    log_id, _ = execute(sql, tuple(values.values()))
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
    old = read_items(kind, log_id)
    if not old:
        return {"error": "Record not found"}, 404
    # The owned record was checked above; obtain a row lock before changing it.
    primary_key = setting['key'].split('.')[-1]
    where = ' WHERE ' + primary_key + ' = %s'
    fetch_one('SELECT ' + primary_key + ' FROM ' + setting['table'] + where + ' FOR UPDATE', (log_id,))
    if request.method == "DELETE":
        execute("DELETE FROM " + setting["table"] + where, (log_id,))
        message = "Record deleted"
    else:
        values = stored_values(kind, checked_values(kind, payload()))
        execute("UPDATE " + setting["table"] + " SET " + ", ".join(key + " = %s" for key in values) + where,
                (*values.values(), log_id))
        message = "Record updated"
    if kind == 'food':
        remove_empty_meal(old['eating_event_id'])
    get_db().commit()
    return {"message": message}
