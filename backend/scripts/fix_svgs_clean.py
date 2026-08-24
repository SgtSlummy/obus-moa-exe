#!/usr/bin/env python3
"""
Atomic SVG cleanup: fixes all 16 key files with exact, non-overlapping text.
Reads each file, extracts seal name/number/color, rewrites footer with clean spacing.
"""
import re
import html
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

Y_SEAL   = 340   # seal name (21px Georgia serif)
Y_PROV   = 362   # provider • NN (10px Semibold)
Y_SOL    = 377   # SOLOMON KEY (11px)
Y_FOOTER = 393   # footer (7px)

def fix(path: Path) -> str:
    """Returns empty string on success, or error message."""
    raw = path.read_text(encoding='utf-8')

    # Find last closing tag and truncate everything after it
    end = raw.rfind('</svg>')
    if end == -1:
        return f'no </svg> found'

    raw = raw[:end]  # strip original footer entirely

    # Now walk lines, collecting everything and extracting required values
    lines = raw.splitlines()
    seal_name = None
    accent = None
    number = None
    kept = []

    for ln in lines:
        s = ln.strip()

        # Capture seal name from y="345" position
        if '<text' in s and 'y="345"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal_name = html.escape(m.group(1).strip())
            continue

        # Extract key number and accent from existing SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_num = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_fill = re.search(r'fill="([^"]+)"', s)
            if m_num:
                number = int(m_num.group(1))
            if m_fill:
                accent = m_fill.group(1)
            continue

        # Discard any old provider labels (contain bullet "•")
        if '<text' in s and '•' in s:
            continue

        # Discard old footer
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue

        kept.append(ln)

    # Fill defaults
    if not seal_name:
        seal_name = 'SEAL'
    if number is None:
        number = 0
    if not accent:
        accent = '#d9e1f2'

    provider = PROVIDER.get(path.name)
    if not provider:
        return f'unknown provider for {path.name}'

    nn = f'{number:02d}'

    # Build new footer with exact spacing
    new_footer = [
        f'<text x="200" y="{Y_SEAL}"   text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif"   font-size="21" font-weight="700" letter-spacing="3">{seal_name}</text>',
        f'<text x="200" y="{Y_PROV}"   text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{provider} • {nn}</text>',
        f'<text x="200" y="{Y_SOL}"    text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]

    result = '\n'.join(kept) + '\n' + '\n'.join(new_footer) + '\n'

    # Prove the XML is valid
    try:
        ET.fromstring(result)
    except ET.ParseError as e:
        return f'XML error: {e}'

    # Write the fixed file
    path.write_text(result, encoding='utf-8')
    return ''


if __name__ == '__main__':
    print('Fixing all 16 SVG files...\n')
    count_ok = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        err = fix(svg)
        if err:
            print(f'✗ {svg.name}: {err}')
        else:
            print(f'✓ {svg.name}')
            count_ok += 1
    print(f'\nFixed {count_ok}/16 SVG files successfully.')