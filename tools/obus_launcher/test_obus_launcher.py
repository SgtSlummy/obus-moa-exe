from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import obus_launcher


class Response:
    def __init__(self, payload: dict, status: int = 200):
        self.status = status
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class LauncherContractTests(unittest.TestCase):
    @patch("obus_launcher.urllib.request.urlopen")
    def test_health_check_uses_the_real_obus_endpoint(self, urlopen):
        urlopen.return_value = Response({"status": "ok", "service": "obus-moa"})
        self.assertTrue(obus_launcher.is_dashboard_healthy())
        self.assertEqual(urlopen.call_args.args[0].full_url, "http://127.0.0.1:38173/health")

    @patch("obus_launcher.urllib.request.urlopen", side_effect=OSError("offline"))
    def test_health_check_fails_when_backend_is_unreachable(self, _urlopen):
        self.assertFalse(obus_launcher.is_dashboard_healthy())

    @patch("obus_launcher.urllib.request.urlopen")
    def test_collect_readiness_uses_real_warmup_and_memory_routes(self, urlopen):
        urlopen.side_effect = [
            Response({"status": "ok"}),
            Response({"connected": True, "models": ["gpt-oss:20b"]}),
            Response({"status": "warm", "model": "gpt-oss:20b"}),
            Response({"sources": []}),
        ]
        readiness = obus_launcher.collect_readiness()
        self.assertTrue(readiness["dashboard_healthy"])
        self.assertTrue(readiness["ollama"]["connected"])
        self.assertEqual(readiness["warmup"]["model"], "gpt-oss:20b")
        urls = [call.args[0].full_url for call in urlopen.call_args_list]
        self.assertEqual(urls, [
            "http://127.0.0.1:38173/health",
            "http://127.0.0.1:11434/api/tags",
            "http://127.0.0.1:38173/api/warmup",
            "http://127.0.0.1:38173/api/integrations/memory",
        ])

    @patch("obus_launcher.subprocess.Popen")
    @patch("obus_launcher.wait_for_dashboard", return_value=True)
    @patch("obus_launcher.is_dashboard_healthy", return_value=False)
    def test_starts_backend_only_when_not_already_healthy(self, healthy, wait, popen):
        self.assertTrue(obus_launcher.ensure_backend_running())
        healthy.assert_called_once_with()
        wait.assert_called_once_with()
        self.assertTrue(popen.called)
        self.assertEqual(popen.call_args.args[0][-1], "--serve")

    @patch("obus_launcher.subprocess.Popen")
    @patch("obus_launcher.is_dashboard_healthy", return_value=True)
    def test_does_not_start_duplicate_backend(self, healthy, popen):
        self.assertTrue(obus_launcher.ensure_backend_running())
        healthy.assert_called_once_with()
        popen.assert_not_called()

    @patch("obus_launcher.webbrowser.open")
    @patch("obus_launcher.collect_readiness")
    @patch("obus_launcher.ensure_backend_running", return_value=True)
    def test_launch_opens_dashboard_after_readiness_checks(self, ensure, readiness, browser_open):
        readiness.return_value = {"dashboard_healthy": True, "ollama": {"connected": True}, "warmup": {"status": "warm"}, "memory": {"sources": []}}
        self.assertEqual(obus_launcher.launch_dashboard(keep_alive=False), 0)
        ensure.assert_called_once_with()
        browser_open.assert_called_once_with("http://127.0.0.1:38173/")

    @patch("obus_launcher.webbrowser.open")
    @patch("obus_launcher.show_error")
    @patch("obus_launcher.ensure_backend_running", return_value=False)
    def test_launch_does_not_open_browser_when_backend_cannot_start(self, ensure, show_error, browser_open):
        self.assertEqual(obus_launcher.launch_dashboard(keep_alive=False), 1)
        ensure.assert_called_once_with()
        show_error.assert_called_once()
        browser_open.assert_not_called()

    def test_source_server_command_reenters_launcher_with_serve_mode(self):
        with patch.object(sys, "frozen", False, create=True):
            command = obus_launcher.backend_command()
        self.assertEqual(command[-1], "--serve")
        self.assertTrue(command[1].endswith("obus_launcher.py"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
