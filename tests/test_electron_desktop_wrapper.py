from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "electron_app" / "main.js"


def test_electron_desktop_fallback_uses_the_canonical_local_obus_endpoint_and_sandbox():
    source = WRAPPER.read_text(encoding="utf-8")

    assert 'DEFAULT_OBUS_URL = "http://127.0.0.1:38173/"' in source
    assert "OBUS_URL" in source
    assert "not a loopback HTTP URL" in source
    assert "nodeIntegration: false" in source
    assert "contextIsolation: true" in source
    assert "sandbox: true" in source


def test_electron_desktop_fallback_stays_single_window_and_blocks_external_navigation():
    source = WRAPPER.read_text(encoding="utf-8")

    assert "requestSingleInstanceLock" in source
    assert "second-instance" in source
    assert "setWindowOpenHandler" in source
    assert "will-navigate" in source
    assert "event.preventDefault()" in source
