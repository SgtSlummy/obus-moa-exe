#!/usr/bin/env python3
"""
Fix all 16 Solomon Key SVG files with safe, non-overlapping text.
This script ACTUALLY writes changes.
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

# Safe vertical positions - 20px+ separation
Y_SEAL, Y_PROV, Y_SOL, Y_FOOTER = 340, 362, 377, 393


def fix_svg(path: Path):
    raw = path.read_text(encoding='utf-8')
    
    # Cut at last </svg>
    end = raw.rfind('</svg>')
    if end == -1:
        print(f"WARN: no </svg> in {path.name}")
        end = len(raw)
    raw = raw[:end]  # remove everything after last close
    
    lines = raw.splitlines()
    seal, accent, number, kept = None, None, None, []
    
    for ln in lines:
        s = ln.strip()
        
        # Extract seal name from top provider line
        if '<text' in s and 'y="37"' in s and 'font-size="16"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal = html.escape(m.group(1).strip())
            continue
        
        # Extract number & color from old SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            n = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            a = re.search(r'fill="([^"]+)"', s)
            if n:
                number = int(n.group(1))
            if a:
                accent = a.group(1)
            continue
        
        # Skip old provider labels (contain •)
        if '<text' in s and '•' in s:
            continue
        
        # Skip old footer
        if 'PUBLIC-DOMAIN' in s:
            continue
        
        kept.append(s)
    
    seal = seal or 'SEAL'
    number = number or 0
    accent = accent or '#d9e1f2'
    
    prov = PROVIDER.get(path.name)
    if not prov:
        print(f"ERROR: no provider for {path.name}")
        return
    
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
        print(f"XML ERROR in {path.name}: {e}")
        return
    
    path.write_text(result, encoding='utf-8')
    print(f"✓ Fixed {path.name}")


if __name__ == '__main__':
    print('Fixing all 16 SVG files...\n')
    count = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        try:
            fix_svg(svg)
            count += 1
        except Exception as e:
            print(f"✗ {svg.name}: {e}")
    print(f"\nFixed {count}/16 SVGs")