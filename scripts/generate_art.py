"""Generate original bundled SVG artwork for OBus cards and provider Keys."""
from pathlib import Path
import colorsys
import math
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
ROOT = PROJECT / "backend" / "static" / "art"
CARDS = ROOT / "cards"
KEYS = ROOT / "keys"
CARDS.mkdir(parents=True, exist_ok=True)
KEYS.mkdir(parents=True, exist_ok=True)


def card_shell(title: str, numeral: str, palette: tuple[str, str, str], scene: str, stars: str) -> str:
    a, b, c = palette
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 1120">
<defs>
 <radialGradient id="sky" cx="50%" cy="35%"><stop stop-color="{b}"/><stop offset="1" stop-color="#050711"/></radialGradient>
 <linearGradient id="frame"><stop stop-color="{a}"/><stop offset=".5" stop-color="#fff1a8"/><stop offset="1" stop-color="{a}"/></linearGradient>
 <pattern id="runes" width="64" height="64" patternUnits="userSpaceOnUse"><path d="M8 32h48M32 8v48M16 16l32 32M48 16L16 48" stroke="{c}" opacity=".13"/></pattern>
 <filter id="glow"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="720" height="1120" rx="42" fill="#050711"/>
<rect x="18" y="18" width="684" height="1084" rx="34" fill="url(#sky)" stroke="url(#frame)" stroke-width="8"/>
<rect x="42" y="42" width="636" height="1036" rx="26" fill="url(#runes)" stroke="{a}" stroke-width="2"/>
<path d="M70 150Q360 60 650 150M70 940Q360 1030 650 940" fill="none" stroke="{a}" stroke-width="3"/>
{stars}
<text x="360" y="104" text-anchor="middle" fill="#fff3bd" font-size="38" font-family="Georgia">{numeral}</text>
{scene}
<rect x="94" y="946" width="532" height="96" rx="18" fill="#070914dd" stroke="{a}" stroke-width="2"/>
<text x="360" y="1006" text-anchor="middle" fill="#fff7d6" font-size="38" font-family="Georgia" letter-spacing="5">{title}</text>
</svg>'''


stars = ''.join(f'<circle cx="{80 + (i * 73) % 560}" cy="{155 + (i * 97) % 700}" r="{2 + i % 4}" fill="#fff5c7" opacity=".{4 + i % 6}"/>' for i in range(24))

magician = '''<circle cx="360" cy="390" r="175" fill="#ffb23e22" stroke="#f5c451" stroke-width="3"/><path d="M270 350Q360 250 450 350L420 680H300Z" fill="#841b42" stroke="#ffd76a" stroke-width="5"/><circle cx="360" cy="330" r="66" fill="#d59a72" stroke="#ffe19a" stroke-width="4"/><path d="M298 322Q360 212 422 322Q360 286 298 322" fill="#f7f0df"/><path d="M340 330h16M364 330h16" stroke="#1b1025" stroke-width="7"/><path d="M285 445L160 275M435 445L560 255" stroke="#f5c451" stroke-width="15"/><circle cx="560" cy="242" r="23" fill="#55d8ff" filter="url(#glow)"/><path d="M287 676h146l80 142H207Z" fill="#171b33" stroke="#f5c451" stroke-width="4"/><circle cx="280" cy="760" r="24" fill="#55d8ff"/><path d="M350 734l28 48 28-48" fill="#ff6b7a"/><path d="M286 235c40-45 108-45 148 0-40 44-108 44-148 0Z" fill="none" stroke="#fff3bd" stroke-width="8"/>'''
priestess = '''<rect x="120" y="210" width="110" height="620" rx="18" fill="#101a41" stroke="#55d8ff" stroke-width="5"/><rect x="490" y="210" width="110" height="620" rx="18" fill="#eee8df" stroke="#f5c451" stroke-width="5"/><text x="175" y="300" text-anchor="middle" fill="#fff" font-size="70">B</text><text x="545" y="300" text-anchor="middle" fill="#171220" font-size="70">J</text><path d="M210 280Q360 150 510 280V790Q360 690 210 790Z" fill="#39245e" opacity=".85" stroke="#a98cff" stroke-width="4"/><circle cx="360" cy="350" r="67" fill="#d9af93" stroke="#fff1a8" stroke-width="4"/><path d="M290 330Q360 225 430 330L405 292 360 260 315 292Z" fill="#d6dce9"/><path d="M305 425Q360 385 415 425L455 780H265Z" fill="#e6e8f2" stroke="#55d8ff" stroke-width="4"/><path d="M326 342h22M372 342h22" stroke="#25213e" stroke-width="7"/><path d="M280 520Q360 575 440 520" fill="none" stroke="#f5c451" stroke-width="12"/><path d="M322 200a42 42 0 1 0 76 0 55 55 0 1 1-76 0" fill="#fff0a8" filter="url(#glow)"/><path d="M260 800Q360 740 460 800L430 875H290Z" fill="#55d8ff33" stroke="#55d8ff" stroke-width="4"/>'''
emperor = '''<path d="M170 780V360L250 275 300 330H420L470 275 550 360V780Z" fill="#5d1d23" stroke="#f5c451" stroke-width="7"/><path d="M210 310L130 210 260 270M510 310L590 210 460 270" fill="#782a2d" stroke="#ffb45c" stroke-width="8"/><circle cx="360" cy="340" r="72" fill="#c88762" stroke="#f5c451" stroke-width="4"/><path d="M300 315L320 235 360 280 400 235 420 315Z" fill="#f5c451" stroke="#fff1a8" stroke-width="4"/><path d="M292 410Q360 370 428 410L470 680H250Z" fill="#8d2630" stroke="#f5c451" stroke-width="5"/><path d="M315 346h22M383 346h22" stroke="#1a1012" stroke-width="8"/><path d="M325 382Q360 410 395 382" fill="none" stroke="#f2d2b8" stroke-width="18"/><path d="M190 575h120M410 575h120" stroke="#f5c451" stroke-width="18"/><circle cx="195" cy="600" r="40" fill="#5c2330" stroke="#f5c451" stroke-width="5"/><circle cx="525" cy="600" r="40" fill="#5c2330" stroke="#f5c451" stroke-width="5"/><path d="M110 875L240 715 330 875M390 875L500 700 620 875" fill="#151a2d" stroke="#a98cff" stroke-width="3"/>'''
hermit = '''<path d="M350 170L310 260 350 245 390 260Z" fill="#fff3bd" filter="url(#glow)"/><path d="M330 255Q360 210 390 255L430 690 510 870H210L290 690Z" fill="#263149" stroke="#a98cff" stroke-width="5"/><circle cx="360" cy="330" r="58" fill="#c89a79" stroke="#fff1a8" stroke-width="4"/><path d="M310 315Q360 250 410 315" fill="#d7d8df"/><path d="M330 350h18M372 350h18" stroke="#151725" stroke-width="7"/><path d="M330 384Q360 420 390 384" fill="none" stroke="#dfe5ef" stroke-width="16"/><path d="M292 475L180 735M425 480L540 710" stroke="#8f6847" stroke-width="17"/><path d="M505 600h100v150H505Z" fill="#23263b" stroke="#f5c451" stroke-width="7"/><path d="M520 620l35-28 35 28v92h-70Z" fill="#ffd258" filter="url(#glow)"/><path d="M120 870Q250 760 360 845Q470 735 620 870" fill="#0e1624" stroke="#55d8ff" stroke-width="4"/>'''

card_specs = {
    "magician.svg": ("THE MAGICIAN", "I", ("#f5c451", "#541735", "#55d8ff"), magician),
    "high-priestess.svg": ("HIGH PRIESTESS", "II", ("#55d8ff", "#25225b", "#a98cff"), priestess),
    "emperor.svg": ("THE EMPEROR", "IV", ("#f5c451", "#552128", "#ff6b7a"), emperor),
    "hermit.svg": ("THE HERMIT", "IX", ("#a98cff", "#17243d", "#55d8ff"), hermit),
}
for filename, (title, numeral, palette, scene) in card_specs.items():
    (CARDS / filename).write_text(card_shell(title, numeral, palette, scene, stars), encoding="utf-8")

# Render the remaining deck as original high-fantasy JRPG-inspired character portraits.
# These designs use no protected characters, logos, costumes, or franchise-specific assets.
from backend.card_catalog import DEFAULT_CARDS


def jrpg_card_svg(card: dict, index: int) -> str:
    seed = sum((i + 5) * ord(ch) for i, ch in enumerate(card["slug"]))
    hue = (seed * 11) % 360
    accent = f"hsl({hue} 82% 66%)"
    accent2 = f"hsl({(hue + 72) % 360} 78% 60%)"
    hair = f"hsl({(hue + 190) % 360} 35% {28 + index % 35}%)"
    armor = f"hsl({(hue + 25) % 360} 45% 24%)"
    aura_points = ' '.join(
        f"{360 + math.cos(math.radians(i * 30 + seed % 29)) * (190 + (seed >> (i % 9)) % 48):.1f},"
        f"{475 + math.sin(math.radians(i * 30 + seed % 29)) * (190 + (seed >> (i % 9)) % 48):.1f}"
        for i in range(12)
    )
    gem_count = 3 + index % 7
    gems = ''.join(
        f'<circle cx="{245 + i * (230 / max(1, gem_count - 1)):.1f}" cy="705" r="{8 + i % 4}" fill="{accent2}" filter="url(#glow)"/>'
        for i in range(gem_count)
    )
    weapon_kind = index % 4
    weapon = [
        f'<path d="M505 720L610 270" stroke="#eaf5ff" stroke-width="15"/><path d="M570 355l65-30-35 62Z" fill="{accent}"/>',
        f'<path d="M515 735Q630 545 575 315" fill="none" stroke="{accent}" stroke-width="18"/><path d="M540 330q75-55 100 20" fill="none" stroke="#f5c451" stroke-width="8"/>',
        f'<path d="M510 720L620 390M566 555l80 25" stroke="#f7df9b" stroke-width="17"/><circle cx="622" cy="382" r="35" fill="{accent2}" filter="url(#glow)"/>',
        f'<path d="M500 720L620 315" stroke="#cbd5f6" stroke-width="13"/><path d="M580 420l76-20-44 70Z" fill="{accent}"/><path d="M548 530l65 42" stroke="#f5c451" stroke-width="12"/>',
    ][weapon_kind]
    rank = card.get("rank") or card["symbol"]
    suit = (card.get("suit") or "major").upper()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 1120"><defs><radialGradient id="bg"><stop stop-color="{accent2}" stop-opacity=".38"/><stop offset=".6" stop-color="#10142b"/><stop offset="1" stop-color="#03050c"/></radialGradient><linearGradient id="metal"><stop stop-color="#f7e6a1"/><stop offset=".45" stop-color="{accent}"/><stop offset="1" stop-color="#363b59"/></linearGradient><pattern id="stars" width="52" height="52" patternUnits="userSpaceOnUse"><path d="M26 4v44M4 26h44M10 10l32 32M42 10L10 42" stroke="{accent}" opacity=".1"/></pattern><filter id="glow"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><rect width="720" height="1120" rx="44" fill="#03050c"/><rect x="18" y="18" width="684" height="1084" rx="34" fill="url(#bg)" stroke="url(#metal)" stroke-width="8"/><rect x="42" y="42" width="636" height="1036" rx="25" fill="url(#stars)" stroke="{accent}" stroke-width="2"/><polygon points="{aura_points}" fill="none" stroke="{accent}" stroke-width="4" opacity=".55"/><circle cx="360" cy="458" r="220" fill="none" stroke="#f5c451" stroke-width="3"/><path d="M235 405Q360 270 485 405L458 785H262Z" fill="{armor}" stroke="url(#metal)" stroke-width="7"/><path d="M255 430L165 620 250 645M465 430L540 610 480 650" fill="none" stroke="#d4a681" stroke-width="32"/><circle cx="360" cy="345" r="79" fill="#d7a47f" stroke="#fff0be" stroke-width="5"/><path d="M284 340Q300 190 360 225Q440 180 438 350Q392 285 284 340Z" fill="{hair}" stroke="{accent}" stroke-width="5"/><path d="M318 350l26 3M376 353l26-3" stroke="#131420" stroke-width="10"/><path d="M340 390Q360 404 380 390" fill="none" stroke="#8c5145" stroke-width="6"/><path d="M290 440L215 520 270 555 325 475M430 440L505 520 450 555 395 475" fill="url(#metal)" stroke="{accent}" stroke-width="5"/><path d="M292 540L245 690 360 780 475 690 428 540Q360 600 292 540Z" fill="#151a30" stroke="url(#metal)" stroke-width="6"/>{gems}{weapon}<path d="M95 875Q230 770 360 850Q490 760 625 875" fill="#090d19" stroke="{accent2}" stroke-width="5"/><rect x="88" y="910" width="544" height="126" rx="20" fill="#050713e8" stroke="url(#metal)" stroke-width="3"/><text x="360" y="964" text-anchor="middle" fill="#fff6d8" font-family="Georgia" font-size="34" letter-spacing="3">{card['name'].upper()}</text><text x="360" y="1005" text-anchor="middle" fill="{accent}" font-family="Segoe UI" font-size="18" letter-spacing="5">{suit} · {str(rank).upper()}</text><text x="360" y="88" text-anchor="middle" fill="#fff1b5" font-family="Georgia" font-size="31">{card['symbol']}</text></svg>'''


existing_slugs = {name.removesuffix('.svg') for name in card_specs}
for index, card in enumerate(DEFAULT_CARDS):
    if card["slug"] not in existing_slugs:
        (CARDS / f"{card['slug']}.svg").write_text(jrpg_card_svg(card, index), encoding="utf-8")

key_ids = [
    "key-local-ollama", "key-codex-oauth", "key-nous-oauth", "key-nvidia-nim",
    "key-anthropic", "key-google-gemini", "key-openrouter", "key-mistral",
    "key-groq", "key-xai", "key-together", "key-fireworks", "key-deepseek",
    "key-cerebras", "key-huggingface", "key-azure-openai",
]

def sigil_svg(key_id: str, index: int) -> str:
    seed = sum((i + 3) * ord(c) for i, c in enumerate(key_id))
    hue = (seed * 17) % 360
    rgb = colorsys.hsv_to_rgb(hue / 360, .68, 1)
    color = '#%02x%02x%02x' % tuple(int(v * 255) for v in rgb)
    points = []
    for i in range(11):
        angle = math.radians((seed % 31) + i * (360 / 11) * (2 + index % 3))
        radius = 70 + ((seed >> (i % 10)) % 48)
        points.append(f"{200 + math.cos(angle) * radius:.1f},{200 + math.sin(angle) * radius:.1f}")
    spokes = ''.join(f'<path d="M200 200L{p}"/>' for p in points[::2])
    runes = ''.join(f'<circle cx="{200 + math.cos(i*math.pi/6)*150:.1f}" cy="{200 + math.sin(i*math.pi/6)*150:.1f}" r="{4+i%3}"/>' for i in range(12))
    horn = 28 + index % 5 * 6
    label = key_id.removeprefix('key-').replace('-', ' ').upper()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400"><defs><radialGradient id="a"><stop stop-color="{color}" stop-opacity=".5"/><stop offset="1" stop-color="#060812" stop-opacity="0"/></radialGradient><filter id="g"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><rect width="400" height="400" rx="42" fill="#060812"/><circle cx="200" cy="200" r="178" fill="url(#a)" stroke="#f5c451" stroke-width="2"/><circle cx="200" cy="200" r="145" fill="none" stroke="{color}" stroke-width="3"/><g fill="{color}" stroke="{color}" filter="url(#g)">{runes}</g><g fill="none" stroke="#f5c451" stroke-width="2" opacity=".75">{spokes}</g><polygon points="{' '.join(points)}" fill="none" stroke="{color}" stroke-width="4"/><path d="M150 180Q{130-horn} 110 185 142M250 180Q{270+horn} 110 215 142" fill="none" stroke="#f5c451" stroke-width="9"/><path d="M154 165Q200 125 246 165L232 248 200 278 168 248Z" fill="#0d1120" stroke="{color}" stroke-width="5"/><path d="M168 190l28 12-32 14M232 190l-28 12 32 14" fill="{color}" filter="url(#g)"/><path d="M182 242l18-14 18 14-18 23Z" fill="#f5c451"/><circle cx="200" cy="200" r="34" fill="none" stroke="#f5c451" stroke-width="2"/><text x="200" y="366" text-anchor="middle" fill="#eef3ff" font-family="Segoe UI" font-size="15" letter-spacing="2">{label}</text><text x="200" y="388" text-anchor="middle" fill="#929ab4" font-family="Segoe UI" font-size="9">ORIGINAL PROVIDER DAEMON SIGIL</text></svg>'''

for index, key_id in enumerate(key_ids):
    (KEYS / f"{key_id}.svg").write_text(sigil_svg(key_id, index), encoding="utf-8")

print(f"generated {len(DEFAULT_CARDS)} card artworks and {len(key_ids)} provider sigils in {ROOT}")
