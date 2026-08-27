from pathlib import Path


def test_pyinstaller_spec_bundles_winpty_agent_for_frozen_shells():
    spec = (Path(__file__).parents[1] / "OBus.spec").read_text(encoding="utf-8")

    assert 'winpty_agent = winpty_dir / "winpty-agent.exe"' in spec
    assert 'binaries.append((str(winpty_agent), "winpty"))' in spec
