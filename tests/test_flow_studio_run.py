from pathlib import Path
from unittest import TestCase


class FlowStudioRunFeedbackTests(TestCase):
    def test_run_reports_success_or_failure_in_the_main_canvas(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "backend" / "static" / "flow_studio.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("function runFeedback(message,kind,taskId)", source)
        self.assertIn("Open task in OBus", source)
        self.assertIn("Flow did not run:", source)
        self.assertIn("canvasMessage.scrollIntoView", source)
