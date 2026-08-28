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


def test_desktop_starts_an_isolated_loopback_backend_when_default_port_is_legacy():
    source = WRAPPER.read_text(encoding="utf-8")

    assert 'probe.listen(0, "127.0.0.1"' in source
    assert "reserveLoopbackTarget" in source
    assert "if (process.env.OBUS_URL)" in source
    assert "return startBundledBackend(await reserveLoopbackTarget());" in source
    assert "The packaged desktop owns a dedicated runtime." in source
    assert "env: { ...process.env, OBUS_PORT: port }" in source
    assert "activeTarget = await ensureBackend(target);" in source
