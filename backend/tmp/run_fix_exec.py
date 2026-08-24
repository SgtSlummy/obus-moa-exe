#!/usr/bin/env python3
"""
Fix all 16 SVG key files with safe, non-overlapping text.
Executes fixes directly in cwd.
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

# Safe y-coordinates (baseline separation)
Y = { 'Seal': 340, 'Prov': 362, 'Sol': 377, 'Foot': 393 }


def fix_svg(path):
    raw = path.read_text(encoding='utf-8')
    
    # Truncate at last </svg>
    end = raw.rfind('</svg>')
    if end != -1:
        raw = raw[:end]
    
    lines = raw.splitlines()
    kept = []
    seal, accent, number = None, None, None
    
    for ln in lines:
        s = ln.strip()
        
        # Seal name from top line (y="37", font-size="16", font-weight="700")
        if '<text' in s and 'y="37"' in s and 'font-size="16"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal = html.escape(m.group(1).strip())
            continue
        
        # Extract number & color from existing SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_n = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_a = re.search(r'fill="([^"]+)"', s)
            if m_n:
                number = int(m_n.group(1))
            if m_a:
                accent = m_a.group(1)
            continue
        
        # Skip existing provider labels (contain •)
        if '<text' in s and '•' in s:
            continue
        
        # Skip old PUBLIC-DOMAIN footer
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue
        
        kept.append(s)
    
    # Defaults
    seal = seal or 'SEAL'
    number = number or 0
    accent = accent or '#d9e1f2'
    
    prov = PROVIDER.get(path.name)
    if not prov:
        print(f"SKIP {path.name}: no provider")
        return
    
    nn = f'{number:02d}'
    
    # Build clean, non-overlapping footer
    footer = [
        f'<text x="200" y="{Y["Seal"]}"   text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif"   font-size="21" font-weight="700" letter-spacing="3">{seal}</text>',
        f'<text x="200" y="{Y["Prov"]}"   text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{prov} • {nn}</text>',
        f'<text x="200" y="{Y["Sol"]}"    text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y["Foot"]}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]
    
    new_svg = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'
    
    # Validate
    try:
        ET.fromstring(new_svg)
    except ET.ParseError as e:
        print(f'XML ERROR {path.name}: {e}')
        return
    
    path.write_text(new_svg, encoding='utf-8')
    print(f'✓ {path.name}')


if __name__ == '__main__':
    print('Fixing all 16 SVG files...\n')
    count = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        fix_svg(svg)
        count += 1
    print(f'\nFixed {count}/16 SVGs')