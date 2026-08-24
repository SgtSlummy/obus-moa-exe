#!/usr/bin/env python3
"""
Clean all 16 Solomon Key SVGs:
- Remove duplicate provider labels (lines containing "•")
- Ensure safe vertical spacing
- Produce valid XML
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

def fix(path: Path):
    raw = path.read_text(encoding='utf-8')
    end = raw.rfind('</svg>')
    if end == -1:
        raise ValueError('no </svg>')
    raw = raw[:end]  # strip original closing tag
    lines, seal, accent, number, kept = raw.splitlines(), None, None, None, []

    for ln in lines:
        s = ln.strip()

        # seal name at y=345
        if '<text' in s and 'y="345"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal = html.escape(m.group(1).strip())
            continue

        # extract number & color from old SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_n = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_a = re.search(r'fill="([^"]+)"', s)
            if m_n:
                number = int(m_n.group(1))
            if m_a:
                accent = m_a.group(1)
            continue

        # drop any provider label (contains •) or footer
        if '<text' in s and '•' in s:
            continue
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue

        kept.append(ln)

    seal = seal or 'SEAL'
    number = number or 0
    accent = accent or '#d9e1f2'
    prov = PROVIDER.get(path.name)
    if not prov:
        raise ValueError(f'no provider for {path.name}')

    nn = f'{number:02d}'
    footer = [
        f'<text x="200" y="{Y_SEAL}"   text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif"   font-size="21" font-weight="700" letter-spacing="3">{seal}</text>',
        f'<text x="200" y="{Y_PROV}"   text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{prov} • {nn}</text>',
        f'<text x="200" y="{Y_SOL}"    text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]

    result = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'
    ET.fromstring(result)  # validate XML
    path.write_text(result, encoding='utf-8')
    print(f'✓ {path.name}')

if __name__ == '__main__':
    fixed = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        try:
            fix(svg)
            fixed += 1
        except Exception as e:
            print(f'✗ {svg.name}: {e}')
    print(f'\nFixed {fixed}/16 SVG files')