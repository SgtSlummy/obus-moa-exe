#!/usr/bin/env python3
"""
Fix all 16 SVG key files with safe vertical spacing.
Run this script to actually modify the files.
"""
import re, html, xml.etree.ElementTree as ET
from pathlib import Path

# Working directory
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

# Safe y-coordinates (baseline separation ~15-20px)
Y = dict(SEAL=340, PROV=362, SOL=377, FOOTER=393)

def fix_svg(path: Path) -> str:
    """Return '' on success, error string on failure."""
    raw = path.read_text(encoding='utf-8')

    # Truncate at last </svg>
    end = raw.rfind('</svg>')
    if end == -1:
        return f'no </svg> in {path.name}'
    raw = raw[:end]  # exclude the old closing tag

    lines = raw.splitlines()
    kept = []
    seal_name, accent, number = None, None, None

    for ln in lines:
        s = ln.strip()

        # Extract seal name from top provider title line
        if '<text' in s and 'y="37"' in s and 'font-size="16"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal_name = html.escape(m.group(1).strip())
            continue

        # Extract number & color from existing SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_num = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_fill = re.search(r'fill="([^"]+)"', s)
            if m_num:
                number = int(m_num.group(1))
            if m_fill:
                accent = m_fill.group(1)
            continue

        # Skip old provider labels (contain bullet)
        if '<text' in s and '•' in s:
            continue

        # Skip old PUBLIC-DOMAIN footer
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue

        kept.append(s)

    # Apply defaults
    if not seal_name:
        seal_name = 'SEAL'
    if number is None:
        number = 0
    if not accent:
        accent = '#d9e1f2'

    provider = PROVIDER.get(path.name)
    if not provider:
        return f'no provider mapping for {path.name}'

    nn = f'{number:02d}'

    # Build clean, non-overlapping footer
    footer = [
        f'<text x="200" y="{Y["SEAL"]}"   text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif"   font-size="21" font-weight="700" letter-spacing="3">{seal_name}</text>',
        f'<text x="200" y="{Y["PROV"]}"   text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{provider} • {nn}</text>',
        f'<text x="200" y="{Y["SOL"]}"    text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y["FOOTER"]}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]

    new_svg = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'

    # Validate XML
    try:
        ET.fromstring(new_svg)
    except ET.ParseError as e:
        return f'XML error: {e}'

    # Write to file
    path.write_text(new_svg, encoding='utf-8')
    return ''

if __name__ == '__main__':
    print('Fixing 16 SVG files...\n')
    done = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        err = fix_svg(svg)
        if err:
            print(f'✗ {svg.name}: {err}')
        else:
            print(f'✓ {svg.name}')
            done += 1
    print(f'\nFixed {done}/16 SVG files')