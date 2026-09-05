import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as backend
from backend.tentacle_worms import WORM_ROLES, run_tentacle_audit


class TentacleWormTests(unittest.TestCase):
    def test_first_install_audit_repairs_safe_local_state_and_redacts_llm_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            memory = root / "memory.json"
            report = root / "tentacle_worm_report.json"
            memory.write_text("not-json", encoding="utf-8")
            state = {"settings": {"selected_model": "missing-model", "rag_character_budget": 99, "max_parallel_agents": 99}}

            result = run_tentacle_audit(
                data_dir=root,
                state=state,
                ollama={"connected": True, "models": ["llama3.2:latest"], "url": "http://127.0.0.1:11434"},
                report_file=report,
                first_install=True,
                apply_safe_fixes=True,
                llm_review=lambda evidence: {"assessment": "bearer super-secret-token", "recommendations": ["keep localhost binding"]},
            )

            self.assertEqual(set(result["worms"]), set(WORM_ROLES))
            self.assertEqual(json.loads(memory.read_text(encoding="utf-8")), [])
            self.assertEqual(state["settings"]["rag_character_budget"], 800)
            self.assertEqual(state["settings"]["max_parallel_agents"], 20)
            self.assertIn("selected_model_missing", {check["id"] for check in result["checks"]})
            self.assertTrue(result["safe_fixes"])
            self.assertNotIn("super-secret-token", json.dumps(result))
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["run_mode"], "first-install")

    def test_cancelled_audit_does_not_mutate_or_write_a_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "tentacle_worm_report.json"
            state = {"settings": {"rag_character_budget": 99, "max_parallel_agents": 99}}
            stop_event = threading.Event()
            stop_event.set()

            result = run_tentacle_audit(
                data_dir=root,
                state=state,
                ollama={"connected": False, "models": [], "url": "http://127.0.0.1:11434"},
                report_file=report,
                first_install=True,
                apply_safe_fixes=True,
                stop_event=stop_event,
            )

            self.assertEqual(result["status"], "cancelled")
            self.assertTrue(result["verification"]["cancelled"])
            self.assertEqual(state["settings"], {"rag_character_budget": 99, "max_parallel_agents": 99})
            self.assertFalse(report.exists())

    def test_runtime_api_runs_and_exposes_tentacle_report(self):
        client = TestClient(backend.app)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(backend, "TENTACLE_REPORT_FILE", Path(tmp) / "report.json"), \
             patch.object(backend, "TENTACLE_RUN_AUDIT") as audit:
            audit.return_value = {
                "status": "ready", "run_mode": "manual", "worms": list(WORM_ROLES),
                "checks": [], "safe_fixes": [], "verification": {"passed": True}, "llm_review": {"status": "complete"},
            }
            run = client.post("/api/tentacle-worms/run", json={"full": True})
            self.assertEqual(run.status_code, 200)
            self.assertEqual(run.json()["status"], "ready")
            status = client.get("/api/tentacle-worms/status")
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["status"], "ready")

    def test_lifespan_cancels_tentacle_worker_with_bounded_shutdown(self):
        audit_started = threading.Event()

        def wait_for_shutdown(**kwargs):
            stop_event = kwargs["stop_event"]
            audit_started.set()
            stop_event.wait(2)
            return {
                "status": "cancelled",
                "run_mode": "startup",
                "worms": list(WORM_ROLES),
                "checks": [],
                "safe_fixes": [],
                "verification": {"passed": True, "cancelled": True},
                "llm_review": {"status": "skipped"},
            }

        with patch.object(backend, "TENTACLE_THREAD", None), \
             patch.object(backend, "TENTACLE_RUN_AUDIT", side_effect=wait_for_shutdown):
            started_at = time.monotonic()
            with TestClient(backend.app):
                self.assertTrue(audit_started.wait(1))
            elapsed = time.monotonic() - started_at
            worker = backend.TENTACLE_THREAD

        self.assertLess(elapsed, 1.5)
        self.assertIsNotNone(worker)
        self.assertFalse(worker.is_alive())
        self.assertTrue(backend.TENTACLE_STOP_EVENT.is_set())

    def test_tentacle_ui_and_startup_hook_are_present(self):
        client = TestClient(backend.app)
        html = client.get("/").text
        for control_id in ("tentacle-status", "tentacle-worm-grid", "tentacle-run", "tentacle-report"):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn('/static/aui/dashboard.js', html)
        self.assertIn("loadTentacleWorms", client.get("/static/aui/dashboard.js").text)
        self.assertIn("start_tentacle_worms", (Path(__file__).parents[1] / "backend" / "main.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
