"""Generate 78 original fantasy-realistic Tarot paintings via rate-limited anonymous Flux.

Uses Pollinations' documented legacy anonymous endpoint at no more than one request
per 16 seconds. No credential is read, requested, or stored. Raw generations are
kept outside the bundled static tree; framed WebP cards and a provenance manifest
are bundled with OBus.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.card_catalog import DEFAULT_CARDS  # noqa: E402

RAW = ROOT / "assets" / "tarot-source-flux"
OUT = ROOT / "backend" / "static" / "art" / "cards"
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 720, 1120
ENDPOINT = "https://image.pollinations.ai/prompt/"
MODEL = "flux"
REQUEST_INTERVAL = 16.0
USER_AGENT = "Mozilla/5.0 OBus-Tarot-Deck/1.0"
FONT_BOLD = "C:/Windows/Fonts/georgiab.ttf"
FONT_REG = "C:/Windows/Fonts/georgia.ttf"

RESEARCH_SOURCES = [
    "https://www.themorgan.org/collection/tarot-cards",
    "https://commons.wikimedia.org/wiki/Category:Pierpont_Morgan-Bergamo_Visconti-Sforza_Tarot",
    "https://www.britishmuseum.org/collection/object/P_1845-0825-485",
    "https://commons.wikimedia.org/wiki/Sola-Busca_tarot_deck",
    "https://sacred-texts.com/tarot/pkt/",
    "https://wellcomecollection.org/works/vvhjuc5a",
    "https://www.britishmuseum.org/collection/object/P_1904-0511-47-1-78",
    "https://bookofadeptus.ryanginter.com/",
    "https://www.nataliaweedy.com/projects/tarot-campaign",
]

MAJOR_SCENES = {
    "fool": "a fully human young traveler walking on foot toward a mountain cliff at dawn, layered leather and linen clothing, an ordinary realistic four-legged white wolf walking separately beside their boots as a small companion, never ridden and never anthropomorphic, wildflowers, small travel pack, hopeful expression",
    "magician": "a focused human mage at an obsidian altar bearing a wand, chalice, sword and golden pentacle, one hand raised to the stars and one toward the earth, arcane observatory, violet energy",
    "high-priestess": "a serene fully clothed human oracle between one black marble pillar and one ivory pillar, silver moon crown, blue veil over a high-necked layered blue and silver ceremonial gown, ancient scroll, moonlit temple and dark reflecting pool",
    "empress": "a regal human empress seated in a living garden throne, embroidered crimson and gold gown, wheat field, waterfall, pomegranate branches, maternal strength",
    "emperor": "a mature human emperor in engraved bronze plate armor on a stone throne, red cloak, ram motifs, mountain citadel, austere sunrise",
    "hierophant": "a venerable human high priest in an immense candlelit cathedral archive, ornate ceremonial robes, two acolytes kneeling, crossed keys, compassionate authority",
    "lovers": "two fully clothed adult human travelers clearly visible at center in an open enchanted grove, standing face to face and holding hands, their complete bodies unobstructed, a luminous winged guardian floating behind and above them, flowering tree and flame tree, no buildings, intimate choice and sacred union",
    "chariot": "an armored human champion driving a celestial chariot through a storm, one black and one white lion pulling in balance, star canopy, wind-torn blue cloak",
    "strength": "a calm adult human woman gently closing the jaws of a realistic golden lion without force, sunlit overgrown ruins, white dress, red sash, infinity halo",
    "hermit": "an elderly human sage alone on a snowy mountain ridge, weathered wool cloak, raised six-pointed star lantern, staff, distant valley in blue twilight",
    "wheel-of-fortune": "a colossal luminous wheel turning inside a cosmic temple, four mythic guardians reading books at the corners, human seer below, clouds and constellations",
    "justice": "a fully clothed armored human judge seated frontally in a marble tribunal, both arms and hands visible, holding a large unmistakable perfectly balanced golden two-pan scale in the left hand and one upright silver sword in the right hand, red robe, clear gaze",
    "hanged-man": "a fully clothed human knight wearing trousers, boots, long tunic and light armor, suspended upside down by exactly one ankle from a vast living world tree, the other leg bent into a cross, calm illuminated face clearly visible below the torso, green-gold halo, misty forest, no exposed torso or thighs",
    "death": "a black-armored human knight riding a realistic pale horse across an ashen battlefield, black banner with white rose, fallen crown, distant sunrise promising renewal",
    "temperance": "a luminous winged human healer standing with one foot in a river and one on stone, pouring glowing water between two vessels, iris flowers, path to sunrise",
    "devil": "an imposing horned fantasy sovereign seated alone on an obsidian throne, two fully clothed adult human travelers standing far apart at the base and visibly breaking loose chains with their own hands, nobody touching or embracing, ember light, temptation and liberation, strictly nonsexual",
    "tower": "a tall stone tower on a mountain struck by branching lightning, crown blasted from the roof, two fully clothed human figures escaping falling masonry, violent rain and fire, extreme cinematic drama",
    "star": "a human stargazer kneeling beside a crystal lake, pouring water from two silver vessels onto land and water, one huge eight-pointed star and seven smaller stars, serene blue night",
    "moon": "a cloaked human wanderer on a moonlit causeway between two ancient towers, a realistic wolf and hound calling to a vast crescent moon, river crab emerging, dreamlike fog",
    "sun": "a joyful young human champion riding a realistic white horse through sunflowers, red solar banner, vast radiant sun, warm clear daylight, innocence and vitality",
    "judgement": "a magnificent winged angel sounding a golden trumpet above a valley, fully clothed human souls rising from opened stone tombs, white-gold dawn, awakening and forgiveness",
    "world": "an adult human dancer wrapped in flowing violet cloth inside a living laurel wreath suspended above a celestial garden, four realistic guardian creatures at the corners, completion and harmony",
}

MINOR = {
    "wands": {
        "ace":"a solitary human hand raising a living wooden wand sprouting green leaves from a volcanic valley, divine firelight",
        "two":"a human noble on a battlement holding a wand and a small globe while choosing between two distant roads across the Emberwild",
        "three":"a human explorer watching three crimson-sailed ships cross a glowing lava sea, three planted wands, expansion and foresight",
        "four":"four flowering wands forming a ceremonial arch while a group of fully clothed human villagers celebrate at a hilltop sanctuary",
        "five":"five young human warriors practicing with wooden staves in an energetic but nonlethal sparring circle, embers and dust",
        "six":"a victorious human rider returning through a city on a realistic horse, laurel-topped wand, cheering procession, warm copper light",
        "seven":"a determined human defender on high ground holding one wand against six challengers below, volcanic sunset, courage",
        "eight":"eight burning wands streaking like meteors across a vast valley toward a distant citadel, one human messenger watching, speed",
        "nine":"a wounded but standing human guardian leaning on a wand before a fence of eight wands, bandaged brow, dawn endurance",
        "ten":"a burdened human traveler carrying ten heavy wands toward a distant town through ash and sunset, believable strain",
        "page":"a youthful human messenger studying a budding wand in a desert of red cliffs, curious expression, light leather clothing",
        "knight":"a human knight in copper armor charging on a realistic dark horse while raising a fiery wand, sparks and wind",
        "queen":"a powerful human queen on a carved sunflower throne, black cat at her feet, blooming wand, copper and crimson fabrics",
        "king":"a mature human king in ember-forged armor on a basalt throne, living wand, salamander motifs, volcanic kingdom",
    },
    "cups": {
        "ace":"an ornate silver chalice overflowing with luminous water above a moonlit pool, a white dove descending, lotus flowers",
        "two":"wide shot of exactly two fully clothed adult human travelers, both clearly visible from waist up on a moonlit beach, facing each other and each holding one ornate silver goblet while gently touching the two cup rims together, mutual trust, no masks, no modern clothing, no city street",
        "three":"three adult human friends raising silver cups in celebration beside a moonlit garden fountain, abundance and friendship",
        "four":"a contemplative human seated beneath a coastal tree ignoring three cups while a luminous fourth cup appears from mist",
        "five":"a grieving cloaked human before three spilled cups while two upright cups remain behind, ruined bridge and rain",
        "six":"one human child offering a flower-filled cup to another in an old seaside courtyard, four cups nearby, memory and kindness",
        "seven":"a fully clothed human dreamer wearing a high-necked layered blue robe, shown from behind and in profile, facing exactly seven separate ornate chalices floating in a wide visible semicircle, the cups contain visions of a jewel, laurel, dragon, tower, shrouded figure, serpent and human face, no exposed chest",
        "eight":"a solitary human leaving eight carefully stacked cups and walking toward moonlit mountains, difficult departure",
        "nine":"a satisfied human host seated before nine displayed golden cups in a warm coastal hall, earned contentment",
        "ten":"wide landscape shot of exactly four fully clothed humans, two adult parents and two children, standing together with arms raised beneath a bright rainbow made of ten luminous cups, peaceful sea village and home clearly visible behind them, joyful family completion, no table, no single central chalice",
        "page":"a youthful human messenger holding a silver cup from which a small realistic fish leaps, blue silk, moonlit beach",
        "knight":"a human knight in silver-blue armor on a realistic white horse offering a cup, slow river crossing",
        "queen":"a regal human queen beside the sea holding an intricate lidded chalice, silver crown, layered blue silk, reflective water",
        "king":"a mature human king on a stone throne surrounded by turbulent sea yet perfectly calm, golden cup and scepter",
    },
    "swords": {
        "ace":"a powerful human hand raising one flawless silver sword through storm clouds, golden crown and laurel around the blade",
        "two":"a blindfolded fully clothed human woman seated at a moonlit shore holding two crossed swords in perfect balance",
        "three":"a realistic crimson heart pierced by three silver swords beneath cold rain clouds, distant human silhouette, emotional consequence",
        "four":"an armored human knight resting on a stone bier inside a quiet chapel, three swords above and one below, stained glass light",
        "five":"a human victor gathering three swords while two defeated figures leave a windy shore, two swords on the ground, moral ambiguity",
        "six":"a human ferryman carrying an adult and child across dark water in a narrow boat, six swords planted upright, passage through grief",
        "seven":"a stealthy human scout carrying five swords from a military camp while two remain planted, dawn strategy, no violence",
        "eight":"a blindfolded fully clothed human woman loosely bound among eight swords in shallow water, distant open path, self-limitation",
        "nine":"a human waking from a nightmare in a stone chamber, nine swords aligned on the wall, moonlight, grief and anxiety",
        "ten":"a fallen armored human warrior on a stormy plain with ten swords planted around rather than graphically through the body, sunrise on horizon, ending and renewal",
        "page":"a youthful human scout holding a raised sword on a windy hill, alert stance, storm birds, light steel armor",
        "knight":"a human knight in polished steel charging a realistic gray horse through violent wind, sword forward, dynamic anatomy",
        "queen":"a stern human queen seated on a high stone throne, upright sword, crown of butterflies, windblown silver cloak",
        "king":"a mature human king in dark steel armor on a storm citadel throne, upright sword, blue mantle, intellectual command",
    },
    "pentacles": {
        "ace":"a powerful human hand presenting one engraved golden pentacle above a lush garden gate, mountain path, harvest sunlight",
        "two":"a nimble human merchant balancing two golden pentacles connected by an infinity ribbon, ships on rough water behind",
        "three":"three human artisans collaborating beneath a carved cathedral arch, architect plans, stonework and three pentacles",
        "four":"a guarded human noble holding one pentacle while two rest beneath their boots and one above the crown, walled city",
        "five":"two poor but resilient human travelers crossing snow beneath a glowing stained-glass window with five pentacles",
        "six":"a wealthy human benefactor distributing coins to two kneeling adults while holding balanced scales, public square",
        "seven":"a tired human gardener leaning on a tool and assessing seven golden pentacles growing on a living vine, evening light",
        "eight":"a focused human metalsmith engraving the eighth pentacle at a workbench while seven finished pieces hang nearby",
        "nine":"an independent human noble in an embroidered garden with nine pentacles and a hooded falcon, vineyard at golden hour",
        "ten":"three generations of a fully clothed human family beneath an arch of ten pentacles, dogs, ancestral estate, legacy",
        "page":"a youthful human scholar holding a glowing pentacle in both hands in a spring meadow, green-gold traveling clothes",
        "knight":"a human knight in bronze armor on a realistic sturdy black horse holding one pentacle, plowed fields and mountains",
        "queen":"a regal human queen in green velvet and gold embroidery cradling a pentacle on a garden throne, rabbit and roses",
        "king":"a mature human king in ornate bronze and emerald armor on a vine-carved throne, golden pentacle, castle and harvest fields",
    },
}

SUIT_WORLD = {
    "wands":"the Emberwild realm of volcanic cliffs, charcoal forests, copper armor and cinematic orange firelight",
    "cups":"the Tidemoon realm of moonlit coasts, blue glass, silver cloth, water reflections and cool cinematic light",
    "swords":"the Stormhold realm of wind-carved citadels, realistic steel plate, rain, clouds and cold directional light",
    "pentacles":"the Verdant Crown realm of mountain gardens, mossy ruins, bronze, gold, harvest fields and warm natural light",
}

NEGATIVE = "flat vector, cartoon, diagram, stick figure, low detail, anime, comic, text, letters, numbers, border, logo, watermark, signature, extra limbs, malformed hands, fused bodies, duplicate person, blurry, plastic skin, existing franchise character, nudity, bare chest, cleavage, lingerie, sexual pose"


def stable_seed(card_id: str) -> int:
    return int(hashlib.sha256(card_id.encode()).hexdigest()[:8], 16) % 2_147_483_647


def prompt_for(card: dict) -> str:
    if card["arcana"] == "major":
        scene = MAJOR_SCENES[card["slug"]]
        realm = "a coherent original late-medieval high-fantasy world"
    else:
        scene = MINOR[card["suit"]][card["rank"]]
        realm = SUIT_WORLD[card["suit"]]
    return (
        f"Original fantasy realistic Tarot painting for {card['name']}. {scene}. "
        f"{realm}. Anatomically believable human characters, natural hands, detailed expressive faces, "
        "all people fully clothed in layered practical fantasy garments, nonsexual presentation, physically believable skin, hair, leather, cloth, metal, stone and water, cinematic vertical full-scene composition, "
        "foreground subject with midground event and distant environment, atmospheric perspective, volumetric rim lighting, "
        "rich oil-painted texture, intricate but readable symbolism, dramatic fantasy realism, museum-quality digital painting, "
        "entirely original character and costume design, no text, no border, no logo, no signature."
    )


def valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        return path.stat().st_size > 25_000
    except Exception:
        return False


def fetch(card: dict) -> tuple[Path, str, int]:
    target = RAW / f"{card['slug']}.jpg"
    prompt = prompt_for(card); card_seed = stable_seed(card["id"])
    if valid_image(target):
        return target, prompt, card_seed
    query = urllib.parse.urlencode({
        "width": WIDTH, "height": HEIGHT, "seed": card_seed, "model": MODEL,
        "safe": "true", "nofeed": "true", "enhance": "false",
        "negative_prompt": NEGATIVE,
    })
    url = ENDPOINT + urllib.parse.quote(prompt, safe="") + "?" + query
    for attempt in range(1, 9):
        started = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
            data = urllib.request.urlopen(req, timeout=300).read()
            with Image.open(io.BytesIO(data)) as image:
                image.convert("RGB").save(target, "JPEG", quality=95)
            if not valid_image(target):
                raise ValueError("generation was not a valid detailed image")
            elapsed = time.monotonic() - started
            if elapsed < REQUEST_INTERVAL:
                time.sleep(REQUEST_INTERVAL - elapsed)
            return target, prompt, card_seed
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            wait = min(180, 25 * attempt)
            print(f"retry {card['slug']} attempt {attempt}: {exc}; waiting {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"could not generate {card['name']} after bounded retries")


def make_frame(raw_path: Path, card: dict, target: Path):
    source = Image.open(raw_path).convert("RGB")
    source = ImageOps.fit(source, (WIDTH, HEIGHT), Image.Resampling.LANCZOS, centering=(.5, .44))
    arr = np.asarray(source, dtype=np.float32)
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    edge = ((xx-WIDTH/2)/(WIDTH*.75))**2 + ((yy-HEIGHT/2)/(HEIGHT*.8))**2
    arr *= np.clip(1-edge*.18, .64, 1)[...,None]
    image = Image.fromarray(np.uint8(np.clip(arr, 0, 255)), "RGB").convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    suit = card.get("suit") or "major"
    accents = {"major":(218,177,82),"wands":(224,116,44),"cups":(91,188,215),"swords":(171,193,218),"pentacles":(213,165,62)}
    accent = accents[suit]
    # restrained double frame preserves the painting
    draw.rounded_rectangle((15,15,705,1105), radius=30, outline=(*accent,235), width=8)
    draw.rounded_rectangle((29,29,691,1091), radius=24, outline=(235,225,202,175), width=2)
    # Exact Minor Arcana suit-count markers preserve Marseille-style legibility
    # even when the narrative painting abstracts or occludes individual objects.
    rank_count = {"ace":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10}
    def pip(x, y, suit, size=12):
        if suit == "wands":
            draw.line((x-size*.45,y+size,x+size*.45,y-size), fill=(*accent,235), width=3)
        elif suit == "cups":
            draw.arc((x-size,y-size,x+size,y+size*.7), 0, 180, fill=(*accent,235), width=3)
            draw.line((x,y+size*.6,x,y+size*1.25), fill=(*accent,235), width=3)
            draw.line((x-size*.55,y+size*1.25,x+size*.55,y+size*1.25), fill=(*accent,235), width=3)
        elif suit == "swords":
            draw.line((x,y-size*1.15,x,y+size), fill=(*accent,235), width=3)
            draw.line((x-size*.65,y+size*.45,x+size*.65,y+size*.45), fill=(*accent,235), width=3)
            draw.polygon(((x,y-size*1.5),(x-size*.3,y-size),(x+size*.3,y-size)), fill=(*accent,235))
        else:
            draw.ellipse((x-size,y-size,x+size,y+size), outline=(*accent,235), width=3)
            star=[]
            for i in range(10):
                angle=-math.pi/2+i*math.pi/5; radius=size*(.72 if i%2==0 else .3)
                star.append((x+math.cos(angle)*radius,y+math.sin(angle)*radius))
            draw.line(star+[star[0]], fill=(*accent,220), width=2, joint="curve")
    if card["arcana"] != "major":
        count = rank_count.get(card["rank"])
        if count:
            left=(count+1)//2; right=count-left
            for side, total in ((52,left),(668,right)):
                if total:
                    for i in range(total): pip(side, 180+i*(650/max(1,total-1)) if total>1 else 500, card["suit"], 10)
        else:
            pip(52,500,card["suit"],16); pip(668,500,card["suit"],16)
    # translucent title plate
    draw.rounded_rectangle((55,944,665,1075), radius=18, fill=(5,10,18,215), outline=(*accent,235), width=4)
    title_font = ImageFont.truetype(FONT_BOLD, 31)
    sub_font = ImageFont.truetype(FONT_REG, 15)
    draw.text((360,989), card["name"].upper(), font=title_font, fill=(246,238,220,255), anchor="mm", stroke_width=1, stroke_fill=(0,0,0,180))
    subtitle = "MAJOR ARCANA" if card["arcana"]=="major" else f"{card['rank'].upper()} · {card['suit'].upper()}"
    draw.text((360,1031), subtitle, font=sub_font, fill=(*accent,255), anchor="mm")
    top_rank = {"ace":"A","two":"II","three":"III","four":"IV","five":"V","six":"VI","seven":"VII","eight":"VIII","nine":"IX","ten":"X","page":"PAGE","knight":"KNIGHT","queen":"QUEEN","king":"KING"}
    top_label = str(card["symbol"]) if card["arcana"] == "major" else top_rank[card["rank"]]
    draw.text((360,61), top_label, font=ImageFont.truetype(FONT_REG,25), fill=(245,234,205,245), anchor="mm", stroke_width=1, stroke_fill=(0,0,0,180))
    image.convert("RGB").save(target, "WEBP", quality=94, method=6)


def main():
    records=[]
    for index, card in enumerate(DEFAULT_CARDS, 1):
        raw, prompt, card_seed = fetch(card)
        target = OUT / f"{card['slug']}.webp"
        make_frame(raw, card, target)
        records.append({
            "id": card["id"], "name": card["name"], "file": target.name,
            "seed": card_seed, "model": MODEL, "prompt": prompt,
            "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
            "final_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        })
        print(f"[{index:02d}/78] {card['name']} -> {target.stat().st_size:,} bytes", flush=True)
    manifest={
        "deck":"The Realms of Arcana", "style":"fantasy-realistic-painterly",
        "provider":"Pollinations legacy Flux anonymous", "model":MODEL,
        "rate_limit":"one request per 16 seconds; bounded retries; no parallel requests",
        "credentials":"none", "research_sources":RESEARCH_SOURCES, "cards":records,
    }
    (OUT/"generation-manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    if len({r['final_sha256'] for r in records}) != 78:
        raise RuntimeError("final artwork collision")
    print("generated and framed 78 fantasy-realistic Tarot cards", flush=True)

if __name__ == "__main__":
    main()
