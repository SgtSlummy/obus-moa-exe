from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_flow_studio_editor_links_to_settings_and_desktop_help() -> None:
    source = (ROOT / "backend" / "static" / "flow_studio.html").read_text(encoding="utf-8")

    assert 'Settings &amp; setup' in source
    assert 'href="/?page=settings"' in source
    assert 'Open OBus Settings' in source
    assert 'File → First-time setup' in source
    assert 'File → Run self-diagnosis' in source
