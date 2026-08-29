from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

import obus_launcher


class FakeMenuItem:
    def __init__(self, text, action, **kwargs):
        self.text = text
        self.action = action
        self.kwargs = kwargs


class FakeMenu:
    SEPARATOR = object()

    def __init__(self, *items):
        self.items = items


class FakeIcon:
    HAS_NOTIFICATION = True

    def __init__(self, name, image, title, menu):
        self.name = name
        self.image = image
        self.title = title
        self.menu = menu
        self.notifications = []

    def run(self):
        return None

    def update_menu(self):
        return None

    def stop(self):
        return None

    def notify(self, message, title=None):
        self.notifications.append((title, message))


def test_system_tray_starts_with_status_and_voice_controls():
    fake_pystray = SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)
    opened_pages = []

    with patch.dict(sys.modules, {"pystray": fake_pystray}), patch.object(
        obus_launcher, "_tray_image", return_value="image"
    ), patch.object(obus_launcher.threading.Thread, "start") as start:
        icon = obus_launcher.start_system_tray(lambda: None, lambda: None, opened_pages.append)

    assert icon is not None
    assert icon.title == "OBus — starting"
    labels = [item.text for item in icon.menu.items if isinstance(item, FakeMenuItem)]
    assert "Open OBus" in labels
    assert "Open active agents" in labels
    assert "Open latest task outcome" in labels
    assert any(callable(label) for label in labels)
    assert "Open run receipts" in labels
    assert "Refresh local status" in labels
    assert "Mute voice" in labels
    assert "Exit OBus" in labels
    assert start.call_count == 2
    next(item for item in icon.menu.items if isinstance(item, FakeMenuItem) and item.text == "Open active agents").action(icon, None)
    next(item for item in icon.menu.items if isinstance(item, FakeMenuItem) and item.text == "Open run receipts").action(icon, None)
    assert opened_pages == ["runtime", "runs"]


def test_system_tray_opens_only_the_latest_opaque_terminal_task():
    fake_pystray = SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)
    opened_pages = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            import json
            return json.dumps(self.payload).encode("utf-8")

    responses = [
        Response({"active_tasks": 0, "provider_default": "local-ollama"}),
        Response({"approvals": []}),
        Response({"tasks": [{"id": "task-opaque-42", "state": "succeeded", "objective": "must not be passed"}]}),
        Response({"threads": [], "pending_approvals": []}),
        Response({"muted": False}),
    ]
    with patch.dict(sys.modules, {"pystray": fake_pystray}), patch.object(
        obus_launcher, "_tray_image", return_value="image"
    ), patch.object(obus_launcher.urllib.request, "urlopen", side_effect=responses), patch.object(
        obus_launcher.threading.Thread, "start"
    ):
        icon = obus_launcher.start_system_tray(lambda: None, lambda: None, opened_pages.append)
        refresh = next(item for item in icon.menu.items if isinstance(item, FakeMenuItem) and item.text == "Refresh local status")
        refresh.action(icon, None)
        latest = next(item for item in icon.menu.items if isinstance(item, FakeMenuItem) and item.text == "Open latest task outcome")
        latest.action(icon, None)

    assert opened_pages == ["dashboard&task=task-opaque-42"]
    assert "must not be passed" not in repr(opened_pages)


def test_system_tray_surfaces_pending_major_risk_approvals_without_starting_work():
    fake_pystray = SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)
    opened_pages = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            import json
            return json.dumps(self.payload).encode("utf-8")

    responses = [
        Response({"active_tasks": 0, "provider_default": "local-ollama"}),
            Response({"approvals": [{"status": "pending"}]}),
            Response({"tasks": []}),
            Response({"threads": [], "pending_approvals": []}),
            Response({"muted": False}),
    ]
    with patch.dict(sys.modules, {"pystray": fake_pystray}), patch.object(
        obus_launcher, "_tray_image", return_value="image"
    ), patch.object(obus_launcher.urllib.request, "urlopen", side_effect=responses), patch.object(
        obus_launcher.threading.Thread, "start"
    ):
        icon = obus_launcher.start_system_tray(lambda: None, lambda: None, opened_pages.append)
        refresh = next(item for item in icon.menu.items if isinstance(item, FakeMenuItem) and item.text == "Refresh local status")
        refresh.action(icon, None)
        review = next(
            item for item in icon.menu.items
            if isinstance(item, FakeMenuItem) and callable(item.text) and "major-risk approvals" in item.text(None)
        )
        review.action(icon, None)

    assert "1 approval required" in icon.title
    assert opened_pages == ["runtime"]


def test_system_tray_refreshes_a_redacted_local_status_without_starting_work():
    fake_pystray = SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            import json
            return json.dumps(self.payload).encode("utf-8")

    responses = [
        Response({"active_tasks": 2, "provider_default": "local-ollama"}),
            Response({"approvals": []}),
            Response({"tasks": []}),
            Response({"threads": [], "pending_approvals": []}),
            Response({"muted": False}),
    ]
    with patch.dict(sys.modules, {"pystray": fake_pystray}), patch.object(
        obus_launcher, "_tray_image", return_value="image"
    ), patch.object(obus_launcher.urllib.request, "urlopen", side_effect=responses), patch.object(
        obus_launcher.threading.Thread, "start"
    ):
        icon = obus_launcher.start_system_tray(lambda: None, lambda: None)
        refresh = next(item for item in icon.menu.items if isinstance(item, FakeMenuItem) and item.text == "Refresh local status")
        refresh.action(icon, None)

    assert icon.title == "OBus — ready · 2 active · local-ollama"
    assert "complete" not in icon.title.lower()
    assert "objective" not in icon.title.lower()


def test_system_tray_notifies_redacted_interrupted_task_without_resuming_work():
    fake_pystray = SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            import json
            return json.dumps(self.payload).encode("utf-8")

    responses = [
        Response({"active_tasks": 1, "provider_default": "local-ollama"}),
            Response({"approvals": []}),
            Response({"tasks": [{"id": "task-1", "state": "running"}]}),
            Response({"threads": [], "pending_approvals": []}),
            Response({"muted": False}),
        Response({"active_tasks": 0, "provider_default": "local-ollama"}),
            Response({"approvals": []}),
            Response({"tasks": [{"id": "task-1", "state": "interrupted", "objective": "must not appear"}]}),
            Response({"threads": [], "pending_approvals": []}),
            Response({"muted": False}),
    ]
    with patch.dict(sys.modules, {"pystray": fake_pystray}), patch.object(
        obus_launcher, "_tray_image", return_value="image"
    ), patch.object(obus_launcher.urllib.request, "urlopen", side_effect=responses), patch.object(
        obus_launcher.threading.Thread, "start"
    ):
        icon = obus_launcher.start_system_tray(lambda: None, lambda: None)
        refresh = next(item for item in icon.menu.items if isinstance(item, FakeMenuItem) and item.text == "Refresh local status")
        refresh.action(icon, None)
        refresh.action(icon, None)

    assert "1 task review" in icon.title
    assert ("OBus", "A local task was interrupted. Review its checkpoint before choosing whether to resume it.") in icon.notifications
    assert "must not appear" not in repr(icon.notifications)


def test_system_tray_surfaces_read_only_codex_bridge_activity_and_approval_holds():
    fake_pystray = SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)
    opened_pages = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            import json
            return json.dumps(self.payload).encode("utf-8")

    responses = [
        Response({"active_tasks": 0, "provider_default": "codex"}),
        Response({"approvals": []}),
        Response({"tasks": []}),
        Response({"threads": [{"id": "thr-1", "active_turn": "turn-1"}], "pending_approvals": [{"status": "pending"}]}),
        Response({"muted": False}),
    ]
    with patch.dict(sys.modules, {"pystray": fake_pystray}), patch.object(
        obus_launcher, "_tray_image", return_value="image"
    ), patch.object(obus_launcher.urllib.request, "urlopen", side_effect=responses), patch.object(
        obus_launcher.threading.Thread, "start"
    ):
        icon = obus_launcher.start_system_tray(lambda: None, lambda: None, opened_pages.append)
        refresh = next(item for item in icon.menu.items if isinstance(item, FakeMenuItem) and item.text == "Refresh local status")
        refresh.action(icon, None)
        review = next(
            item for item in icon.menu.items
            if isinstance(item, FakeMenuItem) and callable(item.text) and "Codex approvals" in item.text(None)
        )
        review.action(icon, None)

    assert "1 Codex active" in icon.title
    assert "1 Codex approval" in icon.title
    assert opened_pages == ["home"]
