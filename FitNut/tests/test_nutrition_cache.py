"""Cached search stays usable when the external nutrition service is unavailable."""
import unittest
from unittest.mock import patch
from nutrition import search_foods, FoodServiceUnavailable


class CachedFoodSearchTests(unittest.TestCase):
    def test_search_words_match_names_with_punctuation_without_interpolating_input(self):
        with patch('nutrition.usda_search', side_effect=FoodServiceUnavailable()), patch('nutrition.fetch_all', return_value=[{'food_name': 'Bananas, raw'}]) as lookup:
            foods, source = search_foods('Bananas raw')
        self.assertEqual(source, 'cached')
        self.assertEqual(foods[0]['food_name'], 'Bananas, raw')
        sql, values = lookup.call_args.args
        self.assertIn('food_name LIKE %s AND food_name LIKE %s', sql)
        self.assertEqual(values, ('%Bananas%', '%raw%'))
        self.assertNotIn('Bananas', sql)
