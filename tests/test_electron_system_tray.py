from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_electron_hides_to_tray_and_restores_on_request():
    source = (ROOT / "electron_app" / "main.js").read_text(encoding="utf-8")

    assert "const { Tray, nativeImage } = require(\"electron\");" in source
    assert "function ensureTray()" in source
    assert "new Tray(trayIcon())" in source
    assert "{ label: 'Open OBus', click: showMainWindow }" in source
    assert "{ label: 'Quit OBus', click: quitApplication }" in source
    assert "tray.on('click', showMainWindow);" in source
    assert "event.preventDefault();\n    mainWindow.hide();" in source
    assert "mainWindow.show();" in source
    assert "mainWindow.focus();" in source
    assert "app.on('second-instance', () => showMainWindow());" in source


def test_electron_allows_real_exit_only_after_explicit_quit():
    source = (ROOT / "electron_app" / "main.js").read_text(encoding="utf-8")

    assert "let isQuitting = false;" in source
    assert "isQuitting = true;\n  app.quit();" in source
    assert "if (isQuitting) return;" in source
