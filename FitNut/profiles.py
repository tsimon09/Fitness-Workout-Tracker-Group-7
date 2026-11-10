"""Save profile details and food restrictions."""
from flask import Blueprint, g, render_template, request

from accounts import login_required
from db import execute, fetch_all, fetch_one, get_db, to_json
from validation import number, payload

profiles = Blueprint('profiles', __name__)

ALLERGENS = {
    'milk': 'Milk', 'egg': 'Egg', 'peanut': 'Peanut', 'tree_nuts': 'Tree nuts',
    'soy': 'Soy', 'wheat': 'Wheat', 'fish': 'Fish', 'shellfish': 'Shellfish', 'sesame': 'Sesame',
}
GOALS = {'maintain': 'Maintain weight', 'lose_weight': 'Lose weight',
         'gain_weight': 'Gain weight', 'gain_muscle': 'Build muscle', 'improve_fitness': 'Improve fitness'}
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
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError(key.replace('_', ' ').capitalize() + ' must be a list of up to 100 items')
    labels = []
    seen = set()
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise ValueError('Enter a name for each restriction')
        label = ' '.join(item.split())
        if len(label) > 100:
            raise ValueError('Restriction names must be 100 characters or less')
        if label.casefold() not in seen:
            labels.append(label)
            seen.add(label.casefold())
    return labels


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
    if not isinstance(known, list) or len(known) > len(ALLERGENS):
        raise ValueError('Choose allergies from the list or use the other allergies field')
    for code in known:
        if not isinstance(code, str) or code not in ALLERGENS:
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
    if len(known) + len(other) > 100:
        raise ValueError('Enter up to 100 allergies')
    if values['allergy_status'] == 'listed' and not (known or other):
        raise ValueError('Select an allergy or enter one under other allergies')
    if values['allergy_status'] != 'listed' and (known or other):
        raise ValueError('Choose listed allergies to save the allergies you entered')
    restrictions = [('allergy', code, ALLERGENS[code]) for code in ALLERGENS if code in known]
    for kind, labels in [('allergy', other), ('intolerance', entries(data, 'intolerances')),
                         ('preference', entries(data, 'preferences'))]:
        for index, label in enumerate(labels, start=1):
            restrictions.append((kind, 'custom-' + str(index), label))
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
    # Logging and profile saves use the same account lock.
    fetch_one('SELECT user_id FROM users WHERE user_id=%s FOR UPDATE', (g.user['user_id'],))
    old, exists = read_profile()
    old.update(data)
    values, restrictions = checked_profile(old)
    execute('''INSERT INTO user_profiles
        (user_id, age, height_cm, weight_kg, fitness_goal, fitness_level,
         dietary_pattern, daily_calorie_target, weekly_activity_minutes, allergy_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
        age=VALUES(age), height_cm=VALUES(height_cm), weight_kg=VALUES(weight_kg),
        fitness_goal=VALUES(fitness_goal), fitness_level=VALUES(fitness_level),
        dietary_pattern=VALUES(dietary_pattern), daily_calorie_target=VALUES(daily_calorie_target),
        weekly_activity_minutes=VALUES(weekly_activity_minutes), allergy_status=VALUES(allergy_status),
        updated_at=UTC_TIMESTAMP(6)''',
        (g.user['user_id'], values['age'], values['height_cm'], values['weight_kg'],
         values['fitness_goal'], values['fitness_level'], values['dietary_pattern'],
         values['daily_calorie_target'], values['weekly_activity_minutes'], values['allergy_status']))
    execute('DELETE FROM user_restrictions WHERE user_id=%s', (g.user['user_id'],))
    for kind, code, label in restrictions:
        execute('INSERT INTO user_restrictions (user_id,kind,code,label) VALUES (%s,%s,%s,%s)',
                (g.user['user_id'], kind, code, label))
    get_db().commit()
    saved, _ = read_profile()
    return {'message': 'Profile saved', 'profile': to_json(saved)}, 200 if exists else 201
