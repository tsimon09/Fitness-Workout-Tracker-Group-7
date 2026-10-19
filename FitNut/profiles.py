"""Profile details and dietary restrictions for the signed-in account."""
import hashlib

from flask import Blueprint, g, render_template, request

from accounts import login_required
from db import execute, fetch_all, fetch_one, get_db, to_json
from validation import number, payload, text

profiles = Blueprint('profiles', __name__)

ALLERGENS = {
    'milk': 'Milk', 'egg': 'Egg', 'peanut': 'Peanut', 'tree_nuts': 'Tree nuts',
    'soy': 'Soy', 'wheat': 'Wheat', 'fish': 'Fish', 'shellfish': 'Shellfish', 'sesame': 'Sesame',
}
GOALS = {'maintain': 'Maintain weight', 'lose_weight': 'Lose weight',
         'gain_muscle': 'Build muscle', 'improve_fitness': 'Improve fitness'}
LEVELS = {'beginner': 'Beginner', 'intermediate': 'Intermediate', 'advanced': 'Advanced'}
DIETS = {'no_preference': 'No preference', 'vegetarian': 'Vegetarian',
         'vegan': 'Vegan', 'pescatarian': 'Pescatarian'}
PROFILE_COLUMNS = ('age', 'height_cm', 'weight_kg', 'fitness_goal', 'fitness_level', 'dietary_pattern',
                   'daily_calorie_target', 'weekly_activity_minutes', 'allergy_status')
LIST_FIELDS = ('allergens', 'other_allergies', 'intolerances', 'preferences')


def read_profile():
    row = fetch_one('SELECT * FROM user_profiles WHERE user_id=%s', (g.user['user_id'],))
    values = {key: None for key in PROFILE_COLUMNS}
    values['allergy_status'] = 'not_provided'
    values.update({key: [] for key in LIST_FIELDS})
    if row:
        values.update(row)
    for item in fetch_all('''SELECT kind, code, label FROM user_restrictions
        WHERE user_id=%s ORDER BY kind, label''', (g.user['user_id'],)):
        if item['kind'] == 'allergy':
            if item['code'] in ALLERGENS:
                values['allergens'].append(item['code'])
            else:
                values['other_allergies'].append(item['label'])
        else:
            key = 'intolerances' if item['kind'] == 'intolerance' else 'preferences'
            values[key].append(item['label'])
    return values, row is not None


def choice(data, key, options):
    value = data.get(key)
    if value in (None, ''):
        return None
    if not isinstance(value, str) or value not in options:
        raise ValueError('Choose a valid ' + key.replace('_', ' '))
    return value


def entries(data, key):
    items = data.get(key, [])
    if not isinstance(items, list) or len(items) > 20:
        raise ValueError(key.replace('_', ' ').capitalize() + ' must be a list of up to 20 items')
    unique = {}
    for item in items:
        label = ' '.join(text({'restriction': item}, 'restriction', 100).split())
        unique.setdefault(label.casefold(), label)
    return list(unique.values())


def checked_profile(data):
    values = {
        'age': number(data, 'age', positive=True, optional=True, maximum='120', places=0),
        'height_cm': number(data, 'height_cm', positive=True, optional=True, maximum='300'),
        'weight_kg': number(data, 'weight_kg', positive=True, optional=True, maximum='999.99'),
        'fitness_goal': choice(data, 'fitness_goal', GOALS),
        'fitness_level': choice(data, 'fitness_level', LEVELS),
        'dietary_pattern': choice(data, 'dietary_pattern', DIETS),
        'daily_calorie_target': number(data, 'daily_calorie_target', positive=True, optional=True),
        'weekly_activity_minutes': number(data, 'weekly_activity_minutes', positive=True, optional=True),
        'allergy_status': data.get('allergy_status'),
    }
    if values['age'] is not None:
        values['age'] = int(values['age'])
    if values['allergy_status'] not in ('not_provided', 'none_reported', 'listed'):
        raise ValueError('Choose whether allergies are not provided, none reported, or listed')
    known = data.get('allergens', [])
    if not isinstance(known, list) or len(known) > len(ALLERGENS) or any(
            not isinstance(code, str) or code not in ALLERGENS for code in known):
        raise ValueError('Choose allergies from the list or use the other allergies field')
    known = set(known)
    aliases = {value.casefold(): code for code, value in ALLERGENS.items()}
    aliases.update({code: code for code in ALLERGENS})
    other = []
    for label in entries(data, 'other_allergies'):
        code = aliases.get(label.casefold())
        if code:
            known.add(code)
        else:
            other.append(label)
    if len(known) + len(other) > 20:
        raise ValueError('Enter up to 20 allergies')
    if values['allergy_status'] == 'listed' and not (known or other):
        raise ValueError('Select an allergy or enter one under other allergies')
    if values['allergy_status'] != 'listed' and (known or other):
        raise ValueError('Choose listed allergies to save the allergies you entered')
    restrictions = [('allergy', code, ALLERGENS[code]) for code in ALLERGENS if code in known]
    for kind, labels in [('allergy', other), ('intolerance', entries(data, 'intolerances')),
                         ('preference', entries(data, 'preferences'))]:
        for label in labels:
            # Stable codes keep custom labels distinct without treating them as
            # verified allergen mappings for a future planner.
            code = 'custom-' + hashlib.sha256(label.casefold().encode()).hexdigest()
            restrictions.append((kind, code, label))
    return values, restrictions


@profiles.get('/profile')
@login_required(html=True)
def profile_page():
    values, _ = read_profile()
    return render_template('profile.html', profile=values, allergens=ALLERGENS,
                           goals=GOALS, levels=LEVELS, diets=DIETS)


@profiles.route('/profile-data', methods=['GET', 'POST'])
@login_required()
def profile_data():
    if request.method == 'GET':
        values, exists = read_profile()
        return {'profile': to_json(values), 'exists': exists}
    data = payload()
    if set(data) - set(PROFILE_COLUMNS) - set(LIST_FIELDS):
        raise ValueError('Send only profile fields')
    # Match the logging routes' lock so profile saves and weight/goal updates
    # cannot overwrite one another from stale reads.
    fetch_one('SELECT user_id FROM users WHERE user_id=%s FOR UPDATE', (g.user['user_id'],))
    old, exists = read_profile()
    values, restrictions = checked_profile({**old, **data})
    columns = list(values)
    execute('INSERT INTO user_profiles (user_id,' + ','.join(columns) + ') VALUES (' +
            ','.join(['%s'] * (len(columns) + 1)) + ') ON DUPLICATE KEY UPDATE ' +
            ','.join(key + '=VALUES(' + key + ')' for key in columns) + ',updated_at=UTC_TIMESTAMP(6)',
            (g.user['user_id'], *values.values()))
    execute('DELETE FROM user_restrictions WHERE user_id=%s', (g.user['user_id'],))
    for kind, code, label in restrictions:
        execute('INSERT INTO user_restrictions (user_id,kind,code,label) VALUES (%s,%s,%s,%s)',
                (g.user['user_id'], kind, code, label))
    get_db().commit()
    saved, _ = read_profile()
    return {'message': 'Profile saved', 'profile': to_json(saved)}, 200 if exists else 201
