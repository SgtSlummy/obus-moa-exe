#!/usr/bin/env python3
"""
FIX ALL 16 SVG FILES - THIS SCRIPT RUNS AND MODIFIES FILES.

Strategy:
1. Read each SVG up to (but not including) the last </svg>
2. Remove old:
   - provider labels containing "•"
   - "SOLOMON KEY" line
   - "PUBLIC-DOMAIN..." footer
3. Extract seal name, key number, and accent colour from remaining context lines
4. Append clean, non-overlapping footer:
   y=340  seal name   font-size=21  Georgia 700
   y=362  provider•NN font-size=10  Segoe UI 600
   y=377  SOLOMON KEY font-size=11  Segoe UI regular
   y=393  footer      font-size=7   Segoe UI light
5. Add single </svg>
6. Validate XML
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

def fix(path: Path) -> str:
    """Returns '' on success, error message on failure."""
    raw = path.read_text(encoding='utf-8')
    end = raw.rfind('</svg>')
    if end == -1:
        return 'no closing </svg>'
    raw = raw[:end]  # truncate before original close tag

    lines = raw.splitlines()
    seal, accent, number, kept = None, None, None, []

    for ln in lines:
        s = ln.strip()

        # Extract seal name from top-level title line
        if '<text' in s and 'y="37"' in s and 'font-size="16"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal = html.escape(m.group(1).strip())
            continue

        # Extract number & accent from old SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_n = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_a = re.search(r'fill="([^"]+)"', s)
            if m_n:
                number = int(m_n.group(1))
            if m_a:
                accent = m_a.group(1)
            continue

        # Skip old provider labels (contain •)
        if '<text' in s and '•' in s:
            continue

        # Skip old footer
        if 'PUBLIC-DOMAIN' in s:
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
        return f'no provider for {path.name}'

    nn = f'{number:02d}'
    footer = [
        f'<text x="200" y="{Y_SEAL}"   text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif"   font-size="21" font-weight="700" letter-spacing="3">{seal}</text>',
        f'<text x="200" y="{Y_PROV}"   text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{prov} • {nn}</text>',
        f'<text x="200" y="{Y_SOL}"    text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]

    result = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'

    # Validate XML
    try:
        ET.fromstring(result)
    except ET.ParseError as e:
        return f'bad XML: {e}'

    path.write_text(result, encoding='utf-8')
    return ''


if __name__ == '__main__':
    count = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        err = fix(svg)
        if err:
            print(f'✗ {svg.name}: {err}')
        else:
            print(f'✓ {svg.name}')
            count += 1
    print(f'\nFixed {count}/16 SVGs')