"""Read and save the combined meal, food, activity, and sleep tables."""
from datetime import timedelta
from flask import g
from db import execute, fetch_all, fetch_one

LOG_TYPES = {
    'food': {'table': 'food_entries', 'id': 'food_log_id', 'key': 'f.food_entry_id', 'date': 'logged_at', 'title': 'Food'},
    'activity': {'table': 'activity_events', 'id': 'activity_log_id', 'key': 'a.activity_event_id', 'date': 'performed_at', 'title': 'Activity'},
    'sleep': {'table': 'sleep_logs', 'id': 'sleep_log_id', 'key': 'sleep_log_id', 'date': 'sleep_start', 'title': 'Sleep'},
}
READ_SQL = {
    'food': '''SELECT f.food_entry_id AS food_log_id, e.user_id, f.food_name, f.quantity,
        u.unit_name AS quantity_unit, m.meal_type, e.event_datetime AS logged_at,
        f.calories, f.protein_g, f.carbs_g, f.fat_g, f.fiber_g, f.created_at,
        e.eating_event_id, e.comments AS meal_notes
        FROM food_entries f JOIN eating_events e ON e.eating_event_id = f.eating_event_id
        JOIN meal_types m ON m.meal_type_id = e.meal_type_id
        JOIN units_of_measure u ON u.unit_id = f.unit_id WHERE e.user_id = %s''',
    'activity': '''SELECT a.activity_event_id AS activity_log_id, a.user_id,
        COALESCE(a.custom_activity_name, t.activity_name) AS activity_name, a.time_started AS performed_at, a.time_finished,
        ROUND(TIMESTAMPDIFF(MICROSECOND, a.time_started, a.time_finished) / 60000000, 2) AS duration_minutes,
        a.calories_burned, a.notes, a.created_at FROM activity_events a
        JOIN activity_types t ON t.activity_type_id = a.activity_type_id WHERE a.user_id = %s''',
    'sleep': 'SELECT * FROM sleep_logs WHERE user_id = %s',
}


def read_items(kind, log_id=None):
    sql, args = READ_SQL[kind], [g.user['user_id']]
    if log_id is not None:
        return fetch_one(sql + ' AND ' + LOG_TYPES[kind]['key'] + ' = %s', (*args, log_id))
    return fetch_all(sql + ' ORDER BY ' + LOG_TYPES[kind]['date'] + ' DESC LIMIT 100', args)


def count_items(kind):
    return fetch_one('SELECT COUNT(*) AS total FROM (' + READ_SQL[kind] + ') owned', (g.user['user_id'],))['total']


def lookup_id(kind, name):
    table, key, column = {
        'activity': ('activity_types', 'activity_type_id', 'activity_name'),
        'unit': ('units_of_measure', 'unit_id', 'unit_name'),
    }[kind]
    execute('INSERT INTO ' + table + ' (' + column + ') VALUES (%s) ON DUPLICATE KEY UPDATE ' + column + '=' + column, (name,))
    return fetch_one('SELECT ' + key + ' FROM ' + table + ' WHERE ' + column + ' = %s', (name,))[key]


def stored_values(kind, values):
    if kind == 'food':
        event_id = values.pop('eating_event_id')
        if event_id:
            if not fetch_one('SELECT eating_event_id FROM eating_events WHERE eating_event_id = %s AND user_id = %s',
                             (event_id, g.user['user_id'])):
                raise ValueError('Meal not found in your account')
        else:
            meal = fetch_one('SELECT meal_type_id FROM meal_types WHERE meal_type = %s', (values['meal_type'],))
            execute('''INSERT INTO eating_events (user_id, meal_type_id, event_datetime, comments)
                VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE eating_event_id=eating_event_id''',
                (g.user['user_id'], meal['meal_type_id'], values['logged_at'], values['meal_notes']))
            event_id = fetch_one('SELECT eating_event_id FROM eating_events WHERE user_id=%s AND meal_type_id=%s AND event_datetime=%s',
                                 (g.user['user_id'], meal['meal_type_id'], values['logged_at']))['eating_event_id']
        return {'eating_event_id': event_id, 'unit_id': lookup_id('unit', values['quantity_unit']),
                **{key: values[key] for key in ('food_name', 'quantity', 'calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g')}}
    if kind == 'activity':
        start = values['performed_at']
        try:
            end = start + timedelta(minutes=float(values['duration_minutes']))
        except OverflowError:
            raise ValueError('Activity duration is too long')
        activity = fetch_one('SELECT activity_type_id FROM activity_types WHERE activity_name=%s', (values['activity_name'],))
        fallback = fetch_one("SELECT activity_type_id FROM activity_types WHERE activity_name='Other'")
        return {'user_id': g.user['user_id'], 'activity_type_id': (activity or fallback)['activity_type_id'],
                'custom_activity_name': None if activity else values['activity_name'],
                'time_started': start, 'time_finished': end, 'calories_burned': values['calories_burned'], 'notes': values['notes']}
    return {'user_id': g.user['user_id'], **values}


def remove_empty_meal(event_id):
    execute('''DELETE FROM eating_events WHERE eating_event_id=%s AND user_id=%s
        AND NOT EXISTS (SELECT 1 FROM food_entries WHERE eating_event_id=%s)''',
        (event_id, g.user['user_id'], event_id))


def meal_choices():
    return fetch_all('''SELECT e.eating_event_id, e.event_datetime, m.meal_type FROM eating_events e
        JOIN meal_types m ON m.meal_type_id=e.meal_type_id WHERE e.user_id=%s
        ORDER BY e.event_datetime DESC LIMIT 100''', (g.user['user_id'],))
