"""Offline checks for the benchmark's memory and selection accounting."""
import copy
import unittest

from scripts.practical_almond_comparison import EpisodeState, selection_metrics, select_lexical


class PracticalBenchmarkTests(unittest.TestCase):
    def episode(self):
        return {'initial_profile': {'allergy_status': 'none_reported', 'allergens': [],
            'other_allergies': [], 'intolerances': [], 'preferences': [], 'dietary_pattern': 'no_preference'}}

    def test_unconfirmed_change_applies_to_meal_revisions_without_becoming_durable(self):
        original = self.episode()
        before = copy.deepcopy(original)
        state = EpisodeState(original)
        profile = state.advance({'new_meal': True, 'events': [{'type': 'unconfirmed_add', 'category': 'allergens', 'term': 'milk'}]})
        self.assertEqual(profile['temporary_restrictions'], ['milk'])
        self.assertEqual(state.profile['allergens'], [])
        self.assertEqual(state.advance({'new_meal': False})['temporary_restrictions'], ['milk'])
        self.assertEqual(state.advance({'new_meal': True})['temporary_restrictions'], [])
        self.assertEqual(state.profile['allergens'], [])
        self.assertEqual(original, before)

    def test_confirmed_change_survives_new_meal_and_temporary_change_expires(self):
        state = EpisodeState(self.episode())
        state.advance({'new_meal': True, 'events': [{'type': 'temporary', 'term': 'oats'},
            {'type': 'confirm_add', 'category': 'allergens', 'term': 'milk'}]})
        next_profile = state.advance({'new_meal': True})
        self.assertEqual(next_profile['allergens'], ['milk'])
        self.assertEqual(next_profile['allergy_status'], 'listed')
        self.assertEqual(next_profile['temporary_restrictions'], [])

    def test_allergy_cannot_be_removed_by_a_soft_preference_event(self):
        state = EpisodeState(self.episode())
        with self.assertRaises(ValueError):
            state.advance({'events': [{'type': 'confirm_remove', 'category': 'allergens', 'term': 'milk'}]})

    def test_selected_none_is_not_reported_as_perfect_precision(self):
        items = [{'id': 'useful', 'relevant': True}, {'id': 'noise', 'relevant': False}]
        missing = selection_metrics(items, [])
        self.assertIsNone(missing['precision'])
        self.assertEqual(missing['recall'], 0)
        selected = selection_metrics(items, ['noise'])
        self.assertEqual(selected['false_positive'], 1)
        self.assertEqual(selected['false_negative'], 1)

    def test_lexical_control_does_not_read_reference_labels(self):
        items = [{'id': 'old', 'text': 'Old rice preference', 'relevant': False},
                 {'id': 'current', 'text': 'Current lunch schedule', 'relevant': True}]
        chosen = select_lexical('rice meal', items)
        self.assertEqual(chosen, ['old'])


if __name__ == '__main__':
    unittest.main()
