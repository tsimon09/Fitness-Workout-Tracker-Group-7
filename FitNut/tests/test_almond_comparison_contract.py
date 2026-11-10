"""Offline contracts for the intensive proposal-comparison helpers."""
import unittest
from decimal import Decimal

from almond_gateway import GatewayError, cost_upper_bound
from almond_evidence import validate_recipe
from scripts.compare_almond_methods import preserves_proposal
from scripts.intensive_almond_comparison import MODES, check_answer, probability


def make_catalog():
    return {
        101: {'food_id': 101, 'food_name': 'Almonds, raw', 'ingredients': ['almonds'],
              'allergens': ['tree nut'], 'evidence_complete': True, 'evidence_id': 'almond-ref',
              'source_url': 'https://example.test/almond', 'calories': 583.6, 'protein_g': 21.45,
              'carbs_g': 20.035, 'fat_g': 51.09, 'fiber_g': 12.5,
              'dietary_tags': ['vegan', 'vegetarian']},
        102: {'food_id': 102, 'food_name': 'Apples, raw, with skin', 'ingredients': ['apple'],
              'allergens': [], 'evidence_complete': True, 'evidence_id': 'apple-ref',
              'source_url': 'https://example.test/apple', 'calories': 52, 'protein_g': 0.26,
              'carbs_g': 13.81, 'fat_g': 0.17, 'fiber_g': 2.4,
              'dietary_tags': ['vegan', 'vegetarian']},
        103: {'food_id': 103, 'food_name': 'Oats, whole grain, rolled', 'ingredients': ['oats'],
              'allergens': [], 'evidence_complete': True, 'evidence_id': 'oat-ref',
              'source_url': 'https://example.test/oats', 'calories': 378.87, 'protein_g': 13.5,
              'carbs_g': 68.66, 'fat_g': 5.89, 'fiber_g': None,
              'dietary_tags': ['vegan', 'vegetarian']},
    }


def no_restrictions():
    return {'allergy_status': 'none_reported', 'allergens': [], 'other_allergies': [],
            'intolerances': [], 'preferences': [], 'dietary_pattern': 'no_preference'}


class ProposalPreservationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = make_catalog()
        self.original = {'title': 'Almond oats',
                         'foods': [{'food_id': 103, 'grams': 52}, {'food_id': 101, 'grams': 18}],
                         'instructions': ['Combine the selected foods.'], 'substitutions': [],
                         'evidence_ids': ['almond-ref', 'oat-ref']}

    def test_fixed_proposal_accepts_reordering_and_equivalent_aggregate_quantities(self):
        answer = {'foods': [{'food_id': 101, 'grams': '18.0'},
                            {'food_id': 103, 'grams': 20}, {'food_id': 103, 'grams': 32}]}
        self.assertTrue(preserves_proposal(answer, self.original))

    def test_check_answer_blocks_substitution_addition_removal_and_quantity_drift(self):
        variants = (
            {'title': 'Apple oats', 'foods': [{'food_id': 102, 'grams': 52}, {'food_id': 101, 'grams': 18}],
             'instructions': ['Combine apples and almonds.'], 'substitutions': [], 'evidence_ids': ['apple-ref', 'almond-ref']},
            {'title': 'Almond oats', 'foods': [{'food_id': 103, 'grams': 52}, {'food_id': 101, 'grams': 18},
             {'food_id': 102, 'grams': 5}], 'instructions': ['Combine the selected foods.'],
             'substitutions': [], 'evidence_ids': ['almond-ref', 'oat-ref', 'apple-ref']},
            {'title': 'Almond oats', 'foods': [{'food_id': 101, 'grams': 18}],
             'instructions': ['Serve almonds.'], 'substitutions': [], 'evidence_ids': ['almond-ref']},
            {'title': 'Almond oats', 'foods': [{'food_id': 103, 'grams': 51}, {'food_id': 101, 'grams': 18}],
             'instructions': ['Combine the selected foods.'], 'substitutions': [], 'evidence_ids': ['almond-ref', 'oat-ref']},
        )
        for answer in variants:
            with self.subTest(answer=answer):
                self.assertIsNotNone(check_answer(answer, self.original, self.catalog, no_restrictions()))

    def test_valid_recipe_preserves_original_ids_and_quantities(self):
        answer = {'title': 'Almond oats',
                  'foods': [{'food_id': 103, 'grams': 52}, {'food_id': 101, 'grams': 18}],
                  'instructions': ['Cook the oats, then top with almonds.'], 'substitutions': [],
                  'evidence_ids': ['oat-ref', 'almond-ref']}
        self.assertIsNone(check_answer(answer, self.original, self.catalog, no_restrictions()))

    def test_missing_allergy_status_and_malformed_answers_fail_closed(self):
        answer = {'title': 'Oats', 'foods': [{'food_id': 103, 'grams': 52}],
                  'instructions': ['Cook the oats.'], 'substitutions': [], 'evidence_ids': ['oat-ref']}
        profile = {**no_restrictions(), 'allergy_status': 'not_provided'}
        self.assertIsNotNone(check_answer(answer, self.original, self.catalog, profile))
        for malformed in (None, [], {}, {'clarification': ''}, {'foods': 'not a list'}):
            with self.subTest(answer=malformed):
                self.assertIsNotNone(check_answer(malformed, self.original, self.catalog, no_restrictions()))


class JevProbabilityTests(unittest.TestCase):
    def test_reads_only_a_typed_noul_probability(self):
        self.assertEqual(probability({'answers': {'supported': {'type': 'noul', 'noul': 0.97}}}, 'supported'), 0.97)
        self.assertEqual(probability({'answers': {'supported': {'type': 'noul', 'noul': 0}}}, 'supported'), 0)

    def test_missing_malformed_or_out_of_range_probability_fails_closed(self):
        invalid = (
            None,
            [],
            {},
            {'answers': []},
            {'answers': {}},
            {'answers': {'supported': None}},
            {'answers': {'supported': {'noul': 0.99}}},
            {'answers': {'supported': {'type': 'other', 'noul': 0.99}}},
            {'answers': {'supported': {'type': 'noul', 'noul': '0.99'}}},
            {'answers': {'supported': {'type': 'noul', 'noul': True}}},
            {'answers': {'supported': {'type': 'noul', 'noul': float('nan')}}},
            {'answers': {'supported': {'type': 'noul', 'noul': float('inf')}}},
            {'answers': {'supported': {'type': 'noul', 'noul': float('-inf')}}},
            {'answers': {'supported': {'type': 'noul', 'noul': -0.01}}},
            {'answers': {'supported': {'type': 'noul', 'noul': 1.01}}},
        )
        for response in invalid:
            with self.subTest(response=response):
                with self.assertRaises((GatewayError, AttributeError, TypeError)):
                    probability(response, 'supported')

    def test_jev_call_count_budget_modes_and_cost_ceiling(self):
        self.assertEqual(MODES, ('python_only', 'qwen_judge', 'jev_judge', 'jev_route_judge'))
        one_max_context_decision = cost_upper_bound('typesafe/jev-1.14', 12500, 0)
        self.assertEqual(one_max_context_decision, Decimal('0.000525'))
        self.assertLessEqual(2 * one_max_context_decision, Decimal('2.00'))


if __name__ == '__main__':
    unittest.main()
