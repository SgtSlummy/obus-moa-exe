#!/usr/bin/env python3
"""
Final fix: clean all 16 Soloman Key SVGs with safe, non-overlapping text spacing.
"""
import re
import html
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path('/c/Users/Hermes/Documents/obus-moa-exe/backend/static/art/keys')

# exact provider labels
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

# desired y-coords (baseline spacing)
Y_SEAL   = 340
Y_PROV   = 362
Y_SOL    = 377
Y_FOOTER = 393


def main():
    for path in sorted(BASE.glob('key-*.svg')):
        txt = path.read_text(encoding='utf-8')

        # trim to last </svg>
        end = txt.rfind('</svg>')
        if end == -1:
            print(f'WARNING: no </svg> in {path.name}')
            end = len(txt)
        txt = txt[:end + 7]

        # collect info and filter old labels
        lines = txt.splitlines()
        seal_name, accent, number = None, None, None
        kept = []

        for ln in lines:
            s = ln.strip()

            # capture seal name (demon/angel name)
            if '<text' in s and 'y="345"' in s:
                m = re.search(r'>([^<>]+)</text>', s)
                if m:
                    seal_name = html.escape(m.group(1).strip())
                continue

            # capture number & colour from old SOLOMON KEY line
            if '<text' in s and 'SOLOMON KEY' in s:
                m_num = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
                m_fill = re.search(r'fill="([^"]+)"', s)
                if m_num:
                    number = int(m_num.group(1))
                if m_fill:
                    accent = m_fill.group(1)
                continue

            # drop any existing provider label (contains •)
            if '<text' in s and '•' in s:
                continue

            # drop old PUBLIC-DOMAIN footer
            if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
                continue

            kept.append(ln)

        if not seal_name:
            print(f'ERROR: seal name not found in {path.name}')
            continue
        if number is None:
            print(f'ERROR: key number not found in {path.name}')
            continue
        if not accent:
            accent = '#d9e1f2'

        provider = PROVIDER.get(path.name)
        if not provider:
            print(f'ERROR: no provider map for {path.name}')
            continue

        nn = f"{number:02d}"

        footer = [
            f'<text x="200" y="{Y_SEAL}" text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif" font-size="21" font-weight="700" letter-spacing="3">{seal_name}</text>',
            f'<text x="200" y="{Y_PROV}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{provider} • {nn}</text>',
            f'<text x="200" y="{Y_SOL}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
            f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
            '</svg>',
        ]

        new_svg = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'

        # XML validation
        try:
            ET.fromstring(new_svg)
        except ET.ParseError as e:
            print(f'XML ERROR in {path.name}: {e}')
            continue

        path.write_text(new_svg, encoding='utf-8')
        print(f'✓ Fixed {path.name}')

    print('\nDone.')

if __name__ == '__main__':
    main()