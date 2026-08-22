"""Generate 78 AI-assisted ink-and-watercolor Tarot illustrations.

No credentials are read or stored. Raw generations stay under assets/ and final,
locally titled WebP cards are bundled with OBus. Sequential requests only.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.card_catalog import DEFAULT_CARDS  # noqa: E402
from scripts.generate_flux_tarot import MAJOR_SCENES, MINOR, RESEARCH_SOURCES, SUIT_WORLD  # noqa: E402

RAW = ROOT / "assets" / "tarot-source-ink-watercolor"
OUT = ROOT / "backend" / "static" / "art" / "cards"
SHEETS = ROOT / "assets" / "tarot-contact-sheets-ink-watercolor"
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
SHEETS.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 720, 1120
ENDPOINT = "https://image.pollinations.ai/prompt/"
MODEL = "flux"
REQUEST_INTERVAL = 16.0
USER_AGENT = "Mozilla/5.0 OBus-Pilgrims-Ink/2.0"
FONT_BOLD = "C:/Windows/Fonts/georgiab.ttf"
FONT_REG = "C:/Windows/Fonts/georgia.ttf"

# Gentler symbolism for cards most likely to become grim or uncanny.
SCENE_OVERRIDES = {
    "fool": "a cheerful young traveler stepping along a sunlit alpine path, warm layered travel clothes, a small ordinary white dog walking beside their boots, wildflowers and distant blue mountains, bright curious face",
    "lovers": "exactly two fully clothed adult travelers standing separately in an open flowering grove, gently holding hands and making a shared choice, both faces clearly visible, a small golden bird above them, affectionate but nonsexual",
    "hanged-man": "a calm smiling acrobat in complete layered clothing performing a controlled upside-down aerial pose from one ankle beneath a flowering world tree, other leg bent, peaceful face visible, meditation and new perspective, no distress",
    "death": "a solemn human knight in elegant black-and-silver armor walking beside a calm pale horse through a field of white roses, carrying a white-rose banner, spring sunrise, transformation and renewal, no battlefield, no bodies",
    "devil": "a symbolic still life with no people: an empty carved velvet chair in a sunlit amber conservatory, an elegant theatrical horned mask resting harmlessly on the seat, two neatly cut red silk cords on the floor, open doors revealing a bright garden, liberation from temptation, no human figure, no face, no body, no monster, no horror, no demon",
    "tower": "an empty ancient hilltop observatory struck by brilliant branching lightning as its crown opens into glowing fragments, white birds escaping into a violet storm, revelation and sudden change, no people falling, no injuries, no fire victims",
    "moon": "a gentle cloaked traveler on a silver moonlit garden path between two old towers, one ordinary dog and one wolf standing separately, a crescent moon reflected in a pond, dreamlike but comforting mist",
    "judgement": "a luminous winged herald sounding a golden trumpet above a spring valley while fully clothed townspeople step from shadow into sunrise, awakening and forgiveness, no graves or corpses",
    "three-of-swords": "a large embroidered crimson heart emblem crossed by three decorative silver swords above a rain-washed garden, blue ribbons and three white roses, emotional honesty without gore, no person",
    "nine-of-swords": "a fully clothed person sitting safely in a cozy stone bedroom after waking from a bad dream, nine ceremonial swords arranged harmlessly on a tapestry, warm candle and reassuring dawn through the window",
    "ten-of-swords": "an empty suit of armor resting peacefully on a meadow at sunrise, ten silver swords planted upright in a protective circle around it, ending and renewal, no body, no wounds, no violence",
}

STYLE = (
    "Original artistic hand-drawn Tarot illustration, traditional mixed media on warm cold-press cotton paper: "
    "visible graphite underdrawing, elegant varied black ink contours, transparent watercolor washes, soft colored-pencil shading, "
    "small opaque gouache highlights, subtle paper grain and human brush variation. Warm lyrical storybook high fantasy, graceful and inviting, "
    "clear readable composition, gentle expressive faces, natural human proportions, coherent simplified hands, beautiful costume silhouette, "
    "luminous botanical details, balanced negative space, jewel-tone color accents, hopeful emotional atmosphere. "
    "Entirely original people and costumes; transfer only broad composition and symbolism principles from historic Tarot, illuminated manuscripts, "
    "and public-domain storybook illustration. No imitation of a living artist or protected franchise."
)
NEGATIVE = (
    "photograph, photorealistic, hyperrealistic, cinematic CGI, 3d render, plastic skin, airbrushed digital realism, horror, gore, macabre, "
    "disturbing, uncanny face, black eyes, hollow eyes, hidden face, blurred face, melted face, skeletal person, monster, demon, corpse, blood, "
    "extra limbs, extra fingers, malformed hands, fused bodies, duplicate person, distorted anatomy, giant head, modern clothing, mask except theatrical devil card, "
    "dark muddy image, black background, harsh desaturation, anime, manga, flat vector, clipart, diagram, generated text, letters, numbers, logo, watermark, signature, border, nudity, cleavage, lingerie, sexual pose"
)


def stable_seed(card_id: str) -> int:
    return int(hashlib.sha256(("pilgrims-ink-v3:" + card_id).encode()).hexdigest()[:8], 16) % 2_147_483_647


def scene_for(card: dict) -> str:
    if card["slug"] in SCENE_OVERRIDES:
        return SCENE_OVERRIDES[card["slug"]]
    if card["arcana"] == "major":
        return MAJOR_SCENES[card["slug"]]
    return MINOR[card["suit"]][card["rank"]]


def prompt_for(card: dict) -> str:
    realm = "the shared Pilgrim's Ink world of flowering ruins, carved wood, linen, hand-forged metal and distant mountains" if card["arcana"] == "major" else SUIT_WORLD[card["suit"]]
    subject_clause = "The still-life subject is clearly centered; absolutely no human figure is present." if card["slug"] in {"devil", "three-of-swords", "tower", "ten-of-swords"} else "The principal subject is centered and every face is clear, natural, kind-eyed, and unobstructed."
    return (
        f"{STYLE} Tarot card scene for {card['name']}: {scene_for(card)}. Setting: {realm}. "
        f"Vertical full-scene composition. {subject_clause} Everyone shown is fully clothed, nonsexual, and physically coherent. "
        "No printed title or frame inside the painting."
    )


def valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return path.stat().st_size > 30_000
    except Exception:
        return False


def fetch(card: dict, force: bool = False) -> tuple[Path, str, int]:
    target = RAW / f"{card['slug']}.jpg"
    prompt, seed = prompt_for(card), stable_seed(card["id"])
    if valid_image(target) and not force:
        return target, prompt, seed
    query = urllib.parse.urlencode({
        "width": WIDTH, "height": HEIGHT, "seed": seed, "model": MODEL,
        "safe": "true", "nofeed": "true", "enhance": "false", "negative_prompt": NEGATIVE,
    })
    url = ENDPOINT + urllib.parse.quote(prompt, safe="") + "?" + query
    for attempt in range(1, 7):
        started = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
            data = urllib.request.urlopen(request, timeout=300).read()
            with Image.open(io.BytesIO(data)) as image:
                image.convert("RGB").save(target, "JPEG", quality=96)
            if not valid_image(target):
                raise ValueError("response was not a valid detailed image")
            elapsed = time.monotonic() - started
            if elapsed < REQUEST_INTERVAL:
                time.sleep(REQUEST_INTERVAL - elapsed)
            return target, prompt, seed
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            wait = min(180, 20 * attempt)
            print(f"retry {card['slug']} attempt {attempt}: {exc}; waiting {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"could not generate {card['name']} after bounded retries")


def frame(raw_path: Path, card: dict, target: Path) -> None:
    source = Image.open(raw_path).convert("RGB")
    source = ImageOps.fit(source, (WIDTH, HEIGHT), Image.Resampling.LANCZOS, centering=(.5, .43))
    source = ImageEnhance.Color(source).enhance(.92)
    source = ImageEnhance.Contrast(source).enhance(.94)
    arr = np.asarray(source, dtype=np.float32)
    # Warm paper veil softens digital harshness without flattening linework.
    paper = np.array([239, 224, 194], dtype=np.float32)
    arr = arr * .92 + paper * .08
    image = Image.fromarray(np.uint8(np.clip(arr, 0, 255)), "RGB").convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    suit = card.get("suit") or "major"
    accents = {"major": (111, 70, 119), "wands": (180, 83, 45), "cups": (65, 122, 145), "swords": (91, 102, 135), "pentacles": (92, 122, 72)}
    accent = accents[suit]
    # Parchment footer and imperfect ink-like nested frame.
    draw.rounded_rectangle((14, 14, 706, 1106), radius=32, outline=(48, 40, 34, 235), width=6)
    draw.rounded_rectangle((25, 25, 695, 1095), radius=27, outline=(*accent, 225), width=4)
    draw.rounded_rectangle((55, 944, 665, 1078), radius=17, fill=(245, 235, 214, 238), outline=(48, 40, 34, 230), width=4)
    draw.line((79, 960, 641, 960), fill=(*accent, 160), width=2)
    title_font = ImageFont.truetype(FONT_BOLD, 31)
    sub_font = ImageFont.truetype(FONT_REG, 15)
    draw.text((360, 997), card["name"].upper(), font=title_font, fill=(43, 36, 31, 255), anchor="mm")
    subtitle = "MAJOR ARCANA" if card["arcana"] == "major" else f"{card['rank'].upper()} · {card['suit'].upper()}"
    draw.text((360, 1037), subtitle, font=sub_font, fill=(*accent, 255), anchor="mm")
    top = str(card["symbol"]) if card["arcana"] == "major" else {"ace":"A","two":"II","three":"III","four":"IV","five":"V","six":"VI","seven":"VII","eight":"VIII","nine":"IX","ten":"X","page":"PAGE","knight":"KNIGHT","queen":"QUEEN","king":"KING"}[card["rank"]]
    draw.rounded_rectangle((300, 28, 420, 84), radius=18, fill=(245, 235, 214, 215), outline=(*accent, 170), width=2)
    draw.text((360, 56), top, font=ImageFont.truetype(FONT_REG, 23), fill=(45, 38, 33, 255), anchor="mm")
    image.convert("RGB").save(target, "WEBP", quality=94, method=6)


def make_contact_sheet(cards: list[dict], name: str) -> None:
    thumbs = []
    for card in cards:
        image = Image.open(OUT / f"{card['slug']}.webp").convert("RGB")
        image.thumbnail((180, 280), Image.Resampling.LANCZOS)
        thumbs.append((card, image.copy()))
    cols = 7 if len(cards) > 14 else 4
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 190 + 20, rows * 290 + 20), "#211e1b")
    for i, (_, image) in enumerate(thumbs):
        sheet.paste(image, (10 + (i % cols) * 190, 10 + (i // cols) * 290))
    sheet.save(SHEETS / f"{name}.jpg", quality=91)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", default=[], help="Card slug; repeatable")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--contact-sheets", action="store_true")
    args = parser.parse_args()
    selected = [c for c in DEFAULT_CARDS if not args.only or c["slug"] in set(args.only)]
    if args.only and len(selected) != len(set(args.only)):
        raise SystemExit("Unknown card slug in --only")
    records = []
    for index, card in enumerate(selected, 1):
        raw, prompt, seed = fetch(card, force=args.force)
        target = OUT / f"{card['slug']}.webp"
        frame(raw, card, target)
        records.append({
            "id": card["id"], "name": card["name"], "file": target.name, "seed": seed,
            "model": MODEL, "prompt": prompt, "negative_prompt": NEGATIVE,
            "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
            "final_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        })
        print(f"[{index:02d}/{len(selected):02d}] {card['name']} -> {target.stat().st_size:,} bytes", flush=True)
    if not args.only:
        manifest = {
            "deck": "The Pilgrim's Ink", "style": "ai-assisted-hand-drawn-ink-watercolor",
            "provider": "Pollinations legacy Flux anonymous", "model": MODEL,
            "rate_limit": "one request per 16 seconds; bounded retries; no parallel requests",
            "credentials": "none", "research_sources": RESEARCH_SOURCES, "cards": records,
        }
        (OUT / "generation-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        if len({r["final_sha256"] for r in records}) != 78:
            raise RuntimeError("final artwork collision")
    if args.contact_sheets:
        groups = {"major": [c for c in DEFAULT_CARDS if c["arcana"] == "major"]}
        groups.update({suit: [c for c in DEFAULT_CARDS if c.get("suit") == suit] for suit in ("wands", "cups", "swords", "pentacles")})
        for name, cards in groups.items():
            if all((OUT / f"{c['slug']}.webp").is_file() for c in cards):
                make_contact_sheet(cards, name)
        print(f"contact sheets -> {SHEETS}")


if __name__ == "__main__":
    main()
