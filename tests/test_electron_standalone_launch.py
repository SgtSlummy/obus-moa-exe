import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_electron_owns_a_private_bundled_backend_before_loading_ui() -> None:
    source = (ROOT / "electron_app" / "main.js").read_text(encoding="utf-8")

    assert 'const { spawn } = require("child_process");' in source
    assert 'path.join(process.resourcesPath, "backend", "OBus.exe")' in source
    assert 'spawn(executable, ["--headless"]' in source
    assert 'OBUS_PORT: port' in source
    assert 'return startBundledBackend(await reserveLoopbackTarget());' in source
    assert 'activeTarget = activeTarget || await ensureBackend(obusUrl());' in source
    assert 'createWindow(activeTarget);' in source


def test_primary_ui_has_no_system_browser_fallback() -> None:
    source = (ROOT / "electron_app" / "main.js").read_text(encoding="utf-8")

    assert "webbrowser" not in source
    assert 'mainWindow.loadURL(target);' in source
    assert 'mainWindow.webContents.setWindowOpenHandler' in source
    assert 'if (isSafeExternalUrl(url)) shell.openExternal(url);' in source
    assert 'if (!isLoopbackUrl(url)) event.preventDefault();' in source


def test_windows_package_includes_the_owned_backend() -> None:
    package = json.loads((ROOT / "electron_app" / "package.json").read_text(encoding="utf-8"))

    assert "electron" in package["devDependencies"]
    assert package["build"]["productName"] == "OBus"
    assert {"from": "../dist/OBus.exe", "to": "backend/OBus.exe"} in package["build"]["extraResources"]


def test_electron_serializes_concurrent_startup_requests() -> None:
    source = (ROOT / "electron_app" / "main.js").read_text(encoding="utf-8")

    assert "let launchPromise = null;" in source
    assert "if (launchPromise) return launchPromise;" in source
    assert "launchPromise = (async () => {" in source
    assert "finally {\n      launchPromise = null;" in source
