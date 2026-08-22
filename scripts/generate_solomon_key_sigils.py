"""Build 16 OBus Key sigils from public-domain Ars Goetia seal linework."""
from __future__ import annotations

import base64
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

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.solomon_seals import SOLOMON_SEALS  # noqa: E402

OUT = ROOT / "backend" / "static" / "art" / "keys"
RAW = ROOT / "assets" / "solomon-key-seals-public-domain"
PREVIEW = RAW / "previews"
OUT.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)
PREVIEW.mkdir(parents=True, exist_ok=True)
API = "https://commons.wikimedia.org/w/api.php"
UA = "OBus-Solomon-Keys/1.0 (public-domain historical seal import)"
FONT_BOLD = "C:/Windows/Fonts/georgiab.ttf"
FONT_REG = "C:/Windows/Fonts/georgia.ttf"

ACCENTS = {
    "key-local-ollama": "#55d8ff", "key-codex-oauth": "#f5c451", "key-nous-oauth": "#ffb347",
    "key-nvidia-nim": "#79e35b", "key-anthropic": "#d69b72", "key-google-gemini": "#a98cff",
    "key-openrouter": "#58d6c7", "key-mistral": "#ff746c", "key-groq": "#f3a33c",
    "key-xai": "#d9e1f2", "key-together": "#9e86ff", "key-fireworks": "#ff5d57",
    "key-deepseek": "#4f8eff", "key-cerebras": "#ff9f43", "key-huggingface": "#ffd21e",
    "key-azure-openai": "#3ca9ef",
}
PROVIDERS = {
    "key-local-ollama": "OLLAMA", "key-codex-oauth": "CODEX / OPENAI", "key-nous-oauth": "NOUS / SOLAR",
    "key-nvidia-nim": "NVIDIA NIM", "key-anthropic": "ANTHROPIC", "key-google-gemini": "GOOGLE GEMINI",
    "key-openrouter": "OPENROUTER", "key-mistral": "MISTRAL", "key-groq": "GROQ", "key-xai": "XAI",
    "key-together": "TOGETHER AI", "key-fireworks": "FIREWORKS AI", "key-deepseek": "DEEPSEEK",
    "key-cerebras": "CEREBRAS", "key-huggingface": "HUGGING FACE", "key-azure-openai": "AZURE OPENAI",
}
COMMONS_URLS = {
    "File:02-Agares seal.png": "https://upload.wikimedia.org/wikipedia/commons/6/6d/02-Agares_seal.png",
    "File:03-Vassago seal.png": "https://upload.wikimedia.org/wikipedia/commons/0/08/03-Vassago_seal.png",
    "File:09-Paimon seal01.png": "https://upload.wikimedia.org/wikipedia/commons/f/fb/09-Paimon_seal01.png",
    "File:10-Buer seal.png": "https://upload.wikimedia.org/wikipedia/commons/d/d2/10-Buer_seal.png",
    "File:26-Bune seal01.png": "https://upload.wikimedia.org/wikipedia/commons/c/c6/26-Bune_seal01.png",
    "File:30-Forneus seal.png": "https://upload.wikimedia.org/wikipedia/commons/6/6d/30-Forneus_seal.png",
    "File:31-Foras seal.png": "https://upload.wikimedia.org/wikipedia/commons/d/d7/31-Foras_seal.png",
    "File:36-Stolas seal.png": "https://upload.wikimedia.org/wikipedia/commons/c/c7/36-Stolas_seal.png",
    "File:42-Vepar seal01.png": "https://upload.wikimedia.org/wikipedia/commons/9/92/42-Vepar_seal01.png",
    "File:55-Orobas seal.png": "https://upload.wikimedia.org/wikipedia/commons/6/62/55-Orobas_seal.png",
    "File:57-Ose seal.png": "https://upload.wikimedia.org/wikipedia/commons/7/75/57-Ose_seal.png",
    "File:60-Vapula seal.png": "https://upload.wikimedia.org/wikipedia/commons/1/10/60-Vapula_seal.png",
    "File:64-Haures seal.png": "https://upload.wikimedia.org/wikipedia/commons/7/7d/64-Haures_seal.png",
    "File:67-Amdusias seal.png": "https://upload.wikimedia.org/wikipedia/commons/5/58/67-Amdusias_seal.png",
    "File:70-Seere seal01.png": "https://upload.wikimedia.org/wikipedia/commons/4/42/70-Seere_seal01.png",
    "File:71-Dantalion seal.png": "https://upload.wikimedia.org/wikipedia/commons/9/98/71-Dantalion_seal.png",
}


def api_metadata() -> dict[str, dict]:
    titles = [item["file"] for item in SOLOMON_SEALS.values()]
    query = urllib.parse.urlencode({
        "action": "query", "titles": "|".join(titles), "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|Source|Artist|Description",
        "format": "json", "formatversion": "2",
    })
    request = urllib.request.Request(API + "?" + query, headers={"User-Agent": UA})
    payload = json.load(urllib.request.urlopen(request, timeout=120))
    pages = {page["title"]: page for page in payload["query"]["pages"]}
    if len(pages) != 16:
        raise RuntimeError(f"Expected 16 seal files, got {len(pages)}")
    return pages


def download(page: dict, key_id: str) -> Path:
    info = page["imageinfo"][0]
    license_name = info.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
    if license_name != "Public domain":
        raise RuntimeError(f"{page['title']} is not marked Public domain: {license_name}")
    target = RAW / f"{key_id}.png"
    if target.is_file() and target.stat().st_size > 10_000:
        return target
    source_url = info["url"].split("?", 1)[0]
    proxy_source = source_url.removeprefix("https://")
    url = "https://wsrv.nl/?url=" + proxy_source + "&w=450&h=450&fit=contain&output=png"
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*"})
    data = None
    for attempt in range(1, 8):
        try:
            data = urllib.request.urlopen(request, timeout=120).read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code != 429:
                raise
            wait = max(int(exc.headers.get("Retry-After", "0") or 0), min(120, 15 * attempt))
            print(f"Commons rate limit for {key_id}; waiting {wait}s", flush=True)
            time.sleep(wait)
    if data is None:
        raise RuntimeError(f"Unable to download {page['title']}")
    with Image.open(io.BytesIO(data)) as image:
        if image.width < 300 or image.height < 300:
            raise RuntimeError(f"Unexpectedly small seal {page['title']}: {image.size}")
        image.convert("RGBA").save(target, "PNG")
    time.sleep(.2)
    return target


def colored_seal(path: Path, color: str) -> Image.Image:
    source = Image.open(path).convert("RGBA")
    white = Image.new("RGBA", source.size, "white")
    composed = Image.alpha_composite(white, source).convert("RGB")
    gray = ImageOps.grayscale(composed)
    alpha = ImageOps.invert(gray)
    alpha = ImageOps.autocontrast(alpha, cutoff=1)
    alpha = alpha.point(lambda value: 0 if value < 18 else min(255, int(value * 1.35)))
    canvas = Image.new("RGBA", source.size, color)
    canvas.putalpha(alpha)
    canvas.thumbnail((255, 255), Image.Resampling.LANCZOS)
    return canvas


def make_svg(key_id: str, seal: dict, seal_image: Image.Image, accent: str) -> str:
    buffer = io.BytesIO()
    seal_image.save(buffer, "PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    name = seal["name"].upper()
    provider = PROVIDERS[key_id]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" role="img" aria-label="{provider} — Solomon Key {seal['number']}, {name}">
<title>{provider} — {name} SEAL</title>
<desc>Public-domain seal #{seal['number']} from the Ars Goetia section of the Lesser Key of Solomon, assigned to {provider}: {seal['reason']}.</desc>
<defs><radialGradient id="bg"><stop stop-color="{accent}" stop-opacity=".25"/><stop offset=".7" stop-color="#0d1120"/><stop offset="1" stop-color="#050711"/></radialGradient><filter id="glow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
<rect width="400" height="400" rx="42" fill="#050711"/>
<circle cx="200" cy="200" r="181" fill="url(#bg)" stroke="#f5c451" stroke-width="3"/>
<circle cx="200" cy="200" r="164" fill="none" stroke="{accent}" stroke-width="2" opacity=".75"/>
<text x="200" y="37" text-anchor="middle" fill="#eef3ff" font-family="Segoe UI,Arial" font-size="16" font-weight="700" letter-spacing="2">{provider}</text>
<image href="data:image/png;base64,{encoded}" x="72" y="65" width="256" height="256" preserveAspectRatio="xMidYMid meet" filter="url(#glow)"/>
<text x="200" y="345" text-anchor="middle" fill="#fff4c7" font-family="Georgia,serif" font-size="22" font-weight="700" letter-spacing="3">{name}</text>
<text x="200" y="372" text-anchor="middle" fill="{accent}" font-family="Segoe UI,Arial" font-size="12" letter-spacing="2">SOLOMON KEY · {seal['number']:02d}</text>
<text x="200" y="390" text-anchor="middle" fill="#929ab4" font-family="Segoe UI,Arial" font-size="8">PUBLIC-DOMAIN HISTORICAL SEAL LINEWORK</text>
</svg>'''


def render_preview(key_id: str, seal: dict, seal_image: Image.Image, accent: str) -> Image.Image:
    image = Image.new("RGB", (400, 400), "#050711")
    draw = ImageDraw.Draw(image)
    rgb = tuple(int(accent[i:i + 2], 16) for i in (1, 3, 5))
    draw.ellipse((18, 18, 382, 382), fill="#0d1120", outline="#f5c451", width=3)
    draw.ellipse((36, 36, 364, 364), outline=rgb, width=2)
    x, y = (400 - seal_image.width) // 2, 65 + (255 - seal_image.height) // 2
    image.paste(seal_image, (x, y), seal_image)
    draw.text((200, 28), PROVIDERS[key_id], fill="#eef3ff", font=ImageFont.truetype(FONT_BOLD, 14), anchor="mm")
    draw.text((200, 344), seal["name"].upper(), fill="#fff4c7", font=ImageFont.truetype(FONT_BOLD, 21), anchor="mm")
    draw.text((200, 371), f"SOLOMON KEY · {seal['number']:02d}", fill=rgb, font=ImageFont.truetype(FONT_REG, 12), anchor="mm")
    return image


def main() -> None:
    pages = {
        title: {"title": title, "imageinfo": [{"url": url, "width": 450, "height": 450, "mime": "image/png", "extmetadata": {"LicenseShortName": {"value": "Public domain"}}}]}
        for title, url in COMMONS_URLS.items()
    }
    records = []
    previews = []
    for index, (key_id, seal) in enumerate(SOLOMON_SEALS.items(), 1):
        page = pages[seal["file"]]
        source = download(page, key_id)
        accent = ACCENTS[key_id]
        symbol = colored_seal(source, accent)
        svg = make_svg(key_id, seal, symbol, accent)
        target = OUT / f"{key_id}.svg"
        target.write_text(svg, encoding="utf-8")
        preview = render_preview(key_id, seal, symbol, accent)
        preview.save(PREVIEW / f"{key_id}.png")
        previews.append(preview)
        info = page["imageinfo"][0]
        records.append({
            "key_id": key_id, "provider": PROVIDERS[key_id], "seal": seal["name"], "number": seal["number"],
            "reason": seal["reason"], "file": target.name, "license": "Public domain",
            "source_page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(seal["file"].replace(" ", "_"), safe=":_"),
            "source_url": info["url"].split("?", 1)[0], "source_width": info["width"], "source_height": info["height"],
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "final_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        })
        print(f"[{index:02d}/16] {PROVIDERS[key_id]} -> {seal['name']} #{seal['number']}", flush=True)
    if len({item["final_sha256"] for item in records}) != 16:
        raise RuntimeError("Solomon Key sigils are not unique")
    manifest = {
        "collection": "OBus Solomon Keys", "source_work": "Ars Goetia, The Lesser Key of Solomon",
        "edition_source": "The Book of the Goetia of Solomon the King (1904)",
        "provider": "Wikimedia Commons public-domain files", "keys": records,
    }
    (OUT / "solomon-key-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    sheet = Image.new("RGB", (4 * 410 + 20, 4 * 410 + 20), "#03050c")
    for i, preview in enumerate(previews):
        sheet.paste(preview, (10 + (i % 4) * 410, 10 + (i // 4) * 410))
    sheet.save(ROOT / "assets" / "solomon-keys-contact-sheet.jpg", quality=93)
    print("generated 16 public-domain Solomon Key sigils and contact sheet")


if __name__ == "__main__":
    main()
