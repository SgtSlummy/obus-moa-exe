"""Generate The Pilgrim's Ink Deck: 78 original hand-drawn Tarot SVG paintings."""
from __future__ import annotations

import html
import math
import random
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from backend.card_catalog import DEFAULT_CARDS  # noqa: E402

OUT = PROJECT / "backend" / "static" / "art" / "cards"
OUT.mkdir(parents=True, exist_ok=True)

PALETTES = {
    "major": ("#20334d", "#8f3151", "#d6a84b", "#6f8f83"),
    "wands": ("#7f2e25", "#d77b35", "#e5b95c", "#4e6745"),
    "cups": ("#244b70", "#4d7f94", "#a66f83", "#d3b46f"),
    "swords": ("#303b58", "#68738f", "#9f4950", "#d2bf91"),
    "pentacles": ("#3f593e", "#77834c", "#9b633d", "#d3aa50"),
}

RANK_VALUE = {"ace": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def seed_for(text: str) -> int:
    return sum((i + 11) * ord(ch) for i, ch in enumerate(text))


def paper_defs(palette: tuple[str, str, str, str], seed: int) -> str:
    a, b, gold, wash = palette
    return f'''<defs>
<filter id="paper-grain" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency=".72" numOctaves="4" seed="{seed % 97}" result="noise"/><feColorMatrix in="noise" values=".18 0 0 0 .72  0 .14 0 0 .66  0 0 .1 0 .54  0 0 0 .22 0"/><feBlend in="SourceGraphic" mode="multiply"/></filter>
<filter id="rough-ink" x="-8%" y="-8%" width="116%" height="116%"><feTurbulence type="turbulence" baseFrequency=".012 .055" numOctaves="2" seed="{(seed + 17) % 101}" result="wobble"/><feDisplacementMap in="SourceGraphic" in2="wobble" scale="3.8" xChannelSelector="R" yChannelSelector="G"/></filter>
<filter id="watercolor" x="-20%" y="-20%" width="140%" height="140%"><feTurbulence type="fractalNoise" baseFrequency=".018" numOctaves="3" seed="{(seed + 31) % 113}" result="wet"/><feDisplacementMap in="SourceGraphic" in2="wet" scale="18"/><feGaussianBlur stdDeviation="2.2"/></filter>
<linearGradient id="ink-wash" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{a}" stop-opacity=".66"/><stop offset=".52" stop-color="{wash}" stop-opacity=".32"/><stop offset="1" stop-color="{b}" stop-opacity=".62"/></linearGradient>
<radialGradient id="gold-bloom"><stop stop-color="{gold}" stop-opacity=".7"/><stop offset="1" stop-color="{gold}" stop-opacity="0"/></radialGradient>
<pattern id="crosshatch" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M-3 18L18-3M4 22L22 4" stroke="#392f2a" stroke-width="1" opacity=".12"/></pattern>
</defs>'''


def watercolor_blobs(rng: random.Random, palette: tuple[str, str, str, str]) -> str:
    colors = [palette[0], palette[1], palette[2], palette[3]]
    parts = []
    for i in range(12):
        cx, cy = rng.randint(90, 630), rng.randint(140, 900)
        rx, ry = rng.randint(65, 190), rng.randint(55, 180)
        points = []
        for j in range(10):
            angle = 2 * math.pi * j / 10
            radius = 1 + rng.uniform(-.24, .24)
            points.append((cx + math.cos(angle) * rx * radius, cy + math.sin(angle) * ry * radius))
        path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points) + " Z"
        parts.append(f'<path d="{path}" fill="{colors[i % 4]}" opacity="{.055 + (i % 4) * .018:.3f}" filter="url(#watercolor)"/>')
    return "".join(parts)


def ink_border(rng: random.Random, accent: str) -> str:
    parts = []
    for offset, opacity, width in ((20, .92, 5), (28, .42, 2), (43, .7, 2.5)):
        jitter = rng.randint(-3, 3)
        parts.append(f'<rect x="{offset+jitter}" y="{offset}" width="{720-2*offset}" height="{1120-2*offset}" rx="{32-offset//3}" fill="none" stroke="#2b2724" stroke-width="{width}" opacity="{opacity}" filter="url(#rough-ink)"/>')
    parts.append(f'<path d="M72 130Q360 {80+rng.randint(-12,12)} 648 130M72 930Q360 {985+rng.randint(-12,12)} 648 930" fill="none" stroke="{accent}" stroke-width="3" opacity=".75" filter="url(#rough-ink)"/>')
    return "".join(parts)


def texture_marks(rng: random.Random) -> str:
    marks = []
    for _ in range(95):
        x, y = rng.randint(64, 656), rng.randint(118, 930)
        r = rng.choice([.8, 1.1, 1.6, 2.2])
        marks.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#372f2a" opacity="{rng.uniform(.12,.45):.2f}"/>')
    for _ in range(42):
        x, y = rng.randint(80, 620), rng.randint(180, 870)
        length = rng.randint(18, 80)
        slope = rng.randint(-18, 18)
        marks.append(f'<path d="M{x} {y}l{length} {slope}" stroke="#302a27" stroke-width="1.2" opacity=".18"/>')
    return "".join(marks)


def rough_line(path: str, color: str = "#292622", width: float = 5, opacity: float = 1) -> str:
    return f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}" filter="url(#rough-ink)"/><path d="{path}" fill="none" stroke="{color}" stroke-width="{max(.7,width*.28):.1f}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity*.45:.2f}" transform="translate(2 -1)"/>'


def person(rng: random.Random, palette: tuple[str, str, str, str], pose: int, court: bool = False) -> str:
    a, b, gold, wash = palette
    cx = 360 + rng.randint(-25, 25)
    head_y = 345 + rng.randint(-12, 16)
    robe = f'M{cx-92} 452 Q{cx} 395 {cx+92} 452 L{cx+142} 820 Q{cx} 870 {cx-142} 820 Z'
    arm_l = f'M{cx-72} 485 Q{cx-150-pose*5} {560+pose*8} {cx-185} {665-pose*9}'
    arm_r = f'M{cx+72} 485 Q{cx+150+pose*4} {550-pose*7} {cx+180} {640+pose*6}'
    crown = f'<path d="M{cx-56} {head_y-64}l18-38 38 27 38-27 18 38" fill="none" stroke="{gold}" stroke-width="7" filter="url(#rough-ink)"/>' if court else ''
    hair = f'M{cx-64} {head_y-10}Q{cx-54} {head_y-95} {cx} {head_y-84}Q{cx+70} {head_y-102} {cx+64} {head_y+12}'
    return f'''<g data-layer="hand-drawn-figure">{crown}<path d="{robe}" fill="{a}" opacity=".52" stroke="#292622" stroke-width="6" filter="url(#rough-ink)"/>{rough_line(arm_l, '#362d28', 18)}{rough_line(arm_r, '#362d28', 18)}<ellipse cx="{cx}" cy="{head_y}" rx="69" ry="78" fill="#d3a67e" opacity=".82" stroke="#2e2824" stroke-width="5" filter="url(#rough-ink)"/><path d="{hair}" fill="none" stroke="{b}" stroke-width="24" opacity=".78" filter="url(#rough-ink)"/><path d="M{cx-31} {head_y+3}l17 2M{cx+14} {head_y+5}l17-2" stroke="#292522" stroke-width="7"/><path d="M{cx-19} {head_y+40}Q{cx} {head_y+51} {cx+20} {head_y+38}" fill="none" stroke="#7c4e45" stroke-width="4"/>{rough_line(f'M{cx-60} 540Q{cx} 590 {cx+60} 540', gold, 7, .8)}</g>'''


def celestial(kind: str, x: int, y: int, r: int, color: str) -> str:
    if kind == "sun":
        rays = ''.join(f'<path d="M{x+math.cos(i*math.pi/8)*(r+12):.1f} {y+math.sin(i*math.pi/8)*(r+12):.1f}L{x+math.cos(i*math.pi/8)*(r+38):.1f} {y+math.sin(i*math.pi/8)*(r+38):.1f}" stroke="{color}" stroke-width="3"/>' for i in range(16))
        return f'<g filter="url(#rough-ink)"><circle cx="{x}" cy="{y}" r="{r}" fill="url(#gold-bloom)" stroke="{color}" stroke-width="5"/>{rays}</g>'
    if kind == "moon":
        return f'<path d="M{x+r} {y-r}A{r} {r} 0 1 0 {x+r} {y+r}A{r*.76:.1f} {r*.76:.1f} 0 0 1 {x+r} {y-r}Z" fill="{color}" opacity=".65" stroke="#312923" stroke-width="4" filter="url(#rough-ink)"/>'
    return f'<path d="M{x} {y-r}l{r*.23:.1f} {r*.68:.1f}h{r*.72:.1f}l-{r*.58:.1f} {r*.42:.1f}l{r*.22:.1f} {r*.7:.1f}l-{r*.59:.1f}-{r*.43:.1f}l-{r*.59:.1f} {r*.43:.1f}l{r*.22:.1f}-{r*.7:.1f}l-{r*.58:.1f}-{r*.42:.1f}h{r*.72:.1f}Z" fill="{color}" opacity=".62" stroke="#312923" stroke-width="3" filter="url(#rough-ink)"/>'


def major_scene(slug: str, rng: random.Random, palette: tuple[str, str, str, str], index: int) -> str:
    a, b, gold, wash = palette
    fig = person(rng, palette, index % 5, slug in {"empress", "emperor", "hierophant", "world"})
    scenes = {
        "fool": rough_line("M85 820Q260 710 410 805Q535 720 650 790", "#40362d", 7) + rough_line("M540 770l52-150 38 126", gold, 6) + '<circle cx="525" cy="762" r="18" fill="#efe3c3" stroke="#302925" stroke-width="4"/>',
        "magician": celestial("star", 360, 220, 72, gold) + rough_line("M150 710H570M200 710l-30 100M520 710l30 100", "#352c28", 8),
        "high-priestess": '<rect x="105" y="235" width="90" height="590" fill="#1d3351" opacity=".55" stroke="#302925" stroke-width="6"/><rect x="525" y="235" width="90" height="590" fill="#eee4cf" opacity=".6" stroke="#302925" stroke-width="6"/>' + celestial("moon", 360, 200, 60, gold),
        "empress": ''.join(f'<path d="M{130+i*72} 835q18-110 36 0" fill="none" stroke="{wash}" stroke-width="9"/>' for i in range(7)) + celestial("star", 160, 220, 44, gold),
        "emperor": rough_line("M110 850L245 680 340 850M390 850L500 650 630 850", "#483a34", 8) + '<path d="M270 280l25-72 65 45 65-45 25 72" fill="none" stroke="#c99b3d" stroke-width="8"/>',
        "hierophant": rough_line("M170 760V300M550 760V300M170 330Q360 180 550 330", gold, 7) + rough_line("M320 580h80M360 540v190", "#3a302c", 8),
        "lovers": celestial("sun", 360, 205, 48, gold) + rough_line("M215 715Q360 590 505 715", b, 10) + '<path d="M330 560C275 505 220 590 360 690C500 590 445 505 390 560L360 590Z" fill="#9a3e52" opacity=".45"/>',
        "chariot": rough_line("M190 745H530L490 875H230ZM235 875a45 45 0 1 0 1 0M485 875a45 45 0 1 0 1 0", "#302925", 9) + rough_line("M130 820Q180 700 245 800M590 820Q540 700 475 800", gold, 6),
        "strength": '<path d="M155 730Q185 610 280 660Q340 720 270 825Q180 855 145 790Z" fill="#b8753f" opacity=".38" stroke="#342923" stroke-width="7"/>' + rough_line("M190 720Q225 670 270 710", "#332824", 5) + celestial("sun", 360, 210, 42, gold),
        "hermit": celestial("star", 535, 500, 42, gold) + rough_line("M515 540V760M500 760h70", "#332b27", 8) + rough_line("M80 880Q220 720 350 835Q500 700 650 880", wash, 6),
        "wheel-of-fortune": '<circle cx="360" cy="520" r="205" fill="none" stroke="#342a26" stroke-width="9" filter="url(#rough-ink)"/><circle cx="360" cy="520" r="110" fill="none" stroke="#b98b36" stroke-width="6"/>' + ''.join(rough_line(f"M360 520L{360+math.cos(i*math.pi/4)*205:.1f} {520+math.sin(i*math.pi/4)*205:.1f}", gold, 4) for i in range(8)),
        "justice": rough_line("M360 250V760M250 360H470M250 360L190 600M470 360L530 600", gold, 7) + '<path d="M110 600Q190 680 270 600ZM450 600Q530 680 610 600Z" fill="#52677a" opacity=".35" stroke="#342a26" stroke-width="5"/>',
        "hanged-man": rough_line("M130 245H590M210 245V760M510 245V760", "#554238", 10) + rough_line("M360 250V440M300 720L360 620 420 720", gold, 8),
        "death": rough_line("M120 850Q250 680 360 820Q470 650 620 850", "#3f3935", 8) + '<path d="M515 290l90 45-90 45Z" fill="#d7d0bb" stroke="#2e2926" stroke-width="5"/>' + rough_line("M510 290V760", "#332b27", 9),
        "temperance": '<path d="M170 510Q235 455 300 510L275 700Q235 745 195 700Z" fill="#47748a" opacity=".35" stroke="#332b27" stroke-width="6"/><path d="M420 560Q485 505 550 560L525 750Q485 795 445 750Z" fill="#a65a69" opacity=".35" stroke="#332b27" stroke-width="6"/>' + rough_line("M290 560Q360 650 430 610", gold, 7),
        "devil": rough_line("M245 315Q175 180 295 260M475 315Q545 180 425 260", "#342725", 12) + rough_line("M210 770Q360 650 510 770", b, 10) + rough_line("M235 760l-65 90M485 760l65 90", "#342725", 6),
        "tower": '<path d="M245 790V300H475V790Z" fill="#5a5361" opacity=".35" stroke="#312a27" stroke-width="8" filter="url(#rough-ink)"/>' + rough_line("M195 260l120 75-65 80 130-80-60-75", gold, 12) + rough_line("M245 520l230-95M245 640l230-80", "#9b3c48", 6),
        "star": celestial("star", 360, 215, 78, gold) + ''.join(celestial("star", 120+i*80, 380+(i%2)*55, 20, wash) for i in range(7)) + rough_line("M100 820Q260 720 360 810Q480 690 630 820", wash, 6),
        "moon": celestial("moon", 360, 215, 86, gold) + rough_line("M120 820Q210 705 290 820M430 820Q520 705 610 820", a, 8) + rough_line("M360 830V610", gold, 5),
        "sun": celestial("sun", 360, 225, 88, gold) + ''.join(f'<path d="M{100+i*75} 850q20-145 40 0" stroke="{wash}" stroke-width="10" fill="none"/>' for i in range(8)),
        "judgement": rough_line("M200 290Q360 170 520 290", gold, 7) + rough_line("M350 260l110-45 55 60-110 45Z", "#503e35", 7) + ''.join(rough_line(f"M{160+i*100} 820V700", wash, 9) for i in range(5)),
        "world": '<ellipse cx="360" cy="520" rx="245" ry="335" fill="none" stroke="#6d8b6f" stroke-width="16" opacity=".55" filter="url(#rough-ink)"/>' + ''.join(celestial("star", x, y, 25, gold) for x, y in ((135,230),(585,230),(135,825),(585,825))),
    }
    return scenes.get(slug, "") + fig


def suit_object(suit: str, x: float, y: float, scale: float, palette: tuple[str, str, str, str]) -> str:
    a, b, gold, wash = palette
    if suit == "wands":
        return rough_line(f"M{x-scale*18:.1f} {y+scale*70:.1f}L{x+scale*22:.1f} {y-scale*70:.1f}", "#69452e", 7*scale) + f'<path d="M{x+scale*10:.1f} {y-scale*48:.1f}q{scale*35:.1f}-{scale*22:.1f} {scale*25:.1f} {scale*22:.1f}" stroke="{wash}" stroke-width="{4*scale:.1f}" fill="none"/>'
    if suit == "cups":
        return f'<path d="M{x-scale*42:.1f} {y-scale*50:.1f}Q{x:.1f} {y+scale*20:.1f} {x+scale*42:.1f} {y-scale*50:.1f}L{x+scale*30:.1f} {y-scale*72:.1f}H{x-scale*30:.1f}Z" fill="{a}" opacity=".35" stroke="#302824" stroke-width="{5*scale:.1f}" filter="url(#rough-ink)"/>{rough_line(f"M{x:.1f} {y+scale*10:.1f}V{y+scale*70:.1f}M{x-scale*28:.1f} {y+scale*70:.1f}H{x+scale*28:.1f}", gold, 5*scale)}'
    if suit == "swords":
        return f'{rough_line(f"M{x:.1f} {y+scale*75:.1f}V{y-scale*62:.1f}", "#4c5363", 7*scale)}{rough_line(f"M{x-scale*35:.1f} {y+scale*35:.1f}H{x+scale*35:.1f}", gold, 6*scale)}<path d="M{x:.1f} {y-scale*82:.1f}l-{scale*13:.1f} {scale*25:.1f}h{scale*26:.1f}Z" fill="#d6d4c7" stroke="#302824" stroke-width="{3*scale:.1f}"/>'
    points = " ".join(f"{x+math.cos(-math.pi/2+i*2*math.pi/5)*scale*45:.1f},{y+math.sin(-math.pi/2+i*2*math.pi/5)*scale*45:.1f}" for i in range(5))
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{scale*58:.1f}" fill="{gold}" opacity=".25" stroke="#302824" stroke-width="{5*scale:.1f}" filter="url(#rough-ink)"/><polygon points="{points}" fill="none" stroke="{gold}" stroke-width="{5*scale:.1f}"/>'


def minor_scene(card: dict, rng: random.Random, palette: tuple[str, str, str, str], index: int) -> str:
    suit, rank = card["suit"], card["rank"]
    count = RANK_VALUE.get(rank)
    court = rank in {"page", "knight", "queen", "king"}
    parts = []
    if count:
        cols = 3 if count > 6 else 2 if count > 3 else count
        rows = math.ceil(count / cols)
        for i in range(count):
            col, row = i % cols, i // cols
            x = 360 + (col - (cols-1)/2) * (165 if cols == 3 else 220)
            y = 290 + row * (520 / max(1, rows-1)) if rows > 1 else 420
            parts.append(suit_object(suit, x, y, .68 if count > 6 else .86, palette))
        if count <= 4:
            parts.append(person(rng, palette, index % 5, False))
    else:
        parts.append(person(rng, palette, index % 5, court))
        parts.append(suit_object(suit, 555, 525, 1.05, palette))
        if rank == "knight": parts.append(rough_line("M100 825Q205 690 305 825", palette[0], 9))
        if rank == "queen": parts.append(celestial("moon", 150, 230, 48, palette[2]))
        if rank == "king": parts.append(celestial("sun", 150, 230, 48, palette[2]))
        if rank == "page": parts.append(celestial("star", 150, 230, 42, palette[2]))
    return "".join(parts)


def card_svg(card: dict, index: int) -> str:
    rng = random.Random(seed_for(card["id"]))
    suit_key = card.get("suit") or "major"
    palette = PALETTES[suit_key]
    a, b, gold, wash = palette
    scene = major_scene(card["slug"], rng, palette, index) if card["arcana"] == "major" else minor_scene(card, rng, palette, index)
    title = html.escape(card["name"].upper())
    subtitle = html.escape((card.get("agent_type") or card["arcana"]).replace("_", " ").upper())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 1120" data-style="hand-drawn-ink-watercolor" data-card-id="{html.escape(card['id'])}">
<title>{title} — The Pilgrim's Ink Deck</title><desc>Original hand-drawn Tarot illustration with ink contours, watercolor washes, paper grain, and symbolic imagery.</desc>
{paper_defs(palette, seed_for(card['id']))}
<rect width="720" height="1120" rx="38" fill="#efe2c8"/><rect x="12" y="12" width="696" height="1096" rx="32" fill="#f3e7cf" filter="url(#paper-grain)"/>
{watercolor_blobs(rng, palette)}<rect x="48" y="105" width="624" height="845" rx="16" fill="url(#crosshatch)"/>{texture_marks(rng)}{ink_border(rng, gold)}
<g data-scene="{html.escape(card['slug'])}">{scene}</g>
<rect x="78" y="942" width="564" height="118" rx="12" fill="#f4e8d4" opacity=".86" stroke="#302a27" stroke-width="4" filter="url(#rough-ink)"/>
<text x="360" y="995" text-anchor="middle" fill="#2d2926" font-family="Georgia,serif" font-size="31" font-weight="bold" letter-spacing="2">{title}</text>
<text x="360" y="1032" text-anchor="middle" fill="{a}" font-family="Georgia,serif" font-size="15" letter-spacing="3">{subtitle}</text>
<text x="360" y="84" text-anchor="middle" fill="#2e2925" font-family="Georgia,serif" font-size="30">{html.escape(str(card['symbol']))}</text>
</svg>'''


def main() -> None:
    hashes = set()
    for index, card in enumerate(DEFAULT_CARDS):
        art = card_svg(card, index)
        path = OUT / f"{card['slug']}.svg"
        path.write_text(art, encoding="utf-8")
        hashes.add(hash(art))
    if len(hashes) != 78:
        raise RuntimeError("Artwork collision detected")
    print(f"generated {len(DEFAULT_CARDS)} unique hand-drawn Tarot paintings in {OUT}")


if __name__ == "__main__":
    main()
