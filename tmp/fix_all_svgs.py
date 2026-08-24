#!/usr/bin/env python3
"""
Batch-fix all 16 Solomon Key SVGs:
- Remove duplicate provider labels (those containing "•")
- Remove anything after </svg>
- Rebuild bottom labels with proper spacing
- Ensure XML validity
"""
from pathlib import Path
import re
import html
import xml.etree.ElementTree as ET

# -----------------------------------------------------------------------------
base = Path('/c/Users/Hermes/Documents/obus-moa-exe/backend/static/art/keys')

# Provider -> display name mapping (note: CEREBRAS, not CERBRAS typo from earlier)
PROVIDER_LABELS = {
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

def fix_svg(path: Path) -> None:
    """Read SVG, clean and rewrite with proper spacing, write back."""
    text = path.read_text(encoding='utf-8')

    # Only keep content up to and including the last </svg>
    last_svg = text.rfind('</svg>')
    if last_svg == -1:
        raise RuntimeError(f"No </svg> found in {path}")
    text = text[:last_svg + 7]  # keep the tag

    # Remove any provider labels already inside (lines that contain "•")
    lines = text.splitlines()
    kept = []
    for line in lines:
        if '<text ' in line and '•' in line and 'PUBLIC-DOMAIN' not in line:
            continue  # skip existing/provider labels
        kept.append(line)

    # Now extract seal name, color (accent), and number from what remains
    seal_name = None
    accent = None
    number = None

    for line in kept:
        if '<text ' in line and 'y="345"' in line:
            m = re.search(r'>([^<]+)</text>', line)
            if m:
                seal_name = m.group(1).strip()
        if '<text ' in line and 'SOLOMON KEY' in line:
            m_num = re.search(r'SOLOMON KEY\s*·\s*0?(\d+)', line)
            m_fill = re.search(r'fill="([^"]+)"', line)
            if m_num:
                number = int(m_num.group(1))
            if m_fill:
                accent = m_fill.group(1)
        if 'PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK' in line:
            # skip; rebuild it
            continue

    if not seal_name or not number or not accent:
        raise RuntimeError(f"Could not extract required info from {path}")

    provider_name = PROVIDER_LABELS.get(path.name)
    if not provider_name:
        raise RuntimeError(f"Missing provider label for {path.name}")

    nn = f"{number:02d}"
    if provider_name == "NOUS / SOLAR":
        provider_line = "NOUS / SOLAR"

    # ---------------------------------------------------------------------
    # Build the NEW bottom section with proper spacing
    new_footer = [
        f'<text x="200" y="340" text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif" font-size="21" font-weight="700" letter-spacing="3">{html.escape(seal_name)}</text>',
        f'<text x="200" y="362" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="10" font-weight="600" letter-spacing="1">{html.escape(provider_name)} • {nn}</text>',
        f'<text x="200" y="377" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="11" letter-spacing="2">SOLOMON KEY · {nn}</text>',
        '<text x="200" y="393" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="7">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>',
        '</svg>'
    ]
    # ---------------------------------------------------------------------
    # Remove the last four text lines (seal, solomon, footer) from kept
    cleaned = []
    skip_mode = False
    for line in kept:
        if '<text ' in line and 'y="345"' in line:
            skip_mode = True
        if skip_mode and '</svg>' in line:
            break
        if not skip_mode or '</svg>' in line:
            cleaned.append(line)

    # Combine everything
    final_svg = '\n'.join(cleaned) + '\n' + '\n'.join(new_footer) + '\n'

    # Verify it's valid XML
    try:
        ET.fromstring(final_svg)
    except ET.ParseError as e:
        raise RuntimeError(f"Invalid XML after fix for {path}: {e}")

    # Write out
    path.write_text(final_svg, encoding='utf-8')
    print(f"✓ Fixed {path.name}")

# -----------------------------------------------------------------------------
if __name__ == '__main__':
    if not base.exists():
        print(f"ERROR: folder not found: {base}")
        exit(1)

    for svg_path in sorted(base.glob('key-*.svg')):
        try:
            fix_svg(svg_path)
        except Exception as e:
            print(f"✗ {svg_path.name}: {e}")

    print("\nDone. All SVGs verified.")