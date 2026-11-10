"""Evidence checks and arithmetic for Almond. A model never supplies trusted totals."""
import copy
import math
import re
from decimal import Decimal, ROUND_HALF_UP


class EvidenceError(ValueError):
    pass


NUTRIENTS = ('calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g')
ALIASES = {
    'milk': ('milk', 'dairy', 'whey', 'casein', 'butter', 'cream', 'cheese', 'yogurt'),
    'egg': ('egg', 'eggs', 'albumen', 'mayonnaise'),
    'peanut': ('peanut', 'peanuts', 'groundnut'),
    'tree_nuts': ('almond', 'cashew', 'walnut', 'pecan', 'pistachio', 'hazelnut', 'macadamia', 'brazil nut'),
    'soy': ('soy', 'soya', 'soybean', 'soy bean', 'tofu', 'edamame'),
    'wheat': ('wheat', 'semolina', 'bulgur', 'couscous', 'spelt'),
    'fish': ('fish', 'salmon', 'tuna', 'cod', 'anchovy'),
    'shellfish': ('shellfish', 'shrimp', 'prawn', 'crab', 'lobster', 'oyster', 'clam', 'mussel', 'scallop'),
    'sesame': ('sesame', 'tahini'),
    'lactose': ('milk', 'dairy', 'whey', 'cream', 'cheese', 'yogurt', 'lactose'),
    'oats': ('oat', 'oats', 'oatmeal'),
    'oatmeal': ('oat', 'oats', 'oatmeal'),
    'cocoa': ('cocoa', 'cacao', 'chocolate'),
}


def words_match(term, text):
    return bool(re.search(r'(?<!\w)' + re.escape(term.casefold()) + r'(?:s)?(?!\w)', text.casefold()))


def restriction_terms(profile):
    terms = list(profile.get('allergens') or []) + list(profile.get('other_allergies') or [])
    terms += list(profile.get('intolerances') or []) + list(profile.get('temporary_restrictions') or [])
    for preference in profile.get('preferences') or []:
        match = re.match(r'^(?:no|avoid|exclude)\s+(.+)$', preference, re.I)
        if match:
            terms.append(match.group(1).strip())
    return sorted(set(str(term).strip().casefold() for term in terms if str(term).strip()))


def validate_recipe(recipe, catalog, profile):
    if profile.get('allergy_status') not in ('none_reported', 'listed'):
        raise EvidenceError('Set your allergy status in Profile before requesting a checked meal.')
    if not isinstance(recipe, dict):
        raise EvidenceError('The meal response must be an object.')
    title = recipe.get('title')
    foods = recipe.get('foods')
    instructions = recipe.get('instructions')
    if not isinstance(title, str) or not title.strip() or len(title) > 150:
        raise EvidenceError('The meal needs a short title.')
    if not isinstance(foods, list) or not 1 <= len(foods) <= 20:
        raise EvidenceError('The meal must contain 1–20 foods.')
    if not isinstance(instructions, list) or not 1 <= len(instructions) <= 12 or any(
            not isinstance(step, str) or not step.strip() or len(step) > 1000 for step in instructions):
        raise EvidenceError('The meal needs clear cooking instructions.')
    substitutions = recipe.get('substitutions', [])
    if not isinstance(substitutions, list) or len(substitutions) > 20 or any(
            not isinstance(value, str) or len(value) > 500 for value in substitutions):
        raise EvidenceError('Invalid substitution explanation.')
    prose = ' '.join([title, *instructions, *substitutions]).casefold()
    if re.search(r'(allergen[- ]free|guaranteed safe|safe for (?:your|all)|nutritionally complete|meets all.*needs|cures?\b)', prose):
        raise EvidenceError('Unsupported safety or nutritional-completeness claim.')
    terms = restriction_terms(profile)
    seen, selected, evidence = set(), [], set()
    totals = {name: Decimal(0) for name in NUTRIENTS}
    for item in foods:
        if not isinstance(item, dict):
            raise EvidenceError('Invalid ingredient.')
        food_id = item.get('food_id')
        if isinstance(food_id, bool) or not isinstance(food_id, int) or food_id in seen:
            raise EvidenceError('Ingredient IDs must be distinct catalog IDs.')
        food = catalog.get(food_id)
        if food is None:
            raise EvidenceError('An ingredient is missing from the retrieved evidence.')
        seen.add(food_id)
        grams = item.get('grams')
        if isinstance(grams, bool) or not isinstance(grams, (int, float, Decimal)) or not math.isfinite(float(grams)) or not 0 < grams <= 2000:
            raise EvidenceError('Each ingredient needs a finite quantity between 0 and 2000 grams.')
        if not food.get('evidence_complete') or not food.get('evidence_id') or not food.get('source_url'):
            raise EvidenceError('Ingredient composition has not been reviewed: ' + food['food_name'])
        labels = food.get('ingredients')
        allergens = food.get('allergens')
        coverage = food.get('restriction_coverage', [])
        if not isinstance(coverage, list) or any(not isinstance(value, str) for value in coverage):
            raise EvidenceError('Custom restriction coverage must be a reviewed list of names.')
        if not isinstance(labels, list) or not labels or not isinstance(allergens, list):
            raise EvidenceError('Incomplete ingredient evidence.')
        if any(not isinstance(label, str) for label in labels + allergens):
            raise EvidenceError('Ingredient evidence must use named ingredients.')
        if not str(food['source_url']).startswith('https://'):
            raise EvidenceError('Evidence needs an HTTPS source.')
        if len(labels) == 1:
            # A reviewed single-food record cannot silently change into a different food.
            name_words = set(re.findall(r'\w+', food['food_name'].split(',')[0].casefold()))
            ingredient_words = set(re.findall(r'\w+', labels[0].casefold()))
            normalize = lambda values: {word.rstrip('s') for word in values}
            if not normalize(name_words) & normalize(ingredient_words):
                raise EvidenceError('Food identity contradicts its ingredient evidence.')
        ingredient_text = ' '.join(labels).casefold()
        canonical_labels = {str(value).casefold().replace(' ', '_').rstrip('s') for value in allergens}
        for group in ('milk', 'egg', 'peanut', 'tree_nuts', 'soy', 'wheat', 'fish', 'shellfish', 'sesame'):
            if any(words_match(alias, ingredient_text) for alias in ALIASES[group]):
                if group.rstrip('s') not in canonical_labels:
                    raise EvidenceError('Ingredient evidence omits a declared allergen relationship: ' + group)
        haystack = ' '.join([food['food_name'], *labels, *allergens]).casefold()
        for term in terms:
            aliases = ALIASES.get(term, (term,))
            if term in [str(a).casefold() for a in allergens] or any(words_match(alias, haystack) for alias in aliases):
                raise EvidenceError('Restriction conflict: ' + term + ' in ' + food['food_name'])
            # An alias table cannot establish absence of an arbitrary custom ingredient.
            if term not in ALIASES and term not in coverage:
                raise EvidenceError('No reviewed evidence for custom restriction: ' + term)
        diet = profile.get('dietary_pattern')
        if diet and diet != 'no_preference' and diet not in food.get('dietary_tags', []):
            raise EvidenceError('Dietary pattern has not been verified for ' + food['food_name'])
        for name in NUTRIENTS:
            value = food.get(name)
            if value is None or totals[name] is None:
                totals[name] = None
            else:
                number = Decimal(str(value))
                if not number.is_finite() or number < 0:
                    raise EvidenceError('Invalid nutrient evidence.')
                totals[name] += number * Decimal(str(grams)) / 100
        evidence.add(str(food['evidence_id']))
        selected.append({**copy.deepcopy(food), 'grams': float(grams)})
    supplied = recipe.get('evidence_ids')
    if not isinstance(supplied, list) or any(not isinstance(value, str) for value in supplied) or set(supplied) != evidence:
        raise EvidenceError('Evidence references must match every selected food.')
    # All generated prose is checked, not just the ingredient list.
    for term in terms:
        if any(words_match(alias, prose) for alias in ALIASES.get(term, (term,))):
            raise EvidenceError('Recipe text mentions a restricted ingredient: ' + term)
    selected_words = ' '.join(' '.join([f['food_name'], *f['ingredients']]) for f in selected)
    named_foods = set(value for values in ALIASES.values() for value in values)
    named_foods.update(('apple', 'rice', 'oats', 'chicken', 'beef', 'pork', 'gelatin', 'broth', 'honey',
        'carrot', 'potato', 'tomato', 'onion', 'garlic', 'olive oil', 'coconut', 'pepper', 'salt',
        'mushroom', 'lentil', 'bean', 'chickpea', 'quinoa', 'spinach', 'broccoli', 'banana', 'bread', 'pasta'))
    for ingredient in named_foods:
        if words_match(ingredient, ' '.join(instructions)) and not words_match(ingredient, selected_words):
            raise EvidenceError('Cooking instructions add an unselected ingredient: ' + ingredient)
    for identifier, other in catalog.items():
        if identifier in seen:
            continue
        for ingredient in other.get('ingredients', []):
            if words_match(ingredient, ' '.join(instructions)) and not words_match(ingredient, selected_words):
                raise EvidenceError('Cooking instructions add an unselected ingredient: ' + ingredient)
    return {'title': title.strip(), 'foods': selected, 'instructions': instructions,
            'substitutions': substitutions, 'evidence_ids': sorted(evidence),
            'nutrition': {key: None if value is None else float(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)) for key, value in totals.items()},
            'evidence_status': 'checked_ingredients',
            'note': 'Ingredient records checked against your restrictions. Verify current product labels and preparation cross-contact.'}
