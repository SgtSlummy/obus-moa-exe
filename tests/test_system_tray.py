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
    def __init__(self, name, image, title, menu):
        self.name = name
        self.image = image
        self.title = title
        self.menu = menu

    def run(self):
        return None

    def update_menu(self):
        return None

    def stop(self):
        return None


def test_system_tray_starts_with_status_and_voice_controls():
    fake_pystray = SimpleNamespace(Icon=FakeIcon, Menu=FakeMenu, MenuItem=FakeMenuItem)

    with patch.dict(sys.modules, {"pystray": fake_pystray}), patch.object(
        obus_launcher, "_tray_image", return_value="image"
    ), patch.object(obus_launcher.threading.Thread, "start") as start:
        icon = obus_launcher.start_system_tray(lambda: None, lambda: None)

    assert icon is not None
    assert icon.title == "OBus — starting"
    labels = [item.text for item in icon.menu.items if isinstance(item, FakeMenuItem)]
    assert "Open OBus" in labels
    assert "Mute voice" in labels
    assert "Exit OBus" in labels
    start.assert_called_once()
