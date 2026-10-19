"""USDA lookup, with a local cache; saved entries keep nutrition snapshots."""
import json
import os
from decimal import Decimal, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from db import execute, fetch_all, fetch_one, get_db
from validation import number

NUTRIENTS = {'calories': (1008, 'KCAL'), 'protein_g': (1003, 'G'),
             'carbs_g': (1005, 'G'), 'fat_g': (1004, 'G'), 'fiber_g': (1079, 'G')}


class FoodServiceUnavailable(Exception):
    pass


def usda_search(query):
    params = urlencode({'api_key': os.getenv('USDA_API_KEY', 'DEMO_KEY'), 'query': query,
                        'pageSize': 10, 'dataType': 'SR Legacy'})
    # Fixed host and parameters only: users cannot supply an arbitrary URL.
    request = Request('https://api.nal.usda.gov/fdc/v1/foods/search?' + params,
                      headers={'User-Agent': 'FitNut-Sprint3/1.0'})
    try:
        with urlopen(request, timeout=8) as response:
            data = json.loads(response.read(1048576))
        if not isinstance(data, dict) or not isinstance(data.get('foods'), list):
            raise ValueError('Invalid food response')
        return data['foods']
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        # Never expose a URL containing an API key in errors or logs.
        raise FoodServiceUnavailable() from None


def search_foods(query):
    try:
        foods = usda_search(query)
    except FoodServiceUnavailable:
        rows = fetch_all('SELECT * FROM food_catalog WHERE food_name LIKE %s ORDER BY food_name LIMIT 10',
                         ('%' + query.replace('%', '').replace('_', '') + '%',))
        if rows:
            return rows, 'cached'
        raise
    found = []
    for food in foods:
        if not isinstance(food, dict) or not isinstance(food.get('foodNutrients'), list):
            continue
        nutrients = {}
        for name, (nutrient_id, unit) in NUTRIENTS.items():
            value = next((row.get('value') for row in food.get('foodNutrients', [])
                          if isinstance(row, dict) and row.get('nutrientId') == nutrient_id and str(row.get('unitName', '')).upper() == unit), None)
            nutrients[name] = None if value is None else number({name: str(Decimal(str(value)).quantize(Decimal('.01')))}, name)
        if nutrients['calories'] is None or not food.get('description') or not isinstance(food.get('fdcId'), int):
            continue
        execute('''INSERT INTO food_catalog (fdc_id, food_name, calories, protein_g, carbs_g, fat_g, fiber_g)
            VALUES (%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE food_id=food_id''',
            (food['fdcId'], food['description'][:150], *nutrients.values()))
        found.append(fetch_one('SELECT * FROM food_catalog WHERE fdc_id=%s', (food['fdcId'],)))
    get_db().commit()
    return found, 'USDA FoodData Central (SR Legacy)'


def calculate_food(data, values):
    food_id = data.get('food_id')
    values.update(food_id=None, serving_grams=None)
    if food_id in (None, ''):
        return values
    if isinstance(food_id, bool) or not str(food_id).isdigit() or not 0 < int(food_id) <= 2147483647:
        raise ValueError('Choose a food from the search results or use manual entry')
    food = fetch_one('SELECT * FROM food_catalog WHERE food_id=%s', (int(food_id),))
    if not food:
        raise ValueError('Food not found. Search again or use manual entry')
    if values['quantity_unit'] not in ('g', 'serving'):
        raise ValueError('For a searched food, use g or serving and specify grams per serving')
    grams = Decimal(1) if values['quantity_unit'] == 'g' else number(
        data, 'serving_grams', positive=True, maximum='9999999.999', places=3)
    factor = values['quantity'] * grams / 100
    for name in NUTRIENTS:
        total = None if food[name] is None else (food[name] * factor).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        values[name] = number({name: total}, name, optional=True)
    values.update(food_id=food['food_id'], food_name=food['food_name'], serving_grams=grams)
    return values
