import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "aui_review_score.py"


def load_module():
    spec = importlib.util.spec_from_file_location("aui_review_score", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AUIReviewAggregationTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def review(self, reviewer_id, value):
        return {
            "reviewer_id": reviewer_id,
            "category_scores": {key: value for key in self.module.WEIGHTS},
            "evidence_paths": ["evidence/audit.json"],
        }

    def test_two_passing_reviewers_meet_release_gate_and_report_zero_variance(self):
        result = self.module.aggregate_reviews(
            [self.review("reviewer-a", 9.95), self.review("reviewer-b", 9.95)],
            hard_gates_pass=True,
        )
        self.assertTrue(result["pass"])
        self.assertEqual(result["weighted_mean"], 9.95)
        self.assertEqual(result["weighted_display_truncated"], 9.95)
        self.assertEqual(result["reviewer_weighted_pstdev"], 0.0)
        self.assertTrue(all(value == 0.0 for value in result["category_pstdev"].values()))

    def test_subthreshold_score_is_not_rounded_up(self):
        result = self.module.aggregate_reviews(
            [self.review("reviewer-a", 9.89999), self.review("reviewer-b", 9.89999)],
            hard_gates_pass=True,
        )
        self.assertFalse(result["pass"])
        self.assertLess(result["weighted_mean"], 9.90)
        self.assertEqual(result["weighted_display_truncated"], 9.89)

    def test_category_floor_and_hard_gate_both_block_release(self):
        left = self.review("reviewer-a", 10.0)
        right = self.review("reviewer-b", 10.0)
        left["category_scores"]["polish"] = 9.3
        right["category_scores"]["polish"] = 9.3
        result = self.module.aggregate_reviews([left, right], hard_gates_pass=False)
        self.assertFalse(result["pass"])
        self.assertIn("hard_gates", result["blockers"])
        self.assertIn("category_floor:polish", result["blockers"])

    def test_requires_two_unique_complete_reviewers(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            self.module.aggregate_reviews([self.review("reviewer-a", 10)], hard_gates_pass=True)
        with self.assertRaisesRegex(ValueError, "unique"):
            self.module.aggregate_reviews(
                [self.review("same", 10), self.review("same", 10)], hard_gates_pass=True
            )
        incomplete = self.review("reviewer-b", 10)
        incomplete["category_scores"].pop("geometry")
        with self.assertRaisesRegex(ValueError, "categories"):
            self.module.aggregate_reviews(
                [self.review("reviewer-a", 10), incomplete], hard_gates_pass=True
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
