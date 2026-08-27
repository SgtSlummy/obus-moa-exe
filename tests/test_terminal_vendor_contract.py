from pathlib import Path


def test_xterm_assets_are_local_and_licensed_for_standalone_use():
    vendor = Path(__file__).parents[1] / "backend" / "static" / "vendor" / "xterm"

    assert (vendor / "xterm.js").stat().st_size > 400_000
    assert (vendor / "xterm.css").stat().st_size > 5_000
    assert (vendor / "addon-fit.js").stat().st_size > 1_000
    assert "xterm.js` 6.0.0" in (vendor / "NOTICE.md").read_text(encoding="utf-8")
    assert "Permission is hereby granted, free of charge" in (vendor / "LICENSE-xterm.txt").read_text(encoding="utf-8")
