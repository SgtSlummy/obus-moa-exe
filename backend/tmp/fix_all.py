#!/usr/bin/env python3
"""
Fix all 16 Solomon Key SVG files:
- Remove duplicates (lines with "•")
- Position text cleanly with no overlap
- Validate XML output
"""
from pathlib import Path
import re
import html
import xml.etree.ElementTree as ET

BASE = Path('/c/Users/Hermes/Documents/obus-moa-exe/backend/static/art/keys')

# provider -> display name (note CEREBRAS, not CERBRAS)
PROVIDER = {
    'key-anthropic.svg':   'ANTHROPIC',
    'key-azure-openai.svg': 'AZURE OPENAI',
    'key-cerebras.svg':    'CEREBRAS',
    'key-codex-oauth.svg': 'CODEX OAUTH',
    'key-deepseek.svg':    'DEEPSEEK',
    'key-fireworks.svg':   'FIREWORKS AI',
    'key-google-gemini.svg': 'GOOGLE GEMINI',
    'key-groq.svg':        'GROQ',
    'key-huggingface.svg': 'HUGGING FACE',
    'key-local-ollama.svg': 'OLLAMA',
    'key-mistral.svg':     'MISTRAL',
    'key-nous-oauth.svg':  'NOUS / SOLAR',
    'key-nvidia-nim.svg':  'NVIDIA NIM',
    'key-openrouter.svg':  'OPENROUTER',
    'key-together.svg':    'TOGETHER AI',
    'key-xai.svg':         'XAI',
}

Y_SEAL   = 340  # seal/demon name
Y_PROV   = 362  # provider • NN (10px with 600 weight)
Y_SOL    = 377  # SOLOMON KEY (11px)
Y_FOOTER = 393  # PUBLIC-DOMAIN footer (7px)


def clean_svg(path: Path) -> None:
    txt = path.read_text(encoding='utf-8')

    # truncate at last </svg>
    end = txt.rfind('</svg>')
    if end == -1:
        raise RuntimeError(f"No </svg> in {path}")
    txt = txt[:end + 7]

    lines = txt.splitlines()

    seal   = None
    accent = None
    number = None
    kept   = []

    for ln in lines:
        s = ln.strip()

        # seal name at y=345 (originally)
        if '<text' in s and 'y="345"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal = html.escape(m.group(1).strip())
            continue

        # extract number and accent from old SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_num = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_fill = re.search(r'fill="([^"]+)"', s)
            if m_num:
                number = int(m_num.group(1))
            if m_fill:
                accent = m_fill.group(1)
            continue

        # skip any old provider label (has •)
        if '<text' in s and '•' in s and 'PUBLIC-DOMAIN' not in s:
            continue

        # skip old PUBLIC-DOMAIN footer (will be rebuilt)
        if '<text' in s and 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue

        kept.append(ln)

    if not seal:
        seal = 'SEAL'
    if number is None:
        number = 0
    if not accent:
        accent = '#d9e1f2'

    prov = PROVIDER.get(path.name)
    if not prov:
        raise RuntimeError(f"No provider for {path}")

    nn = f"{number:02d}"

    footer = [
        f'<text x="200" y="{Y_SEAL}" text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif" font-size="21" font-weight="700" letter-spacing="3">{seal}</text>',
        f'<text x="200" y="{Y_PROV}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{prov} • {nn}</text>',
        f'<text x="200" y="{Y_SOL}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>',
    ]

    result = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'

    # XML validation
    try:
        ET.fromstring(result)
    except ET.ParseError as e:
        raise RuntimeError(f"Invalid XML after fix: {e}")

    path.write_text(result, encoding='utf-8')
    print(f"✓ {path.name}")


if __name__ == '__main__':
    count = 0
    for p in sorted(BASE.glob('key-*.svg')):
        try:
            clean_svg(p)
            count += 1
        except Exception as e:
            print(f"✗ {p.name}: {e}")
    print(f"\nFixed {count}/16 SVGs")