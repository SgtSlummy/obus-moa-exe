import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = ROOT / "docs" / "aui-design-rubric.md"


class AUIDesignRubricTests(unittest.TestCase):
    def test_design_rubric_has_hard_gates_and_exact_weight_total(self):
        self.assertTrue(RUBRIC_PATH.exists(), "AUI design rubric must be checked in")
        rubric = RUBRIC_PATH.read_text(encoding="utf-8")
        weights = [int(value) for value in re.findall(r"\|\s*(\d+)%\s*\|", rubric)]
        self.assertEqual(weights, [20, 12, 10, 10, 12, 12, 10, 8, 3, 3])
        self.assertEqual(sum(weights), 100)
        for marker in (
            "9.90",
            "no rounding",
            "zero unintended overlap",
            "zero clipped non-scrollable text",
            "390",
            "1920",
            "compact",
            "comfortable",
            "spacious",
        ):
            self.assertIn(marker.lower(), rubric.lower())

    def test_design_rubric_covers_every_operational_surface_and_review_role(self):
        rubric = RUBRIC_PATH.read_text(encoding="utf-8")
        for surface in (
            "Run",
            "Cards & Keys",
            "Agents",
            "Runtime",
            "Rooms",
            "Receipts",
            "Visual Studio",
            "Routing",
            "Memory",
            "Setup",
        ):
            self.assertIn(surface, rubric)
        for reviewer in (
            "spec reviewer",
            "visual-design reviewer",
            "accessibility/geometry reviewer",
            "code/security reviewer",
        ):
            self.assertIn(reviewer, rubric.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
