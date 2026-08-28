"""Small, packaging-safe capability checks shared by local voice routes."""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def faster_whisper_available() -> bool:
    """Check the bundled transcriber without loading a speech model.

    ``importlib.util.find_spec`` can return ``None`` for hidden imports in a
    PyInstaller executable even when the module is bundled.  Importing the module
    verifies the actual runtime capability while model construction remains lazy.
    """

    try:
        from faster_whisper import WhisperModel
    except (ImportError, OSError):
        return False
    return WhisperModel is not None
