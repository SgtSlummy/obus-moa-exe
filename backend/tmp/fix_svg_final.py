#!/usr/bin/env python3
"""
Clean, validate, and generate a visual gallery for the 16 Solomon Key SVGs.
All bottom labels are repositioned to avoid overlap.
"""
from pathlib import Path
import re
import html
import xml.etree.ElementTree as ET

# -------------------------------------------------------------------------
base = Path('/c/Users/Hermes/Documents/obus-moa-exe/backend/static/art/keys')

PROVIDER_DISPLAY = {
    "key-anthropic.svg": "ANTHROPIC",
    "key-azure-openai.svg": "AZURE OPENAI",
    "key-cerebras.svg": "CEREBRAS",
    "key-codex-oauth.svg": "CODEX OAUTH",
    "key-deepseek.svg": "DEEPSEEK",
    "key-fireworks.svg": "FIREWORKS AI",
    "key-google-gemini.svg": "GOOGLE GEMINI",
    "key-groq.svg": "GROQ",
    "key-huggingface.svg": "HUGGING FACE",
    "key-local-ollama.svg": "OLLAMA",
    "key-mistral.svg": "MISTRAL",
    "key-nous-oauth.svg": "NOUS / SOLAR",
    "key-nvidia-nim.svg": "NVIDIA NIM",
    "key-openrouter.svg": "OPENROUTER",
    "key-together.svg": "TOGETHER AI",
    "key-xai.svg": "XAI",
}

Y_SEAL   = 340  # demon/seal name
Y_PROV   = 362  # provider • NN
Y_SOL    = 378  # SOLOMON KEY · NN
Y_FOOTER = 393  # PUBLIC-DOMAIN footer


def strip_providers(text: str) -> str:
    """Remove any existing provider labels (lines containing '•')."""
    lines = text.splitlines()
    return '\n'.join(ln for ln in lines if '•' not in ln or 'PUBLIC-DOMAIN' in ln)


def extract_seal_info(path: Path) -> tuple[str, str, int]:
    """Extract seal name, accent colour, and key number from SVG."""
    raw = path.read_text(encoding='utf-8')
    seal_name, accent, number = None, None, None

    for line in raw.splitlines():
        if '<text' in line and 'y="345"' in line:
            m = re.search(r'>([^<>]+)</text>', line)
            if m:
                seal_name = m.group(1).strip()
        if '<text' in line and 'SOLOMON KEY' in line:
            m_num = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', line)
            m_fill = re.search(r'fill="([^"#]+)"', line)
            if m_num:
                number = int(m_num.group(1))
            if m_fill:
                accent = m_fill.group(1)
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in line:
            break

    if not seal_name:
        seal_name = "SEAL"
    if not number:
        number = 0
    if not accent:
        accent = "#d9e1f2"

    return seal_name, accent, number


def build_footer(seal: str, accent: str, number: int, provider: str) -> list[str]:
    nn = f"{number:02d}"
    return [
        f'<text x="200" y="{Y_SEAL}" text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif" font-size="21" font-weight="700" letter-spacing="3">{html.escape(seal)}</text>',
        f'<text x="200" y="{Y_PROV}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{html.escape(provider)} • {nn}</text>',
        f'<text x="200" y="{Y_SOL}" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        f'<text x="200" y="{Y_FOOTER}" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>',
    ]


def clean_and_fix(path: Path) -> None:
    """Strip all bottom labels, rebuild them with safe spacing."""
    text = path.read_text(encoding='utf-8')

    # Cut at the last </svg>
    end = text.rfind('</svg>')
    if end == -1:
        raise RuntimeError(f"No closing SVG in {path}")
    text = text[:end + 7]

    # Remove existing provider labels (the ones with "•")
    good_lines = []
    for ln in text.splitlines():
        if '<text' in ln and '•' in ln and 'PUBLIC-DOMAIN' not in ln:
            continue  # skip old provider labels
        if '<text' in ln and 'SOLOMON KEY' not in ln and 'PUBLIC-DOMAIN' not in ln and 'y="345"' not in ln:
            # keep seal name, image, etc
            good_lines.append(ln)
        elif 'SOLOMON KEY' in ln:
            continue  # skip old solomon line
        else:
            good_lines.append(ln)

    seal, accent, number = extract_seal_info(path)
    provider = PROVIDER_DISPLAY.get(path.name)
    if not provider:
        raise RuntimeError(f"Missing provider mapping for {path.name}")

    footer = build_footer(seal, accent, number, provider)
    final = '\n'.join(good_lines) + '\n' + '\n'.join(footer) + '\n'

    # Validate XML
    try:
        ET.fromstring(final)
    except ET.ParseError as e:
        raise RuntimeError(f"Bad XML after fix: {e}")

    path.write_text(final, encoding='utf-8')
    print(f"✓ {path.name}")


# -------------------------------------------------------------------------
if __name__ == '__main__':
    count = 0
    for p in sorted(base.glob('key-*.svg')):
        try:
            clean_and_fix(p)
            count += 1
        except Exception as ex:
            print(f"✗ {p.name}: {ex}")
    print(f"\nFixed {count}/16 SVGs.")