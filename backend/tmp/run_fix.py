#!/usr/bin/env python3
"""
FIXED SVG cleanup - runs the actual fix, not just writes the script.
"""
import re, html, xml.etree.ElementTree as ET
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

# Safe, non-overlapping y positions
Y = dict(SEAL=340, PROV=362, SOL=377, FOOTER=393)

def fix(path: Path):
    raw = path.read_text(encoding='utf-8')
    end = raw.rfind('</svg>')
    if end == -1:
        return f'no svg close'
    raw = raw[:end]
    
    seal, accent, number, kept = None, None, None, []
    
    for ln in raw.splitlines():
        s = ln.strip()
        
        # Get seal name from y=345
        if '<text' in s and 'y="345"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal = html.escape(m.group(1).strip())
            continue
        
        # Get number & color from old SOLOMON KEY line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_n = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_a = re.search(r'fill="([^"]+)"', s)
            if m_n:
                number = int(m_n.group(1))
            if m_a:
                accent = m_a.group(1)
            continue
        
        # Skip any old provider labels and footer
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
        return f'no provider for {path.name}'
    
    nn = f'{number:02d}'
    footer = [
        f'<text x="200" y="{Y["SEAL"]}" text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif" font-size="21" font-weight="700" letter-spacing="3">{seal}</text>',
        f'<text x="200" y="{Y["PROV"]}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{prov} • {nn}</text>',
        f'<text x="200" y="{Y["SOL"]}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y["FOOTER"]}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]
    
    result = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'
    
    try:
        ET.fromstring(result)
    except ET.ParseError as e:
        return f'XML: {e}'
    
    path.write_text(result, encoding='utf-8')
    return ''

if __name__ == '__main__':
    print('Fixing 16 SVG files...\n')
    done = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        err = fix(svg)
        if err:
            print(f'✗ {svg.name}: {err}')
        else:
            print(f'✓ {svg.name}')
            done += 1
    print(f'\nFixed {done}/16 SVGs')