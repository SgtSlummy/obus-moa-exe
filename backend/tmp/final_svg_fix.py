#!/usr/bin/env python3
"""
Final SVG cleanup – fixes ALL 16 key files in one pass.

Algorithm:
1. Read each SVG up to the last </svg> tag.
2. Remove any bottom <text> lines that:
   - contain a provider label (the • bullet)
   - contain "SOLOMON KEY"
   - contain "PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK"
3. Preserve everything else (top title, seal image, etc.)
4. Append clean, non-overlapping footer lines at exact positions:
   seal@340, provider@362, key@377, footer@393
5. Append one </svg> and validate XML.
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

Y = dict(SEAL=340, PROV=362, SOL=377, FOOTER=393)


def fix(path: Path):
    raw = path.read_text(encoding='utf-8')
    end = raw.rfind('</svg>')
    if end == -1:
        raise ValueError('No </svg>')
    raw = raw[:end]  # everything up to last closing tag

    lines = raw.splitlines()
    seal_name, accent, number = None, None, None
    kept = []

    for ln in lines:
        s = ln.strip()

        if '<text' in s and 'y="345"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal_name = html.escape(m.group(1).strip())
            continue

        if '<text' in s and 'SOLOMON KEY' in s:
            m_n = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_a = re.search(r'fill="([^"]+)"', s)
            if m_n:
                number = int(m_n.group(1))
            if m_a:
                accent = m_a.group(1)
            continue

        # skip provider labels and old footer
        if '•' in s and '<text' in s:
            continue
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue

        kept.append(ln)

    if not seal_name:
        seal_name = 'SEAL'
    if number is None:
        number = 0
    if not accent:
        accent = '#d9e1f2'

    prov = PROVIDER.get(path.name)
    if not prov:
        raise ValueError(f'No provider: {path.name}')

    nn = f'{number:02d}'
    footer = [
        f'<text x="200" y="{Y["SEAL"]}"   text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif"   font-size="21" font-weight="700" letter-spacing="3">{seal_name}</text>',
        f'<text x="200" y="{Y["PROV"]}"   text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{prov} • {nn}</text>',
        f'<text x="200" y="{Y["SOL"]}"    text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y["FOOTER"]}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]

    new_svg = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'
    ET.fromstring(new_svg)  # validate
    path.write_text(new_svg, encoding='utf-8')
    print(f'✓ {path.name}')


if __name__ == '__main__':
    ok = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        try:
            fix(svg)
            ok += 1
        except Exception as e:
            print(f'✗ {svg.name}: {e}')
    print(f'\nFixed {ok}/16 SVGs')