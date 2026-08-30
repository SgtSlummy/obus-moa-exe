from pathlib import Path

from tools.voice_link import relay_pad


def test_relay_pad_serves_its_bundled_client():
    assert (relay_pad.CLIENT_DIR / "index.html").is_file()
    page = (relay_pad.CLIENT_DIR / "index.html").read_text(encoding="utf-8")
    assert "OBus Relay Pad" in page
    assert "pointerdown" in page and "speechSynthesis.speak" in page
    assert "assistant:true" in page
