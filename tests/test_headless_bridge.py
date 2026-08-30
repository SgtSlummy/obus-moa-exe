import unittest
from pathlib import Path
from unittest.mock import patch

import obus_hermes_bridge as bridge
import obus_launcher


class HeadlessRuntimeTests(unittest.TestCase):
    def test_launcher_recognizes_headless_mode(self):
        self.assertTrue(obus_launcher.headless_requested(["--headless"]))
        self.assertTrue(obus_launcher.headless_requested(["--serve"]))
        self.assertFalse(obus_launcher.headless_requested([]))
        self.assertTrue(obus_launcher.INSTANCE_MUTEX_NAME.endswith(str(obus_launcher.APP_PORT)))

    def test_headless_source_does_not_reuse_an_unrelated_health_endpoint(self):
        source = Path(obus_launcher.__file__).read_text(encoding="utf-8")
        self.assertIn("if not headless:\n        existing_health = obus_health_state(HEALTH_URL)", source)

    def test_headless_secondary_launch_never_opens_the_ui(self):
        with patch.object(obus_launcher, "acquire_single_instance", return_value=False), \
             patch.object(obus_launcher, "wait_for_server", return_value=True), \
             patch.object(obus_launcher, "ensure_app_window") as open_window:
            obus_launcher.main(["--headless"])
        open_window.assert_not_called()

    def test_bridge_starts_the_runtime_in_headless_mode(self):
        runtime = bridge.ObusRuntime()
        fake_exe = Path("C:/OBus/OBus.exe")
        with patch.object(bridge, "OBUS_EXE", fake_exe), \
             patch.object(Path, "is_file", return_value=True):
            self.assertEqual(runtime.launch_command(), [str(fake_exe), "--headless"])

    def test_bridge_advertises_the_actual_local_default_model(self):
        self.assertEqual(bridge.OBUS_MODEL, "gpt-oss:20b")

    def test_windows_service_does_not_override_the_current_runtime_path(self):
        service_source = Path("obus_bridge_service.py").read_text(encoding="utf-8")
        self.assertNotIn('os.environ.setdefault("OBUS_EXE"', service_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
