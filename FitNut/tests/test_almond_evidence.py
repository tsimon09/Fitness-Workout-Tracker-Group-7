"""Reference-backed, deterministic tests for the pure almond evidence gate.

Run with: python -m unittest tests.test_almond_evidence (from FitNut).
The fixture JSON is deliberately self-contained; no network or nutrition API is used.
"""
import json
import copy
import unittest
from pathlib import Path

from almond_evidence import EvidenceError, validate_recipe


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "almond_cases.json"


class AlmondEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_set_has_20_dev_and_60_heldout_cases(self):
        cases = self.data["cases"]
        self.assertEqual(len(cases), 80)
        self.assertEqual(sum(case["split"] == "dev" for case in cases), 20)
        self.assertEqual(sum(case["split"] == "heldout" for case in cases), 60)
        self.assertEqual(len({case["case_id"] for case in cases}), 80)
        self.assertTrue(all(case.get("rationale") and case.get("expected") in {"accept", "reject"}
                            for case in cases))

    def test_fixture_urls_are_real_reference_endpoints(self):
        catalog = self.data["catalog"]
        self.assertTrue(catalog)
        for entry in catalog.values():
            self.assertTrue(entry["source_url"].startswith("https://"))
            self.assertTrue(entry["evidence_id"])
            self.assertTrue(entry["food_name"])

    def test_all_labeled_cases_against_reference_evidence(self):
        for case in self.data["cases"]:
            with self.subTest(case_id=case["case_id"], rationale=case["rationale"]):
                catalog = {int(food_id): copy.deepcopy(food)
                           for food_id, food in self.data["catalog"].items()}
                recipe = copy.deepcopy(case["recipe"])
                mutation = recipe.pop("fixture_mutation", None)
                if mutation:
                    target = catalog[101]
                    if mutation == "missing_evidence":
                        target["evidence_complete"] = False
                    elif mutation == "wrong_food_name":
                        target["food_name"] = "Apples, raw, with skin"
                    elif mutation == "wrong_ingredients":
                        target["ingredients"] = ["apple"]
                    elif mutation == "missing_allergen":
                        target["allergens"] = []
                    elif mutation == "foreign_evidence":
                        recipe["evidence_ids"] = ["foreign-source"]
                    elif mutation == "negative_calories":
                        target["calories"] = -1
                    elif mutation == "nan_macro":
                        target["protein_g"] = "NaN"
                    elif mutation == "boolean_food_id":
                        recipe["foods"][0]["food_id"] = True
                    elif mutation == "boolean_grams":
                        recipe["foods"][0]["grams"] = True
                    elif mutation == "empty_title":
                        recipe["title"] = ""
                if case["expected"] == "accept":
                    result = validate_recipe(recipe, catalog, case["profile"])
                    self.assertIsInstance(result, dict)
                else:
                    with self.assertRaises(EvidenceError):
                        validate_recipe(recipe, catalog, case["profile"])

    def test_nutrition_unknowns_are_not_silently_zeroed(self):
        catalog = {int(food_id): copy.deepcopy(food) for food_id, food in self.data["catalog"].items()}
        food = catalog[101]
        food["fiber_g"] = None
        recipe = {"title": "Plain almond portion", "foods": [{"food_id": 101, "grams": 28}],
                  "instructions": ["Serve plain."], "substitutions": [],
                  "evidence_ids": [food["evidence_id"]]}
        profile = {"allergy_status": "none_reported", "allergens": [], "other_allergies": [],
                   "intolerances": [], "preferences": [], "dietary_pattern": "no_preference"}
        result = validate_recipe(recipe, catalog, profile)
        self.assertIsNone(result["nutrition"]["fiber_g"],
                          "missing fiber must remain unknown, not become zero")

    def test_allergen_and_ingredient_labels_are_not_conflated(self):
        catalog = {int(food_id): copy.deepcopy(food) for food_id, food in self.data["catalog"].items()}
        food = catalog[101]
        food["ingredients"] = ["almond"]
        food["allergens"] = []
        recipe = {"title": "Plain almond portion", "foods": [{"food_id": 101, "grams": 28}],
                  "instructions": ["Serve plain."], "substitutions": [],
                  "evidence_ids": [food["evidence_id"]]}
        profile = {"allergy_status": "listed", "allergens": ["almond"], "other_allergies": [],
                   "intolerances": [], "preferences": [], "dietary_pattern": "no_preference"}
        with self.assertRaises(EvidenceError):
            validate_recipe(recipe, catalog, profile)

    def test_tree_nut_allergy_checks_substitution_text(self):
        catalog = {int(food_id): copy.deepcopy(food) for food_id, food in self.data["catalog"].items()}
        food = catalog[102]
        recipe = {"title": "Apple snack", "foods": [{"food_id": 102, "grams": 150}],
                  "instructions": ["Slice and serve the apple."],
                  "substitutions": ["Add almond butter if you want more protein."],
                  "evidence_ids": [food["evidence_id"]]}
        profile = {"allergy_status": "listed", "allergens": ["tree_nuts"], "other_allergies": [],
                   "intolerances": [], "preferences": [], "dietary_pattern": "no_preference"}
        with self.assertRaises(EvidenceError):
            validate_recipe(recipe, catalog, profile)

    def test_tree_nut_allergy_checks_title_text(self):
        catalog = {int(food_id): copy.deepcopy(food) for food_id, food in self.data["catalog"].items()}
        food = catalog[102]
        recipe = {"title": "Apple with almond crunch", "foods": [{"food_id": 102, "grams": 150}],
                  "instructions": ["Slice and serve the apple."], "substitutions": [],
                  "evidence_ids": [food["evidence_id"]]}
        profile = {"allergy_status": "listed", "allergens": ["tree_nuts"], "other_allergies": [],
                   "intolerances": [], "preferences": [], "dietary_pattern": "no_preference"}
        with self.assertRaises(EvidenceError):
            validate_recipe(recipe, catalog, profile)

    def test_instruction_cannot_add_an_unselected_ingredient(self):
        catalog = {int(food_id): copy.deepcopy(food) for food_id, food in self.data["catalog"].items()}
        food = catalog[103]
        recipe = {"title": "Plain oats", "foods": [{"food_id": 103, "grams": 40}],
                  "instructions": ["Cook the oats with peanut butter."], "substitutions": [],
                  "evidence_ids": [food["evidence_id"]]}
        profile = {"allergy_status": "none_reported", "allergens": [], "other_allergies": [],
                   "intolerances": [], "preferences": [], "dietary_pattern": "no_preference"}
        with self.assertRaises(EvidenceError):
            validate_recipe(recipe, catalog, profile)

    def test_custom_restriction_is_checked_in_substitution_text(self):
        catalog = {int(food_id): copy.deepcopy(food) for food_id, food in self.data["catalog"].items()}
        food = catalog[102]
        # This says absence of pork was reviewed for the selected apple; the recipe must
        # still reject a substitution that explicitly introduces pork.
        food["restriction_coverage"] = ["pork"]
        recipe = {"title": "Apple snack", "foods": [{"food_id": 102, "grams": 150}],
                  "instructions": ["Slice and serve the apple."],
                  "substitutions": ["Replace it with pork broth."],
                  "evidence_ids": [food["evidence_id"]]}
        profile = {"allergy_status": "none_reported", "allergens": [], "other_allergies": [],
                   "intolerances": [], "preferences": ["No pork"], "dietary_pattern": "no_preference"}
        with self.assertRaises(EvidenceError):
            validate_recipe(recipe, catalog, profile)

    def test_custom_restriction_coverage_must_be_structured_evidence(self):
        catalog = {int(food_id): copy.deepcopy(food) for food_id, food in self.data["catalog"].items()}
        food = catalog[102]
        # A bare string must not be accepted as reviewed coverage by substring membership.
        food["restriction_coverage"] = "pork"
        recipe = {"title": "Apple snack", "foods": [{"food_id": 102, "grams": 150}],
                  "instructions": ["Slice and serve the apple."], "substitutions": [],
                  "evidence_ids": [food["evidence_id"]]}
        profile = {"allergy_status": "none_reported", "allergens": [], "other_allergies": [],
                   "intolerances": [], "preferences": ["No pork"], "dietary_pattern": "no_preference"}
        with self.assertRaises(EvidenceError):
            validate_recipe(recipe, catalog, profile)


if __name__ == "__main__":
    unittest.main()
