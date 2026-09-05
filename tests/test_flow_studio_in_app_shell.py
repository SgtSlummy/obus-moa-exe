from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_embeds_flow_studio_in_the_existing_window() -> None:
    page = (ROOT / "backend" / "static" / "index.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "backend" / "static" / "aui" / "dashboard.js").read_text(encoding="utf-8")

    assert 'data-flow-studio-in-app' in page
    assert 'id="flow-studio-dialog"' in page
    assert 'id="flow-studio-frame"' in page
    assert 'Back to command center' in page
    assert "function installFlowStudioInApp()" in dashboard
    assert "frame.src=`${trigger.href}?v=flow-settings-parent-navigation-1`" in dashboard
    assert "event.source!==frame.contentWindow" in dashboard
    assert "event.data?.type!=='obus:navigate'" in dashboard
    assert "dialog.showModal()" in dashboard


def test_electron_installs_an_in_window_flow_studio_fallback_for_older_backend_bundles():
    source = (ROOT / "electron_app" / "main.js").read_text(encoding="utf-8")

    assert "flow-studio-electron-dialog" in source
    assert "dialog.showModal();" in source
    assert "new URL('/flow-studio', window.location.origin).href" in source


def test_electron_reuses_current_window_for_loopback_popups() -> None:
    source = (ROOT / "electron_app" / "main.js").read_text(encoding="utf-8")

    assert "if (isLoopbackUrl(url)) {" in source
    assert "mainWindow?.loadURL(url);" in source
    assert "if (isSafeExternalUrl(url)) shell.openExternal(url);" in source
