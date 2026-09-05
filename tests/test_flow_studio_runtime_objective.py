from pathlib import Path
from unittest import TestCase

from backend.flow_studio import compile_runtime_objective


class FlowStudioRuntimeObjectiveTests(TestCase):
    def test_runtime_objective_is_a_readable_plan_not_serialized_editor_data(self) -> None:
        objective = compile_runtime_objective(
            {
                "title": "Research Brief",
                "version": 4,
                "nodes": [
                    {
                        "id": "input",
                        "stage": "observe",
                        "label": "Input",
                        "description": "Capture the request",
                    },
                    {
                        "id": "output",
                        "stage": "act",
                        "label": "Output",
                        "description": "Deliver the result",
                    },
                ],
                "edges": [{"source": "input", "target": "output", "type": "data"}],
            }
        )

        self.assertIn("Run the saved Flow Studio draft: Research Brief (version 4).", objective)
        self.assertIn("- Observe: Input — Capture the request", objective)
        self.assertIn("- Act: Output — Deliver the result", objective)
        self.assertIn("- Input → Output (data)", objective)
        self.assertNotIn('"nodes"', objective)

    def test_flow_studio_shows_only_blueprints_and_exposes_advanced_navigation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        flow_studio = (root / "backend" / "static" / "flow_studio.html").read_text(encoding="utf-8")
        dashboard = (root / "backend" / "static" / "index.html").read_text(encoding="utf-8")

        self.assertIn("items.filter(x=>x.kind==='template')", flow_studio)
        self.assertIn('<details id="guided-advanced-nav" class="guided-advanced-nav" open>', dashboard)
