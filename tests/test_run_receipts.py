import json
import tempfile
import unittest
from pathlib import Path

from backend.run_receipts import (
    build_run_receipt,
    format_receipt_markdown,
    load_receipts,
    persist_receipt,
    redact_text,
)


class RunReceiptTests(unittest.TestCase):
    def test_redaction_removes_credentials_and_pem_material(self):
        raw = "api_key=sk-secret Bearer abc123 password: hunter2\n-----BEGIN PRIVATE KEY-----\nsecret"
        redacted = redact_text(raw)
        self.assertNotIn("sk-secret", redacted)
        self.assertNotIn("abc123", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertNotIn("BEGIN PRIVATE KEY", redacted)
        self.assertIn("redacted", redacted.lower())

    def test_redaction_removes_bare_provider_keys_and_basic_authorization(self):
        provider_key = "sk-" + "proj-" + "examplesecret123"
        basic_token = "Zm9v" + "OmJhcg=="
        header_value = "local-" + "secret-value"
        raw = f"{provider_key} Authorization: Basic {basic_token} x-api-key: {header_value}"
        redacted = redact_text(raw)
        self.assertNotIn(provider_key, redacted)
        self.assertNotIn(basic_token, redacted)
        self.assertNotIn(header_value, redacted)
        self.assertIn("redacted", redacted.lower())

    def test_receipt_contains_hash_plan_trace_and_no_raw_prompt(self):
        prompt = "Review this service using api_key=secret"
        plan = {
            "routing_policy": "auto-open",
            "selected_deck": {"id": "security", "name": "Security"},
            "moa": {"profile": "balanced", "advisor_count": 3},
            "agents": {"dynamic_assignments": [{
                "agent_id": "card-hermit", "agent_title": "The Hermit", "provider": "Ollama", "model": "open", "llm_key": "key-local-ollama",
                "routing_explanation": {"reason": "local"},
            }], "aggregator": {"provider": "Luna", "model": "gpt-5.6-luna"}},
        }
        result = {"status": "partial", "final": "answer Bearer secret", "trace": [{"stage": "local", "output": "answer"}], "usage": {"total_tokens": 12}, "execution_scope": {"mode": "preview_only", "remote_prompt_transfer": False}}
        receipt = build_run_receipt(prompt, plan, result, receipt_id="run-test")
        self.assertEqual(receipt["id"], "run-test")
        self.assertEqual(len(receipt["prompt_sha256"]), 64)
        self.assertNotIn(prompt, json.dumps(receipt))
        self.assertNotIn("secret", json.dumps(receipt).lower())
        self.assertEqual(receipt["routing_policy"], "auto-open")
        self.assertEqual(receipt["execution_scope"]["mode"], "preview_only")
        self.assertTrue(receipt["trace"])
        self.assertIn("Execution scope", format_receipt_markdown(receipt))

    def test_receipts_persist_with_retention_and_export_without_private_room_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipts.json"
            first = {"id": "one", "final": "first"}
            second = {"id": "two", "final": "second"}
            persist_receipt(path, first, retention=1)
            persist_receipt(path, second, retention=1)
            self.assertEqual([item["id"] for item in load_receipts(path)], ["two"])
            markdown = format_receipt_markdown(second)
            self.assertIn("two", markdown)
            self.assertNotIn("private_messages", markdown)

    def test_offline_route_returns_and_persists_receipt_end_to_end(self):
        from fastapi.testclient import TestClient
        import backend.main as backend
        client = TestClient(backend.app)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patches = [
                __import__("unittest.mock", fromlist=["patch"]).patch.object(backend, "STATE_FILE", root / "state.json"),
                __import__("unittest.mock", fromlist=["patch"]).patch.object(backend, "MEMORY_FILE", root / "memory.json"),
                __import__("unittest.mock", fromlist=["patch"]).patch.object(backend, "USAGE_FILE", root / "usage.json"),
                __import__("unittest.mock", fromlist=["patch"]).patch.object(backend, "RECEIPT_FILE", root / "receipts.json"),
                __import__("unittest.mock", fromlist=["patch"]).patch.object(backend, "get_ollama_status", return_value={"connected": False, "models": []}),
            ]
            for item in patches:
                item.start()
            try:
                response = client.post("/api/route/run", json={"prompt": "Record an offline route", "rag_enabled": False})
                self.assertEqual(response.status_code, 200)
                receipt = response.json()["receipt"]
                self.assertEqual(receipt["status"], "complete")
                listing = client.get("/api/runs")
                self.assertEqual(listing.status_code, 200)
                self.assertEqual(listing.json()[0]["id"], receipt["id"])
                detail = client.get(f"/api/runs/{receipt['id']}")
                self.assertEqual(detail.status_code, 200)
                self.assertNotIn("Record an offline route", json.dumps(detail.json()))
                exported = client.get(f"/api/runs/{receipt['id']}/export")
                self.assertEqual(exported.status_code, 200)
                self.assertIn("OBus run receipt", exported.text)
            finally:
                for item in reversed(patches):
                    item.stop()

    def test_ui_exposes_run_receipt_controls_and_endpoints(self):
        from fastapi.testclient import TestClient
        import backend.main as backend
        html = TestClient(backend.app).get("/").text
        for control_id in ("export-latest-receipt", "run-list", "run-receipt-detail"):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("exportLatestReceipt", html)
        self.assertIn("/api/runs/", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
