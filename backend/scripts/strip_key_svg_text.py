#!/usr/bin/env python3
"""Remove visible labels from Solomon Key SVG art.

Provider, seal, model, context, and provenance copy belongs in the HTML card
below the image. SVG title/description metadata remains for provenance and
accessibility; only rendered <text> elements are removed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path


KEY_DIR = Path(__file__).resolve().parents[1] / "static" / "art" / "keys"
TEXT_ELEMENT = re.compile(r"\s*<text\b[^>]*>.*?</text>\s*", re.IGNORECASE | re.DOTALL)


def strip_visible_text(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    closing_index = original.rfind("</svg>")
    if closing_index < 0:
        raise ValueError(f"Missing closing </svg>: {path.name}")
    bounded = original[: closing_index + len("</svg>")]
    cleaned = TEXT_ELEMENT.sub("\n", bounded)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).rstrip() + "\n"
    root = ET.fromstring(cleaned)
    if any(node.tag.rsplit("}", 1)[-1] == "text" for node in root.iter()):
        raise ValueError(f"Visible text remains in {path.name}")
    if cleaned == original:
        return False
    path.write_text(cleaned, encoding="utf-8")
    return True


def main() -> int:
    paths = sorted(KEY_DIR.glob("key-*.svg"))
    if len(paths) != 16:
        raise RuntimeError(f"Expected 16 built-in Key SVGs, found {len(paths)}")
    changed = sum(strip_visible_text(path) for path in paths)
    print(f"Removed visible labels from {changed}/{len(paths)} Key SVGs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
