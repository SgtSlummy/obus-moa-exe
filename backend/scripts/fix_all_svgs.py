#!/usr/bin/env python3
"""
Clean all 16 Solomon Key SVGs: fix duplicate/conflicting labels, enforce spacing.

After running this, each SVG has exactly:
- demon/seal name at y=340
- "PROVIDER • NN" at y=362  (10px, 600 weight)
- "SOLOMON KEY · NN" at y=377 (11px)
- "PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK" at y=393 (7px)
- </svg> as final element
"""
import re
import html
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path('.').resolve() / 'backend' / 'static' / 'art' / 'keys'

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


def fix(path: Path):
    txt = path.read_text(encoding='utf-8')

    # truncate to last </svg>
    idx = txt.rfind('</svg>')
    if idx == -1:
        raise RuntimeError("No closing </svg>")

    txt = txt[:idx + 7]

    # split into lines and analyse
    lines = txt.splitlines()
    seal_name, accent, number = None, None, None
    kept = []

    for ln in lines:
        s = ln.strip()

        # capture seal name
        if '<text' in s and 'y="345"' in s:
            m = re.search(r'>([^<>]+)</text>', s)
            if m:
                seal_name = m.group(1).strip()
            continue

        # capture number & accent from old SOLOMON line
        if '<text' in s and 'SOLOMON KEY' in s:
            m_n = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', s)
            m_a = re.search(r'fill="([^"]+)"', s)
            if m_n:
                number = int(m_n.group(1))
            if m_a:
                accent = m_a.group(1)
            continue

        # drop old provider label
        if '<text' in s and '•' in s:
            continue

        # drop old footer
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in s:
            continue

        kept.append(ln)

    if not seal_name:
        raise RuntimeError("Could not find seal name")
    if not number:
        raise RuntimeError("Could not find key number")
    if not accent:
        accent = '#d9e1f2'

    prov = PROVIDER.get(path.name)
    if not prov:
        raise RuntimeError(f"Missing provider for {path.name}")

    nn = f"{number:02d}"

    # build new footer
    footer = [
        f'<text x="200" y="{Y_SEAL}" text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif" font-size="21" font-weight="700" letter-spacing="3">{html.escape(seal_name)}</text>',
        f'<text x="200" y="{Y_PROV}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{prov} • {nn}</text>',
        f'<text x="200" y="{Y_SOL}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]

    final = '\n'.join(kept) + '\n' + '\n'.join(footer) + '\n'

    # validate
    ET.fromstring(final)

    path.write_text(final, encoding='utf-8')
    print(f"✓ {path.name}")


if __name__ == '__main__':
    fixed = 0
    for svg in sorted(BASE.glob('key-*.svg')):
        try:
            fix(svg)
            fixed += 1
        except Exception as e:
            print(f"✗ {svg.name}: {e}")

    print(f"\nFixed {fixed} files")