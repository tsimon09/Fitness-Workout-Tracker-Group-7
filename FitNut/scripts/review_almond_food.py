"""Import human-reviewed composition evidence for an existing USDA catalog food.

Usage: python -m scripts.review_almond_food reviewed-food.json
The file contains food_id, source_url, evidence_id, ingredients, allergens,
dietary_tags, restriction_coverage and reviewer_notes. No nutrient overrides.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from app import app
from db import execute, fetch_one, get_db
from almond_store import dump


def main(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    identifier = data.get('food_id')
    if isinstance(identifier, bool) or not isinstance(identifier, int):
        raise ValueError('food_id must identify an existing catalog record.')
    if not isinstance(data.get('ingredients'), list) or not data['ingredients'] or any(not isinstance(v, str) or not v.strip() for v in data['ingredients']):
        raise ValueError('List every ingredient and subingredient from the reviewed source.')
    source = urlsplit(data.get('source_url', ''))
    if source.scheme != 'https' or not source.hostname or source.username:
        raise ValueError('Provide the exact HTTPS source reviewed.')
    for field in ('evidence_id', 'reviewer_notes'):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError('Provide ' + field)
    for field in ('allergens', 'dietary_tags', 'restriction_coverage'):
        if not isinstance(data.get(field, []), list) or any(not isinstance(v, str) for v in data.get(field, [])):
            raise ValueError('Invalid ' + field)
    with app.app_context():
        if not fetch_one('SELECT food_id FROM food_catalog WHERE food_id=%s', (identifier,)):
            raise ValueError('Search/import the USDA food record before reviewing it.')
        evidence = {key: data.get(key, []) for key in ('ingredients', 'allergens', 'dietary_tags', 'restriction_coverage')}
        evidence.update({key: data[key] for key in ('source_url', 'evidence_id', 'reviewer_notes')})
        evidence['evidence_complete'] = True
        execute('INSERT INTO almond_food_evidence (food_id,evidence) VALUES (%s,%s) ON DUPLICATE KEY UPDATE evidence=VALUES(evidence),reviewed_at=UTC_TIMESTAMP(6)', (identifier, dump(evidence)))
        get_db().commit()
    print('Reviewed evidence saved. This is not a cross-contact certification.')


if __name__ == '__main__':
    main(sys.argv[1])
