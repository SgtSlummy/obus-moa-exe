#!/usr/bin/env python3
"""
Summarise the bottom <text> elements in every SVG file in key directory.
"""
from pathlib import Path
import re

def extract_footer(path):
    text = path.read_text(encoding='utf-8')
    lines = [ln for ln in text.splitlines()
             if '<text ' in ln and any(k in ln for k in ('y="3', 'SEAL', 'KEY', 'PUBLIC-DOMAIN'))]
    return '\n'.join(lines)

base = Path('/c/Users/Hermes/Documents/obus-moa-exe/backend/static/art/keys')
for p in sorted(base.glob('key-*.svg')):
    print(f'=== {p.name} ===')
    footer = extract_footer(p)
    if footer.strip():
        print(footer)
    else:
        print('(no bottom text found)')
    print()