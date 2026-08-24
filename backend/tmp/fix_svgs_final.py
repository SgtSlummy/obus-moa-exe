#!/usr/bin/env python3
"""
Batch-clean all 16 Solomon Key SVGs:
- Remove duplicate/old labels (provider bullet lines, SOLOMON KEY, footer)
- Insert new labels at safe spacing
- Validate final XML
"""
import re
import html
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path('backend/static/art/keys')

PROVIDER = {
    'key-anthropic.svg': 'ANTHROPIC',
    'key-azure-openai.svg': 'AZURE OPENAI',
    'key-cerebras.svg': 'CEREBRAS',
    'key-codex-oauth.svg': 'CODEX OAUTH',
    'key-deepseek.svg': 'DEEPSEEK',
    'key-fireworks.svg': 'FIREWORKS AI',
    'key-google-gemini.svg': 'GOOGLE GEMINI',
    'key-groq.svg': 'GROQ',
    'key-huggingface.svg': 'HUGGING FACE',
    'key-local-ollama.svg': 'OLLAMA',
    'key-mistral.svg': 'MISTRAL',
    'key-nous-oauth.svg': 'NOUS / SOLAR',
    'key-nvidia-nim.svg': 'NVIDIA NIM',
    'key-openrouter.svg': 'OPENROUTER',
    'key-together.svg': 'TOGETHER AI',
    'key-xai.svg': 'XAI',
}

Y_SEAL   = 340
Y_PROV   = 362
Y_SOL    = 377
Y_FOOTER = 393


def fix_svg(path: Path):
    txt = path.read_text(encoding='utf-8')

    # truncate at last </svg>
    idx = txt.rfind('</svg>')
    if idx == -1:
        raise RuntimeError('No closing </svg> found')

    txt = txt[:idx]  # everything before closing tag

    # parse and filter
    lines = txt.splitlines()
    seal_name, accent, number = None, None, None
    kept = []

    for line in lines:
        s = line.strip()

        # capture seal name (appears at y=345)
        if '<text' in s and 'y="345"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal_name = html.escape(m.group(1).strip())
            continue

        # capture number and colour from old SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_num = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_fill = re.search(r'fill="([^"]+)"', s)
            if m_num:
                number = int(m_num.group(1))
            if m_fill:
                accent = m_fill.group(1)
            continue

        # drop any existing provider label (contains bullet)
        if '<text' in s and '•' in s:
            continue

        # drop old public-domain footer
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue

        kept.append(line)

    if not seal_name:
        raise RuntimeError('Seal name missing')
    if number is None:
        raise RuntimeError('Key number missing')
    if not accent:
        accent = '#d9e1f2'

    provider = PROVIDER.get(path.name)
    if not provider:
        print(f'WARN: no provider mapping for {path.name}')
        provider = path.stem.replace('key-', '').upper().replace('_', ' ')

    nn = f"{number:02d}"

    footer = [
        f'<text x="200" y="{Y_SEAL}" text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif" font-size="21" font-weight="700" letter-spacing="3">{seal_name}</text>',
        f'<text x="200" y="{Y_PROV}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{provider} • {nn}</text>',
        f'<text x="200" y="{Y_SOL}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]

    new_svg = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'

    # validate
    ET.fromstring(new_svg)

    path.write_text(new_svg, encoding='utf-8')
    print(f'✓ Fixed {path.name}')


if __name__ == '__main__':
    ok = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        try:
            fix_svg(svg)
            ok += 1
        except Exception as e:
            print(f'✗ {svg.name}: {e}')
    print(f'\nFixed {ok}/16 SVGs')