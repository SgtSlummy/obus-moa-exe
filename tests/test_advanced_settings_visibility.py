from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_advanced_settings_are_open_by_default_and_after_refresh() -> None:
    page = (ROOT / "backend" / "static" / "index.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "backend" / "static" / "aui" / "dashboard.js").read_text(encoding="utf-8")

    assert '<details id="guided-advanced-nav" class="guided-advanced-nav" open>' in page
    assert "const advanced=$('#guided-advanced-nav');if(advanced)advanced.open=true;" in dashboard
