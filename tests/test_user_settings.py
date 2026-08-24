import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as backend
from backend.user_settings import (
    DEFAULT_USER_SETTINGS,
    export_user_settings,
    normalize_user_settings,
    validate_import_payload,
)


class UserSettingsTests(unittest.TestCase):
    def test_legacy_settings_receive_workspace_defaults(self):
        value = normalize_user_settings({"rag_enabled": False})
        self.assertEqual(value["settings_schema_version"], 1)
        self.assertEqual(value["workspace_surface"], "operator")
        self.assertEqual(value["routing_policy"], "local-first")
        self.assertIsNone(value["workspace_root"])
        self.assertFalse(value["rag_enabled"])

    def test_invalid_workspace_values_use_safe_defaults(self):
        value = normalize_user_settings({"workspace_surface": "secret", "routing_policy": "anything"})
        self.assertEqual(value["workspace_surface"], DEFAULT_USER_SETTINGS["workspace_surface"])
        self.assertEqual(value["routing_policy"], DEFAULT_USER_SETTINGS["routing_policy"])

    def test_export_is_allowlisted_and_secret_safe(self):
        exported = export_user_settings({
            "workspace_surface": "terminal",
            "routing_policy": "auto-open",
            "workspace_root": "C:/work",
            "api_key": "must-not-export",
            "token": "must-not-export",
            "machine_setup": {"role": "worker"},
        })
        self.assertEqual(exported["settings_schema_version"], 1)
        self.assertEqual(exported["workspace_surface"], "terminal")
        serialized = json.dumps(exported).lower()
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("token", serialized)
        self.assertNotIn("machine_setup", serialized)

    def test_import_rejects_secret_shaped_and_unknown_fields(self):
        with self.assertRaises(ValueError):
            validate_import_payload({"api_key": "secret"})
        with self.assertRaises(ValueError):
            validate_import_payload({"unexpected": True})
        with self.assertRaises(ValueError):
            validate_import_payload({"workspace_surface": "terminal", "token": "secret"})

    def test_settings_export_import_round_trip_does_not_replace_state(self):
        client = TestClient(backend.app)
        with tempfile.TemporaryDirectory() as directory:
            state_file = Path(directory) / "state.json"
            state_patch = patch.object(backend, "STATE_FILE", state_file)
            state_patch.start()
            try:
                backend.save_state(backend.normalize_state({"keys": [{"id": "key-custom", "name": "Keep"}]}))
                exported = client.get("/api/settings/export")
                self.assertEqual(exported.status_code, 200)
                payload = exported.json()
                self.assertEqual(payload["settings_schema_version"], 1)
                imported = client.post("/api/settings/import", json={
                    "settings_schema_version": 1,
                    "workspace_surface": "terminal",
                    "routing_policy": "auto-open",
                    "workspace_root": "C:/work",
                    "rag_enabled": False,
                })
                self.assertEqual(imported.status_code, 200)
                self.assertEqual(imported.json()["workspace_surface"], "terminal")
                persisted = json.loads(state_file.read_text(encoding="utf-8"))
                self.assertEqual(persisted["settings"]["routing_policy"], "auto-open")
                self.assertTrue(any(key["id"] == "key-custom" for key in persisted["keys"]))
            finally:
                state_patch.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)
