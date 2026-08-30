import os
import sys
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import obus_launcher


class FakeClosingEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


def test_native_desktop_host_can_be_explicitly_disabled():
    with patch.dict(os.environ, {"OBUS_DESKTOP_HOST": "edge"}):
        assert obus_launcher.native_desktop_host_enabled() is False


def test_native_desktop_host_creates_a_single_native_webview_window():
    window = SimpleNamespace(load_url=Mock(), restore=Mock(), show=Mock(), destroy=Mock())
    webview = SimpleNamespace(create_window=Mock(return_value=window), start=Mock())

    previous = obus_launcher.NATIVE_WINDOW
    try:
        with patch.dict(sys.modules, {"webview": webview}), patch.object(
            obus_launcher, "native_desktop_host_enabled", return_value=True
        ):
            assert obus_launcher.run_native_desktop_window("http://127.0.0.1:38173/") is True
    finally:
        obus_launcher.NATIVE_WINDOW = previous

    webview.create_window.assert_called_once()
    args, kwargs = webview.create_window.call_args
    assert args == (obus_launcher.DESKTOP_WINDOW_TITLE, "http://127.0.0.1:38173/")
    assert kwargs["min_size"] == (1024, 660)
    start_args, start_kwargs = webview.start.call_args
    assert start_args == ()
    assert start_kwargs["gui"] == "edgechromium"
    assert start_kwargs["private_mode"] is True


def test_native_window_close_hides_to_tray_until_explicit_exit_is_requested():
    window = SimpleNamespace(
        load_url=Mock(),
        restore=Mock(),
        show=Mock(),
        hide=Mock(),
        destroy=Mock(),
        events=SimpleNamespace(closing=FakeClosingEvent()),
    )
    webview = SimpleNamespace(create_window=Mock(return_value=window), start=Mock())
    previous = obus_launcher.NATIVE_WINDOW
    try:
        obus_launcher.NATIVE_WINDOW_EXIT_REQUESTED.clear()
        with patch.dict(sys.modules, {"webview": webview}), patch.object(
            obus_launcher, "native_desktop_host_enabled", return_value=True
        ):
            assert obus_launcher.run_native_desktop_window(
                "http://127.0.0.1:38173/", hide_to_tray_on_close=True
            ) is True

        handler = window.events.closing.handlers[0]
        assert handler(window) is False
        window.hide.assert_called_once_with()

        obus_launcher.NATIVE_WINDOW_EXIT_REQUESTED.set()
        assert handler(window) is None
        window.hide.assert_called_once_with()
    finally:
        obus_launcher.NATIVE_WINDOW = previous
        obus_launcher.NATIVE_WINDOW_EXIT_REQUESTED.clear()


def test_native_window_focuses_in_process_window_before_browser_fallback():
    window = SimpleNamespace(load_url=Mock(), restore=Mock(), show=Mock(), destroy=Mock())
    previous = obus_launcher.NATIVE_WINDOW
    try:
        obus_launcher.NATIVE_WINDOW = window
        assert obus_launcher.focus_native_window("http://127.0.0.1:38173/?page=runtime") is True
    finally:
        obus_launcher.NATIVE_WINDOW = previous

    window.load_url.assert_called_once_with("http://127.0.0.1:38173/?page=runtime")
    window.restore.assert_called_once_with()
    window.show.assert_called_once_with()


def test_startup_diagnostics_are_bounded_and_exclude_unstructured_values(tmp_path):
    previous_path = obus_launcher.STARTUP_DIAGNOSTIC_PATH
    previous_dir = obus_launcher.STARTUP_LOG_DIR
    previous_diagnostic = obus_launcher.STARTUP_DIAGNOSTIC.copy()
    try:
        obus_launcher.STARTUP_LOG_DIR = tmp_path
        obus_launcher.STARTUP_DIAGNOSTIC_PATH = tmp_path / "obus-startup-test.json"
        obus_launcher.STARTUP_DIAGNOSTIC = {"started_at": "now", "app_port": 38173, "events": []}
        obus_launcher.record_startup_event("native_window_failed", error_type="RuntimeError", ignored={"secret": "nope"})
        payload = json.loads(obus_launcher.STARTUP_DIAGNOSTIC_PATH.read_text(encoding="utf-8"))
    finally:
        obus_launcher.STARTUP_DIAGNOSTIC_PATH = previous_path
        obus_launcher.STARTUP_LOG_DIR = previous_dir
        obus_launcher.STARTUP_DIAGNOSTIC = previous_diagnostic

    assert payload["events"][-1]["event"] == "native_window_failed"
    assert payload["events"][-1]["details"] == {"error_type": "RuntimeError"}
