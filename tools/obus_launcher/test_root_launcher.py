"""Regression coverage for the root desktop launcher."""

import importlib.util
from pathlib import Path
from unittest import TestCase, mock

_root_launcher_path = Path(__file__).resolve().parents[2] / "obus_launcher.py"
_root_launcher_spec = importlib.util.spec_from_file_location("root_obus_launcher", _root_launcher_path)
assert _root_launcher_spec and _root_launcher_spec.loader
obus_launcher = importlib.util.module_from_spec(_root_launcher_spec)
_root_launcher_spec.loader.exec_module(obus_launcher)


class RootLauncherTests(TestCase):
    def test_desktop_mode_reuses_a_verified_existing_dashboard(self) -> None:
        with (
            mock.patch.object(obus_launcher, "acquire_single_instance", return_value=True),
            mock.patch.object(obus_launcher, "obus_health_state", return_value="ready"),
            mock.patch.object(obus_launcher, "record_startup_event") as record_event,
            mock.patch.object(obus_launcher, "ensure_app_window") as ensure_window,
        ):
            obus_launcher.main([])

        record_event.assert_any_call("reusing_ready_local_dashboard")
        ensure_window.assert_called_once_with(obus_launcher.APP_URL)


if __name__ == "__main__":
    import unittest

    unittest.main()
