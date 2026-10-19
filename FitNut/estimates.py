"""Representative 2024 Adult Compendium METs; user values remain available."""
from decimal import Decimal, ROUND_HALF_UP
from db import fetch_one
from flask import g
from validation import number

# Low/moderate/high are FitNut's mapping to these representative activities.
# Source: https://pacompendium.com/ (walking, running, bicycling, water activities).
METS = {'walking': ('2.8', '3.8', '4.8'), 'running': ('6.5', '8.5', '11.0'),
        'cycling': ('4.0', '8.0', '10.0'), 'swimming': ('5.8', '8.0', '9.8')}


def calculate_activity(data, values):
    source = data.get('calorie_source', 'manual')
    if source not in ('manual', 'estimated'):
        raise ValueError('Choose estimated or manually entered calories')
    weight = number(data, 'body_weight_kg', positive=True, optional=True, maximum='999.99')
    values.update(calorie_source=source, body_weight_kg=weight, met_value=None)
    if source == 'manual':
        return values
    choices = METS.get(values['activity_name'].strip().lower())
    if choices is None:
        raise ValueError('Estimates support Walking, Running, Cycling, or Swimming. For other activities, enter calories manually')
    if weight is None:
        profile = fetch_one('SELECT weight_kg FROM user_profiles WHERE user_id=%s', (g.user['user_id'],))
        weight = profile['weight_kg'] if profile else None
    if weight is None:
        raise ValueError('Enter your body weight in kg to estimate calories')
    met = Decimal(choices[('low', 'moderate', 'high').index(values['intensity'])])
    calories = (met * Decimal('3.5') * weight / 200 * values['duration_minutes']).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    values.update(body_weight_kg=weight, met_value=met,
                  calories_burned=number({'calories_burned': calories}, 'calories_burned'))
    return values
