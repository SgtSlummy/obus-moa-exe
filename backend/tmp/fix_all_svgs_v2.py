#!/usr/bin/env python3
"""
Fix all 16 Solomon Key SVG files:
- Remove all duplicate/wrong provider labels
- Position text at safe, non-overlapping y-coordinates
- Validate XML after every write
- Report any anomalies
"""
import re
import html
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path('backend/static/art/keys')

PROVIDER = {
    'key-anthropic.svg':   'ANTHROPIC',
    'key-azure-openai.svg':  'AZURE OPENAI',
    'key-cerebras.svg':      'CEREBRAS',   # NOT "CERBRAS" typo
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

# desired baseline positions
Y_SEAL   = 340  # demon/seal name (Georgia 21px)
Y_PROV   = 362  # provider • NN (Segoe UI 10px Semibold)
Y_SOL    = 378  # SOLOMON KEY (Segoe UI 11px)
Y_FOOTER = 394  # PUBLIC-DOMAIN (Segoe UI 7px)


def fix_file(path: Path) -> None:
    raw = path.read_text(encoding='utf-8')

    # Truncate at last </svg>
    last_svg = raw.rfind('</svg>')
    if last_svg == -1:
        raise RuntimeError(f'No </svg> found in {path}')
    raw = raw[:last_svg]  # remove the original closing tag

    lines = raw.splitlines()

    seal_name = None
    accent    = None
    number    = None
    kept      = []

    for line in lines:
        s = line.strip()

        # Capture seal name (currently at y="345")
        if '<text' in s and 'y="345"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal_name = html.escape(m.group(1).strip())
            continue

        # Capture number & colour from existing SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_num = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_fill = re.search(r'fill="([^"]+)"', s)
            if m_num:
                number = int(m_num.group(1))
            if m_fill:
                accent = m_fill.group(1)
            continue

        # Drop any existing provider labels (contain bullet "•")
        if '<text' in s and '•' in s:
            continue

        # Drop old footer
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue

        kept.append(line)

    # Fallbacks
    if not seal_name:
        seal_name = 'SEAL'
    if number is None:
        number = 0
    if not accent:
        accent = '#d9e1f2'

    provider = PROVIDER.get(path.name)
    if not provider:
        raise RuntimeError(f'No provider mapping for {path.name}')

    nn = f'{number:02d}'

    footer = [
        f'<text x="200" y="{Y_SEAL}"   text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif"   font-size="21" font-weight="700" letter-spacing="3">{seal_name}</text>',
        f'<text x="200" y="{Y_PROV}"   text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{provider} • {nn}</text>',
        f'<text x="200" y="{Y_SOL}"    text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>',
    ]

    new_svg = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'

    # Validate XML
    try:
        ET.fromstring(new_svg)
    except ET.ParseError as e:
        raise RuntimeError(f'Invalid XML: {e}')

    path.write_text(new_svg, encoding='utf-8')
    print(f'✓ {path.name}')


if __name__ == '__main__':
    done = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        try:
            fix_file(svg)
            done += 1
        except Exception as e:
            print(f'✗ {svg.name}: {e}')

    print(f'\nFixed {done}/16 SVG files')
    if done == 16:
        print('All files cleaned and validated.')