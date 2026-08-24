#!/usr/bin/env python3
"""
Fix all 16 SVG files with safe, non-overlapping text.

This script:
1. Reads each SVG, discards everything after (and including) the first </svg>
2. Extracts seal name, key number, accent color
3. Drops old provider lines (containing •), old SOLOMON KEY line, old footer
4. Writes clean footer at exact safe y-positions
5. Appends exactly one </svg>
6. Validates XML after every write
"""
import re, html
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path('backend/static/art/keys')

PROVIDER = {
    'key-anthropic.svg':   'ANTHROPIC',
    'key-azure-openai.svg':  'AZURE OPENAI',
    'key-cerebras.svg':      'CEREBRAS',
    'key-codex-oauth.svg':   'CODEX OAUTH',
    'key-deepseek.svg':      'DEEPSEEK',
    'key-fireworks.svg':     'FIREWORKS AI',
    'key-google-gemini.svg': 'GOOGLE GEMINI',
    'key-groq.svg':          'GROQ',
    'key-huggingface.svg':   'HUGGING FACE',
    'key-local-ollama.svg':  'OLLAMA',
    'key-mistral.svg':       'MISTRAL',
    'key-nous-oauth.svg':    'NOUS / SOLAR',
    'key-nvidia-nim.svg':    'NVIDIA NIM',
    'key-openrouter.svg':    'OPENROUTER',
    'key-together.svg':      'TOGETHER AI',
    'key-xai.svg':           'XAI',
}

Y_SEAL, Y_PROV, Y_SOL, Y_FOOTER = 340, 362, 377, 393


def fix_svg(path: Path) -> str:
    """Returns '' on success, error message on failure."""
    raw = path.read_text(encoding='utf-8')

    # Truncate at last </svg>
    last_close = raw.rfind('</svg>')
    if last_close == -1:
        return 'no </svg> found'
    raw = raw[:last_close]  # everything before the closing tag

    lines = raw.splitlines()
    kept = []
    seal_name, accent, number = None, None, None

    for ln in lines:
        s = ln.strip()

        # Seal name at top (y=37, font-size=16, font-weight=700)
        if '<text' in s and 'y="37"' in s and 'font-size="16"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal_name = html.escape(m.group(1).strip())
            continue

        # Number & accent from old SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_n = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_a = re.search(r'fill="([^"]+)"', s)
            if m_n:
                number = int(m_n.group(1))
            if m_a:
                accent = m_a.group(1)
            continue

        # Skip any old provider lines (contain bullet •)
        if '<text' in s and '•' in s:
            continue

        # Skip old PUBLIC-DOMAIN footer
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue

        kept.append(s)

    # Defaults
    if not seal_name:
        seal_name = 'SEAL'
    if number is None:
        number = 0
    if not accent:
        accent = '#d9e1f2'

    prov = PROVIDER.get(path.name)
    if not prov:
        return f'no provider for {path.name}'

    nn = f'{number:02d}'

    # Build non-overlapping footer
    footer = [
        f'<text x="200" y="{Y_SEAL}"   text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif"   font-size="21" font-weight="700" letter-spacing="3">{seal_name}</text>',
        f'<text x="200" y="{Y_PROV}"   text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{prov} • {nn}</text>',
        f'<text x="200" y="{Y_SOL}"    text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]

    result = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'

    # XML validation
    try:
        ET.fromstring(result)
    except ET.ParseError as e:
        return f'XML error: {e}'

    path.write_text(result, encoding='utf-8')
    return ''


if __name__ == '__main__':
    print('Fixing all 16 SVG files...\n')
    fixed = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        err = fix_svg(svg)
        if err:
            print(f'✗ {svg.name}: {err}')
        else:
            print(f'✓ {svg.name}')
            fixed += 1
    print(f'\nFixed {fixed}/16 SVG files')