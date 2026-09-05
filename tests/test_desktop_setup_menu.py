from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_file_menu_exposes_setup_and_self_diagnosis() -> None:
    source = (ROOT / "electron_app" / "main.js").read_text(encoding="utf-8")

    assert 'label: "First-time setup…"' in source
    assert 'label: "Run self-diagnosis…"' in source
    assert 'title: "OBus self-diagnosis"' in source
    assert 'backendHealthy(target)' in source
    assert 'installApplicationMenu();' in source


def test_first_time_setup_opens_the_existing_settings_page() -> None:
    source = (ROOT / "electron_app" / "main.js").read_text(encoding="utf-8")

    assert 'title: "First-time setup"' in source
    assert 'dashboardUrl("/?page=settings")' in source
