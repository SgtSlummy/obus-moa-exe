"""Import and restore Pamela Colman Smith's public-domain 1909 Tarot deck.

Downloads verified originals from Wikimedia Commons, preserves the hand-drawn
artwork, applies restrained color/paper restoration and an OBus outer mount,
and writes 78 WebP assets plus provenance and contact sheets.
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import math
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.card_catalog import DEFAULT_CARDS  # noqa: E402

RAW = ROOT / "assets" / "tarot-source-rws-public-domain"
OUT = ROOT / "backend" / "static" / "art" / "cards"
SHEETS = ROOT / "assets" / "tarot-contact-sheets-rws-restored"
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
SHEETS.mkdir(parents=True, exist_ok=True)
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "OBus-Tarot-Restoration/1.0 (public-domain art import)"
WIDTH, HEIGHT = 720, 1120
FONT = "C:/Windows/Fonts/georgia.ttf"
RESEARCH_SOURCES = [
    "https://en.wikipedia.org/wiki/Rider%E2%80%93Waite_Tarot",
    "https://commons.wikimedia.org/wiki/Category:Rider-Waite_tarot_deck",
    "https://www.themorgan.org/collection/tarot-cards",
    "https://www.britishmuseum.org/collection/object/P_1845-0825-485",
    "https://commons.wikimedia.org/wiki/Sola-Busca_tarot_deck",
    "https://sacred-texts.com/tarot/pkt/",
    "https://wellcomecollection.org/works/vvhjuc5a",
    "https://www.britishmuseum.org/collection/object/P_1904-0511.47.1-78",
]

MAJOR_FILES = {
    "fool": "File:RWS Tarot 00 Fool.jpg", "magician": "File:RWS Tarot 01 Magician.jpg",
    "high-priestess": "File:RWS Tarot 02 High Priestess.jpg", "empress": "File:RWS Tarot 03 Empress.jpg",
    "emperor": "File:RWS Tarot 04 Emperor.jpg", "hierophant": "File:RWS Tarot 05 Hierophant.jpg",
    "lovers": "File:RWS Tarot 06 Lovers.jpg", "chariot": "File:RWS Tarot 07 Chariot.jpg",
    "strength": "File:RWS Tarot 08 Strength.jpg", "hermit": "File:RWS Tarot 09 Hermit.jpg",
    "wheel-of-fortune": "File:RWS Tarot 10 Wheel of Fortune.jpg", "justice": "File:RWS Tarot 11 Justice.jpg",
    "hanged-man": "File:RWS Tarot 12 Hanged Man.jpg", "death": "File:RWS Tarot 13 Death.jpg",
    "temperance": "File:RWS Tarot 14 Temperance.jpg", "devil": "File:RWS Tarot 15 Devil.jpg",
    "tower": "File:RWS Tarot 16 Tower.jpg", "star": "File:RWS Tarot 17 Star.jpg",
    "moon": "File:RWS Tarot 18 Moon.jpg", "sun": "File:RWS Tarot 19 Sun.jpg",
    "judgement": "File:RWS Tarot 20 Judgement.jpg", "world": "File:RWS Tarot 21 World.jpg",
}
RANK_NUM = {"ace": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
            "eight": 8, "nine": 9, "ten": 10, "page": 11, "knight": 12, "queen": 13, "king": 14}
SUIT_PREFIX = {"wands": "Wands", "cups": "Cups", "swords": "Swords", "pentacles": "Pents"}
ACCENTS = {"major": (105, 70, 127), "wands": (179, 81, 42), "cups": (57, 113, 143),
           "swords": (78, 93, 127), "pentacles": (88, 117, 61)}


def file_title(card: dict) -> str:
    if card["arcana"] == "major":
        return MAJOR_FILES[card["slug"]]
    return f"File:{SUIT_PREFIX[card['suit']]}{RANK_NUM[card['rank']]:02d}.jpg"


def api_metadata(titles: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for start in range(0, len(titles), 25):
        batch = titles[start:start + 25]
        query = urllib.parse.urlencode({
            "action": "query", "titles": "|".join(batch), "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist|DateTimeOriginal",
            "format": "json", "formatversion": "2",
        })
        request = urllib.request.Request(API + "?" + query, headers={"User-Agent": USER_AGENT})
        payload = json.load(urllib.request.urlopen(request, timeout=120))
        for page in payload["query"]["pages"]:
            if page.get("missing"):
                raise RuntimeError(f"Missing Commons file: {page['title']}")
            result[page["title"]] = page
    return result


def download(page: dict, card: dict) -> Path:
    info = page["imageinfo"][0]
    license_name = html.unescape(info.get("extmetadata", {}).get("LicenseShortName", {}).get("value", ""))
    if license_name != "Public domain":
        raise RuntimeError(f"{page['title']} is not marked Public domain: {license_name}")
    target = RAW / f"{card['slug']}.jpg"
    if target.is_file() and target.stat().st_size > 40_000:
        with Image.open(target) as existing:
            if 760 <= existing.width <= 840 and existing.height >= 1250:
                return target
    if card["arcana"] == "major":
        mirror_name = page["title"].removeprefix("File:").replace(" ", "_")
        mirror_path = f"textures/tarot_cards/major/{mirror_name}"
    else:
        mirror_name = f"{SUIT_PREFIX[card['suit']]}{RANK_NUM[card['rank']]:02d}.jpg"
        mirror_path = f"textures/tarot_cards/{card['suit']}/{mirror_name}"
    clean_url = "https://raw.githubusercontent.com/Zailef/whispers-of-the-carnival/main/" + mirror_path
    request = urllib.request.Request(clean_url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    data = None
    for attempt in range(1, 8):
        try:
            data = urllib.request.urlopen(request, timeout=180).read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 429:
                raise
            wait = max(int(exc.headers.get("Retry-After", "0") or 0), min(120, 12 * attempt))
            print(f"Wikimedia rate limit for {card['slug']}; waiting {wait}s", flush=True)
            time.sleep(wait)
    if data is None:
        raise RuntimeError(f"Could not download {page['title']} after bounded retries")
    with Image.open(io.BytesIO(data)) as image:
        if image.width < 700 or image.height < 1100:
            raise RuntimeError(f"Unexpectedly small source for {page['title']}: {image.size}")
        image.convert("RGB").save(target, "JPEG", quality=97)
    time.sleep(.1)
    return target


def restore(source_path: Path, card: dict, target: Path) -> None:
    source = Image.open(source_path).convert("RGB")
    # Trim scanner-edge whitespace without touching the illustrated card.
    source = ImageOps.crop(source, border=(12, 12, 12, 12))
    source = ImageEnhance.Color(source).enhance(1.06)
    source = ImageEnhance.Contrast(source).enhance(1.035)
    source = ImageEnhance.Sharpness(source).enhance(1.08)
    card_img = ImageOps.contain(source, (650, 1060), Image.Resampling.LANCZOS)

    # Warm cotton-paper mount with restrained suit tint; the historic drawing is unchanged.
    canvas = Image.new("RGB", (WIDTH, HEIGHT), (238, 226, 202))
    paper_noise = np.random.default_rng(int(hashlib.sha256(card["id"].encode()).hexdigest()[:8], 16)).normal(0, 2.2, (HEIGHT, WIDTH, 1))
    arr = np.asarray(canvas, dtype=np.float32) + paper_noise
    canvas = Image.fromarray(np.uint8(np.clip(arr, 0, 255)), "RGB")
    x = (WIDTH - card_img.width) // 2
    y = (HEIGHT - card_img.height) // 2
    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((x + 7, y + 10, x + card_img.width + 7, y + card_img.height + 10), radius=10, fill=(28, 23, 19, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)
    canvas.alpha_composite(card_img.convert("RGBA"), (x, y))

    draw = ImageDraw.Draw(canvas, "RGBA")
    suit = card.get("suit") or "major"
    accent = ACCENTS[suit]
    draw.rounded_rectangle((9, 9, 711, 1111), radius=31, outline=(48, 39, 31, 235), width=7)
    draw.rounded_rectangle((20, 20, 700, 1100), radius=26, outline=(*accent, 230), width=4)
    draw.line((38, 31, 682, 31), fill=(255, 247, 226, 190), width=2)
    # Small provenance line on the mount, outside Smith's artwork.
    font = ImageFont.truetype(FONT, 11)
    draw.text((360, 1090), "PAMELA COLMAN SMITH · 1909 · PUBLIC DOMAIN", font=font, fill=(55, 46, 38, 190), anchor="mm")
    canvas.convert("RGB").save(target, "WEBP", quality=94, method=6)


def make_contact_sheet(cards: list[dict], name: str) -> None:
    cols = 7 if len(cards) > 14 else 4
    rows = math.ceil(len(cards) / cols)
    sheet = Image.new("RGB", (cols * 190 + 20, rows * 290 + 20), (29, 25, 22))
    for index, card in enumerate(cards):
        image = Image.open(OUT / f"{card['slug']}.webp").convert("RGB")
        image.thumbnail((180, 280), Image.Resampling.LANCZOS)
        sheet.paste(image, (10 + (index % cols) * 190, 10 + (index // cols) * 290))
    sheet.save(SHEETS / f"{name}.jpg", quality=92)


def main() -> None:
    title_by_id = {card["id"]: file_title(card) for card in DEFAULT_CARDS}
    metadata = api_metadata(list(title_by_id.values()))
    records = []
    for index, card in enumerate(DEFAULT_CARDS, 1):
        title = title_by_id[card["id"]]
        page = metadata[title]
        info = page["imageinfo"][0]
        source = download(page, card)
        target = OUT / f"{card['slug']}.webp"
        restore(source, card, target)
        records.append({
            "id": card["id"], "name": card["name"], "file": target.name,
            "artist": "Pamela Colman Smith", "year": 1909, "license": "Public domain",
            "source_page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe=":_"),
            "source_url": info["url"].split("?", 1)[0], "source_width": info["width"], "source_height": info["height"],
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "final_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        })
        print(f"[{index:02d}/78] {card['name']} -> {target.stat().st_size:,} bytes", flush=True)
    if len(records) != 78 or len({r["final_sha256"] for r in records}) != 78:
        raise RuntimeError("Deck count or uniqueness check failed")
    manifest = {
        "deck": "The Pilgrim's Ink · Smith Restoration", "style": "restored-public-domain-hand-drawn-watercolor",
        "provider": "Wikimedia Commons public-domain scans", "artist": "Pamela Colman Smith", "original_publication_year": 1909,
        "credentials": "none", "processing": "color/contrast restoration, parchment mount, deterministic OBus outer frame; source illustration unchanged",
        "research_sources": RESEARCH_SOURCES, "cards": records,
    }
    (OUT / "generation-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    groups = {"major": [c for c in DEFAULT_CARDS if c["arcana"] == "major"]}
    groups.update({suit: [c for c in DEFAULT_CARDS if c.get("suit") == suit] for suit in ("wands", "cups", "swords", "pentacles")})
    for name, cards in groups.items():
        make_contact_sheet(cards, name)
    print(f"restored 78 public-domain hand-drawn cards; contact sheets -> {SHEETS}")


if __name__ == "__main__":
    main()
