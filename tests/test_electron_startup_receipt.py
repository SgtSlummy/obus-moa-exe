from pathlib import Path


WRAPPER = Path(__file__).parents[1] / "electron_app" / "main.js"


def test_electron_resolves_latest_local_startup_receipt_before_fixed_port():
    source = WRAPPER.read_text(encoding="utf-8")

    assert "function latestStartupUrl(newerThan = 0)" in source
    assert 'path.join(localAppData, "OBus", "logs", "startup")' in source
    assert "receipt.app_port" in source
    assert "requested || latestStartupUrl() || DEFAULT_OBUS_URL" in source
    assert "latestStartupUrl(newerThan = 0)" in source
    assert "latest.modified < newerThan" in source
    assert "retryWithFreshReceipt" in source
    assert "retryUntil = launchStartedAt + 20_000" in source


def test_electron_keeps_endpoint_loopback_only():
    source = WRAPPER.read_text(encoding="utf-8")

    assert "function safeLoopbackUrl(value)" in source
    assert 'parsed.protocol !== "http:" || !loopback' in source
