"""Render 78 original fantasy-realistic Tarot paintings as local WebP assets."""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.card_catalog import DEFAULT_CARDS  # noqa: E402

OUT = ROOT / "backend" / "static" / "art" / "cards"
OUT.mkdir(parents=True, exist_ok=True)
W, H, S = 720, 1120, 2
SIZE = (W * S, H * S)
FONT_BOLD = "C:/Windows/Fonts/georgiab.ttf"
FONT_REG = "C:/Windows/Fonts/georgia.ttf"

WORLDS = {
    "major": ((12, 19, 38), (72, 42, 76), (232, 184, 89), (100, 145, 170)),
    "wands": ((25, 16, 22), (120, 42, 27), (242, 142, 53), (106, 85, 52)),
    "cups": ((8, 23, 42), (27, 82, 112), (125, 196, 210), (171, 106, 137)),
    "swords": ((15, 20, 32), (52, 65, 88), (177, 194, 210), (123, 45, 56)),
    "pentacles": ((15, 31, 24), (51, 87, 48), (215, 167, 67), (118, 83, 47)),
}

MAJOR = {
    "fool": ("cliff at dawn", "traveler", "white wolf", "sunrise"),
    "magician": ("arcane observatory", "mage", "elemental altar", "violet"),
    "high-priestess": ("moon temple", "oracle", "twin pillars", "moon"),
    "empress": ("golden garden", "empress", "wheat and waterfall", "warm"),
    "emperor": ("mountain citadel", "emperor", "stone throne", "red"),
    "hierophant": ("cathedral archive", "elder", "twin acolytes", "gold"),
    "lovers": ("enchanted grove", "pair", "luminous guardian", "rose"),
    "chariot": ("storm road", "warrior", "celestial chariot", "blue"),
    "strength": ("sunlit ruins", "woman", "lion", "gold"),
    "hermit": ("snow mountain", "elder", "star lantern", "cold"),
    "wheel-of-fortune": ("cosmic hall", "seer", "great wheel", "amber"),
    "justice": ("marble tribunal", "judge", "scales and sword", "silver"),
    "hanged-man": ("world tree", "sacrificed knight", "inversion", "green"),
    "death": ("ashen battlefield", "black knight", "white horse", "pale"),
    "temperance": ("river sanctuary", "winged healer", "two vessels", "teal"),
    "devil": ("obsidian cavern", "horned sovereign", "broken chains", "ember"),
    "tower": ("clifftop tower", "fleeing figures", "lightning", "fire"),
    "star": ("crystal lake", "stargazer", "eight stars", "azure"),
    "moon": ("moonlit causeway", "wanderer", "wolves and towers", "indigo"),
    "sun": ("sunflower plain", "young champion", "solar banner", "sun"),
    "judgement": ("valley of awakening", "angel", "rising souls", "white"),
    "world": ("celestial garden", "world dancer", "four guardians", "emerald"),
}

RANK_VALUE = {"ace": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def seed(text: str) -> int:
    return sum((i + 17) * ord(c) for i, c in enumerate(text)) & 0xFFFFFFFF


def C(rgb, factor=1.0):
    return tuple(max(0, min(255, int(v * factor))) for v in rgb)


class Canvas:
    def __init__(self, image: Image.Image):
        self.image = image
        self.d = ImageDraw.Draw(image, "RGBA")

    @staticmethod
    def b(box): return tuple(int(v * S) for v in box)
    @staticmethod
    def p(points): return [(int(x * S), int(y * S)) for x, y in points]

    def ellipse(self, box, fill, outline=None, width=1):
        self.d.ellipse(self.b(box), fill=fill, outline=outline, width=max(1, int(width * S)))

    def rectangle(self, box, fill, outline=None, width=1, radius=0):
        self.d.rounded_rectangle(self.b(box), radius=int(radius * S), fill=fill, outline=outline, width=max(1, int(width * S)))

    def polygon(self, points, fill, outline=None, width=1):
        pts = self.p(points); self.d.polygon(pts, fill=fill)
        if outline: self.d.line(pts + [pts[0]], fill=outline, width=max(1, int(width * S)), joint="curve")

    def line(self, points, fill, width=1, joint="curve"):
        self.d.line(self.p(points), fill=fill, width=max(1, int(width * S)), joint=joint)

    def text(self, xy, text, font, fill, anchor="mm", stroke=0, stroke_fill=(0, 0, 0, 0)):
        self.d.text((int(xy[0] * S), int(xy[1] * S)), text, font=font, fill=fill, anchor=anchor,
                    stroke_width=int(stroke * S), stroke_fill=stroke_fill)


def gradient_world(card, rng):
    key = card.get("suit") or "major"
    dark, mid, accent, secondary = WORLDS[key]
    h, w = H * S, W * S
    yy, xx = np.mgrid[0:h, 0:w]
    t = yy / h
    arr = np.empty((h, w, 3), dtype=np.float32)
    for ch in range(3):
        arr[..., ch] = dark[ch] * (1 - t) + mid[ch] * t
    lx = rng.uniform(.25, .75) * w; ly = rng.uniform(.15, .48) * h
    radius = np.sqrt(((xx - lx) / (w * .78)) ** 2 + ((yy - ly) / (h * .52)) ** 2)
    glow = np.clip(1 - radius, 0, 1) ** 2
    for ch in range(3): arr[..., ch] += glow * accent[ch] * .44
    haze = np.exp(-((yy - h * .58) / (h * .18)) ** 2)
    for ch in range(3): arr[..., ch] += haze * secondary[ch] * .14
    noise = rng_np(card["id"], (h, w))
    arr += (noise[..., None] - .5) * 18
    return Image.fromarray(np.uint8(np.clip(arr, 0, 255)), "RGB")


def rng_np(text, shape):
    return np.random.default_rng(seed(text)).random(shape, dtype=np.float32)


def atmospheric_background(c: Canvas, card, rng):
    key = card.get("suit") or "major"; _, mid, accent, secondary = WORLDS[key]
    # Distant mountains / architecture
    for layer in range(4):
        base = 610 + layer * 62
        pts = [(-20, H)]
        for x in range(-20, 780, 90):
            peak = base - rng.randint(30, 170) * (1 - layer * .13)
            pts.extend([(x, base), (x + 45, peak), (x + 90, base)])
        pts += [(780, H)]
        col = (*C(mid, .55 + layer * .11), 105 + layer * 20)
        c.polygon(pts, col)
    # Volumetric mist
    fog = Image.new("RGBA", SIZE, (0, 0, 0, 0)); f = ImageDraw.Draw(fog, "RGBA")
    for _ in range(16):
        x = rng.randint(-200, 900) * S; y = rng.randint(280, 820) * S
        rx = rng.randint(110, 310) * S; ry = rng.randint(28, 95) * S
        f.ellipse((x-rx, y-ry, x+rx, y+ry), fill=(*accent, rng.randint(8, 28)))
    fog = fog.filter(ImageFilter.GaussianBlur(45 * S)); c.image.alpha_composite(fog)
    # Stars/embers/dust
    c.d = ImageDraw.Draw(c.image, "RGBA")
    for _ in range(150):
        x, y = rng.randint(46, 674), rng.randint(80, 900)
        r = rng.choice([.5, .8, 1.2, 1.8, 2.4])
        c.ellipse((x-r, y-r, x+r, y+r), (*accent, rng.randint(30, 155)))


def paint_face_layer(cx, cy, scale, skin, light, shadow):
    layer = Image.new("RGBA", SIZE, (0, 0, 0, 0)); d = ImageDraw.Draw(layer, "RGBA")
    box = tuple(int(v*S) for v in (cx-42*scale, cy-56*scale, cx+42*scale, cy+56*scale))
    d.ellipse(box, fill=(*skin, 255))
    # Soft directional facial modeling
    for i in range(22, 0, -1):
        alpha = int(4 + (22-i)*.45)
        d.ellipse(tuple(int(v*S) for v in (cx-37*scale+i*.25, cy-50*scale+i*.2, cx+35*scale+i*.35, cy+50*scale)), fill=(*shadow, alpha))
    d.ellipse(tuple(int(v*S) for v in (cx-24*scale, cy-36*scale, cx+4*scale, cy+16*scale)), fill=(*light, 42))
    return layer.filter(ImageFilter.GaussianBlur(max(1, int(1.2*S))))


def draw_figure(c: Canvas, rng, cx=360, ground=850, scale=1.0, armor=True, cloak=True,
                crown=False, wings=False, inverted=False, youthful=False, elder=False, pose=0):
    dark, mid, accent, secondary = WORLDS["major"]
    skin = rng.choice([(190,134,102),(218,164,122),(151,98,77),(112,73,59),(231,188,151)])
    hair = rng.choice([(33,25,25),(75,47,28),(181,139,84),(52,49,62),(220,212,190)])
    light = C(skin, 1.22); shadow = C(skin, .62)
    sy = -1 if inverted else 1
    head_y = ground - 430 * scale
    if inverted: head_y = ground - 105 * scale
    torso_y = head_y + sy * 115 * scale
    hip_y = head_y + sy * 270 * scale
    shoulder = 72*scale; waist=50*scale
    # Cast shadow
    c.ellipse((cx-100*scale, ground-18*scale, cx+100*scale, ground+24*scale), (0,0,0,95))
    # Cloak behind figure
    if cloak:
        c.polygon([(cx-shoulder*1.1, torso_y-20*sy),(cx+shoulder*1.05,torso_y-10*sy),(cx+130*scale,ground-25*sy),(cx-125*scale,ground-20*sy)], (*mid,220), (*C(mid,.45),255), 4)
        c.line([(cx-shoulder,torso_y),(cx-92*scale,ground-70*sy)], (*C(accent,.78),130), 5)
    # Legs
    leg_end = ground if not inverted else ground-410*scale
    for dx in (-30,30):
        c.line([(cx+dx*.7,hip_y),(cx+dx,leg_end-25*sy)], (*C(mid,.5),255), 30*scale)
        c.line([(cx+dx,leg_end-25*sy),(cx+dx+18,leg_end)], (*C(dark,.55),255), 18*scale)
        c.line([(cx+dx-7,hip_y),(cx+dx-2,leg_end-30*sy)], (*accent,95), 5*scale)
    # Torso with taper and material panels
    c.polygon([(cx-shoulder,torso_y),(cx+shoulder,torso_y),(cx+waist,hip_y),(cx-waist,hip_y)], (*C(mid,.88),255), (*C(dark,.42),255), 5)
    if armor:
        c.polygon([(cx-shoulder,torso_y+10*sy),(cx,torso_y-14*sy),(cx+shoulder,torso_y+10*sy),(cx+waist*.8,hip_y-35*sy),(cx-waist*.8,hip_y-35*sy)], (*C(secondary,.72),245), (*C(accent,.72),255), 4)
        for off in (-35,0,35): c.line([(cx+off,torso_y+15*sy),(cx+off*.65,hip_y-40*sy)], (*accent,110), 3)
        c.line([(cx-54,torso_y+52*sy),(cx+54,torso_y+52*sy)], (240,245,250,80), 4)
    # Arms with readable gesture
    hand_y_l = torso_y + sy*(120 + pose*9)*scale
    hand_y_r = torso_y + sy*(100 - pose*8)*scale
    c.line([(cx-shoulder*.8,torso_y+15*sy),(cx-118*scale,hand_y_l)], (*C(mid,.62),255), 27*scale)
    c.line([(cx+shoulder*.8,torso_y+15*sy),(cx+120*scale,hand_y_r)], (*C(mid,.62),255), 27*scale)
    c.ellipse((cx-130*scale,hand_y_l-12*scale,cx-108*scale,hand_y_l+15*scale), (*skin,255))
    c.ellipse((cx+108*scale,hand_y_r-12*scale,cx+130*scale,hand_y_r+15*scale), (*skin,255))
    # Neck and face
    c.rectangle((cx-18*scale,head_y+42*scale,cx+18*scale,head_y+78*scale), (*shadow,255), radius=8)
    c.image.alpha_composite(paint_face_layer(cx,head_y,scale,skin,light,shadow)); c.d=ImageDraw.Draw(c.image,"RGBA")
    # Hair volume and face detail
    c.ellipse((cx-45*scale,head_y-61*scale,cx+45*scale,head_y+5*scale), (*hair,250))
    c.ellipse((cx-39*scale,head_y-48*scale,cx+39*scale,head_y+56*scale), (*skin,235))
    if elder:
        c.polygon([(cx-28*scale,head_y+28*scale),(cx,head_y+90*scale),(cx+30*scale,head_y+28*scale)], (*C(hair,1.25),225))
    eye_y=head_y-4*scale
    c.line([(cx-22*scale,eye_y),(cx-9*scale,eye_y-2)], (34,27,25,255), 3*scale)
    c.line([(cx+9*scale,eye_y-2),(cx+22*scale,eye_y)], (34,27,25,255), 3*scale)
    c.line([(cx,eye_y+4),(cx-3*scale,head_y+18*scale),(cx+4*scale,head_y+20*scale)], (*shadow,180), 2*scale)
    c.line([(cx-12*scale,head_y+34*scale),(cx+13*scale,head_y+33*scale)], (92,48,48,210), 2.5*scale)
    # Hair strands and rim light
    for off in range(-36,37,9): c.line([(cx+off*scale,head_y-42*scale),(cx+off*.8*scale,head_y+38*scale)], (*C(hair,.62),130), 2*scale)
    c.line([(cx-38*scale,head_y-38*scale),(cx-42*scale,head_y+20*scale)], (*accent,150), 3*scale)
    if crown:
        c.polygon([(cx-46*scale,head_y-60*scale),(cx-36*scale,head_y-105*scale),(cx-10*scale,head_y-76*scale),(cx,head_y-112*scale),(cx+14*scale,head_y-76*scale),(cx+40*scale,head_y-106*scale),(cx+46*scale,head_y-60*scale)], (*C(accent,.7),230), (*accent,255), 3)
    if wings:
        for side in (-1,1):
            pts=[(cx+side*55*scale,torso_y+20*sy),(cx+side*190*scale,torso_y-100*sy),(cx+side*155*scale,hip_y),(cx+side*70*scale,hip_y-30*sy)]
            c.polygon(pts,(220,225,210,135),(*accent,180),3)
            for k in range(5): c.line([(cx+side*(75+k*18)*scale,torso_y),(cx+side*(130+k*10)*scale,hip_y-20*sy)],(245,240,215,100),3)


def glow_disc(c, x,y,r,color, rays=False):
    layer=Image.new("RGBA",SIZE,(0,0,0,0)); d=ImageDraw.Draw(layer,"RGBA")
    for rr in range(int(r*2),0,-5):
        alpha=int(2+30*(1-rr/(r*2)))
        d.ellipse(tuple(int(v*S) for v in (x-rr,y-rr,x+rr,y+rr)),fill=(*color,alpha))
    layer=layer.filter(ImageFilter.GaussianBlur(12*S)); c.image.alpha_composite(layer); c.d=ImageDraw.Draw(c.image,"RGBA")
    c.ellipse((x-r,y-r,x+r,y+r),(*color,170),(*C(color,1.12),230),4)
    if rays:
        for i in range(16):
            a=i*math.pi/8; c.line([(x+math.cos(a)*(r+8),y+math.sin(a)*(r+8)),(x+math.cos(a)*(r+36),y+math.sin(a)*(r+36))],(*color,180),3)


def emblem(c,suit,x,y,scale,palette):
    _,mid,accent,secondary=palette
    if suit=="wands":
        c.line([(x-9*scale,y+56*scale),(x+13*scale,y-58*scale)],(93,55,31,255),9*scale)
        c.line([(x+6*scale,y-35*scale),(x+33*scale,y-53*scale)],(*secondary,230),5*scale)
    elif suit=="cups":
        c.polygon([(x-35*scale,y-46*scale),(x+35*scale,y-46*scale),(x+25*scale,y+4*scale),(x,y+28*scale),(x-25*scale,y+4*scale)],(*C(mid,.9),220),(*accent,255),4)
        c.line([(x,y+28*scale),(x,y+58*scale),(x-24*scale,y+58*scale),(x+24*scale,y+58*scale)],(*accent,230),5*scale)
    elif suit=="swords":
        c.polygon([(x,y-72*scale),(x-9*scale,y-50*scale),(x-6*scale,y+48*scale),(x+6*scale,y+48*scale),(x+9*scale,y-50*scale)],(190,205,220,245),(*C(mid,.5),255),3)
        c.line([(x-30*scale,y+25*scale),(x+30*scale,y+25*scale)],(*accent,240),6*scale)
    else:
        pts=[]
        for i in range(10):
            a=-math.pi/2+i*math.pi/5; rr=(32 if i%2==0 else 14)*scale; pts.append((x+math.cos(a)*rr,y+math.sin(a)*rr))
        c.ellipse((x-48*scale,y-48*scale,x+48*scale,y+48*scale),(*C(accent,.75),230),(*accent,255),5)
        c.polygon(pts,(30,50,32,120),(*C(accent,1.1),255),3)


def major_scene(c,card,rng):
    slug=card["slug"]; _,_,accent,secondary=WORLDS["major"]
    info=MAJOR[slug]
    # Unique celestial/environment anchors
    if slug in {"sun","fool","strength","lovers"}: glow_disc(c,540 if slug=="fool" else 360,220,70,accent,True)
    if slug in {"moon","high-priestess"}: glow_disc(c,360,205,72,(180,200,235),False)
    if slug in {"star","hermit"}:
        for i in range(8):
            a=i*math.pi/4; glow_disc(c,360+math.cos(a)*150,260+math.sin(a)*90,12,accent)
    if slug=="tower":
        c.polygon([(220,850),(245,300),(475,300),(510,850)],(52,48,58,255),(180,150,120,220),7)
        c.line([(120,160),(360,360),(300,510),(590,270)],(255,228,130,255),16)
        draw_figure(c,rng,190,870,.55,armor=False,pose=2); draw_figure(c,rng,545,880,.5,armor=False,pose=-2)
        return
    if slug=="wheel-of-fortune":
        glow_disc(c,360,500,220,accent)
        c.ellipse((155,295,565,705),(20,20,35,100),(*accent,255),12)
        c.ellipse((270,410,450,590),(20,20,35,150),(*secondary,255),8)
        for i in range(8):
            a=i*math.pi/4;c.line([(360,500),(360+math.cos(a)*205,500+math.sin(a)*205)],(*accent,220),7)
        draw_figure(c,rng,360,900,.52,armor=False,cloak=True,pose=0);return
    if slug=="justice":
        draw_figure(c,rng,360,880,.92,armor=True,cloak=True,crown=True,pose=0)
        c.line([(505,410),(505,760)],(210,215,225,255),10); c.line([(460,500),(550,500)],(*accent,255),7)
        c.line([(475,500),(445,640),(515,640),(490,500)],(*accent,220),4); c.line([(535,500),(505,640),(575,640),(550,500)],(*accent,220),4);return
    if slug=="hanged-man":
        c.line([(115,230),(605,230)],(87,62,42,255),20);c.line([(180,230),(180,900)],(87,62,42,255),16);c.line([(540,230),(540,900)],(87,62,42,255),16)
        draw_figure(c,rng,360,840,.88,armor=False,cloak=True,inverted=True,pose=1);return
    if slug=="death":
        # Horse and rider silhouette
        c.ellipse((150,610,500,860),(218,216,199,220),(45,40,38,255),7);c.polygon([(430,650),(575,570),(620,640),(540,720)],(218,216,199,230),(45,40,38,255),6)
        for x in (210,310,420,500):c.line([(x,805),(x-15,930)],(45,40,38,255),22)
        draw_figure(c,rng,340,700,.68,armor=True,cloak=True,crown=False,pose=2);c.line([(455,500),(560,230)],(45,40,38,255),12);return
    if slug=="devil":
        draw_figure(c,rng,360,885,1.0,armor=True,cloak=True,crown=False,wings=True,pose=2)
        c.line([(320,335),(260,230),(330,280)],(65,43,40,255),18);c.line([(400,335),(460,230),(390,280)],(65,43,40,255),18)
        for side in (-1,1):c.line([(360+side*100,650),(360+side*210,840)],(145,115,82,220),8);return
    if slug=="lovers":
        draw_figure(c,rng,260,880,.76,armor=False,cloak=True,pose=1);draw_figure(c,rng,460,880,.76,armor=False,cloak=True,pose=-1)
        draw_figure(c,rng,360,465,.42,armor=False,cloak=False,wings=True,pose=0);return
    if slug=="strength":
        c.ellipse((95,645,330,865),(172,103,48,235),(59,41,29,255),7);c.ellipse((85,570,240,725),(179,116,57,245),(59,41,29,255),6)
        c.ellipse((120,615,145,638),(20,15,12,255));draw_figure(c,rng,425,885,.82,armor=False,cloak=True,pose=-1);return
    if slug=="chariot":
        c.polygon([(170,650),(550,650),(510,890),(210,890)],(54,67,91,245),(*accent,255),8)
        for x in (235,485):c.ellipse((x-50,825,x+50,925),(35,37,48,255),(*accent,220),8)
        draw_figure(c,rng,360,700,.7,armor=True,cloak=True,crown=True,pose=2);return
    if slug=="temperance":
        draw_figure(c,rng,360,875,.9,armor=False,cloak=True,wings=True,pose=0)
        emblem(c,"cups",225,620,.85,WORLDS["cups"]);emblem(c,"cups",500,700,.85,WORLDS["cups"]);c.line([(250,620),(475,690)],(120,210,230,180),9);return
    if slug=="judgement":
        draw_figure(c,rng,360,520,.6,armor=False,cloak=False,wings=True,pose=2)
        for x in (150,260,460,570):draw_figure(c,rng,x,930,.42,armor=False,cloak=False,pose=2);return
    if slug=="world":
        c.ellipse((110,155,610,900),(30,80,55,40),(90,150,95,240),18)
        draw_figure(c,rng,360,850,.82,armor=False,cloak=True,crown=True,pose=2)
        for x,y in ((125,180),(595,180),(125,840),(595,840)):glow_disc(c,x,y,26,accent);return
    # General iconic staging
    crown=slug in {"empress","emperor","hierophant"}; elder=slug in {"hermit","hierophant"}; wings=False
    armor=slug in {"emperor","chariot","magician"}; cloak=True
    draw_figure(c,rng,360,880,.9,armor,cloak,crown,wings,False,False,elder,(hash(slug)%5)-2)
    if slug=="magician":
        c.rectangle((120,700,600,790),(58,35,49,230),(*accent,220),5,12)
        for i,suit in enumerate(("wands","cups","swords","pentacles")):emblem(c,suit,190+i*115,720,.42,WORLDS.get(suit))
    elif slug=="high-priestess":
        c.rectangle((90,240,180,870),(20,25,45,220),(215,220,230,180),6);c.rectangle((540,240,630,870),(225,215,190,180),(50,45,40,220),6)
    elif slug=="empress":
        for x in range(90,680,65):c.line([(x,880),(x+rng.randint(-20,20),760)],(80,130,60,180),7)
    elif slug=="emperor":
        c.polygon([(80,880),(210,590),(330,880)],(52,45,48,230));c.polygon([(390,880),(530,550),(680,880)],(52,45,48,230))
    elif slug=="hierophant":
        draw_figure(c,rng,190,930,.45,False,True,False,False,False,True,False,0);draw_figure(c,rng,530,930,.45,False,True,False,False,False,True,False,0)
    elif slug=="hermit":
        glow_disc(c,520,520,38,accent);c.line([(520,560),(530,850)],(95,66,40,255),9)
    elif slug=="star":
        c.polygon([(80,880),(220,760),(360,850),(510,735),(680,880)],(15,55,75,210));emblem(c,"cups",200,690,.7,WORLDS["cups"])
    elif slug=="moon":
        c.rectangle((90,410,180,850),(45,48,70,230),(160,170,195,180),5);c.rectangle((540,410,630,850),(45,48,70,230),(160,170,195,180),5)
        for x in (215,505):c.ellipse((x-55,760,x+55,850),(75,70,65,230),(180,185,190,160),4)
    elif slug=="sun":
        for x in range(100,660,55):c.ellipse((x-22,820,x+22,865),(210,145,48,230),(240,190,70,230),3)


def minor_narrative(c,card,rng):
    suit,rank=card["suit"],card["rank"]; palette=WORLDS[suit]; count=RANK_VALUE.get(rank)
    # Court portraits
    if rank in {"page","knight","queen","king"}:
        scale={"page":.72,"knight":.9,"queen":.92,"king":.96}[rank]
        draw_figure(c,rng,350,890,scale,armor=rank in {"knight","king"},cloak=True,crown=rank in {"queen","king"},youthful=rank=="page",pose={"page":0,"knight":2,"queen":-1,"king":1}[rank])
        emblem(c,suit,555,560,1.1,palette)
        if rank=="knight":c.line([(520,600),(640,350)],(*palette[2],220),8)
        return
    n=count or 1
    # Narrative figure count / stance derived from classic meanings
    fig_counts={1:1,2:2,3:3,4:1,5:3,6:2,7:1,8:1,9:1,10:2}
    fc=fig_counts[n]
    if suit=="swords" and n==10: fc=1
    if suit=="cups" and n==10: fc=3
    for i in range(fc):
        x=360+(i-(fc-1)/2)*(145 if fc>1 else 0)
        sc=.72 if fc==1 else .48 if fc==3 else .58
        pose=((i+n)%5)-2
        draw_figure(c,rng,x,900,sc,armor=suit=="swords",cloak=True,pose=pose)
    # Card-specific environmental storytelling
    if n==2: c.line([(360,520),(360,830)],(*palette[2],130),3)
    if n==3 and suit=="swords": c.polygon([(300,520),(360,590),(420,520),(360,690)],(125,35,48,170));
    if n==4: c.rectangle((220,780,500,900),(25,30,35,130),(*palette[2],100),4,12)
    if n==5: c.line([(110,870),(610,720)],(*palette[3],120),6)
    if n==6 and suit=="swords": c.polygon([(110,820),(600,820),(530,900),(180,900)],(45,68,75,220),(*palette[2],170),5)
    if n==7: c.polygon([(80,900),(260,710),(360,900)],(*palette[1],120));
    if n==8 and suit=="pentacles": c.rectangle((100,740,250,890),(55,42,30,220),(*palette[2],180),5)
    if n==9 and suit=="swords":
        for y in range(250,660,45):c.line([(90,y),(630,y)],(*palette[2],120),4)
    if n==10 and suit=="wands": c.line([(190,480),(500,850)],(95,55,30,220),14)
    # Emblems form a framing constellation, not a flat pip grid
    positions=[]
    for i in range(n):
        a=-math.pi/2+2*math.pi*i/max(n,1)
        rx=245 if n>4 else 190; ry=285 if n>4 else 240
        positions.append((360+math.cos(a)*rx,505+math.sin(a)*ry))
    for x,y in positions:emblem(c,suit,x,y,.52 if n>6 else .65,palette)


def ornate_frame(c,card,rng):
    key=card.get("suit") or "major"; _,mid,accent,_=WORLDS[key]
    c.rectangle((18,18,702,1102),None,(*C(accent,.55),255),10,30)
    c.rectangle((32,32,688,1088),None,(*C(accent,1.1),210),3,24)
    c.rectangle((48,48,672,1072),None,(*C(mid,.55),240),4,18)
    for x,y,sx,sy in ((65,65,1,1),(655,65,-1,1),(65,1055,1,-1),(655,1055,-1,-1)):
        pts=[(x,y),(x+sx*48,y),(x+sx*72,y+sy*24),(x+sx*48,y+sy*48),(x,y+sy*48),(x+sx*18,y+sy*24)]
        c.polygon(pts,(*C(accent,.75),170),(*accent,235),2)
    # Painterly edge wear
    for _ in range(80):
        side=rng.choice([0,1,2,3]); t=rng.random()
        if side==0:x,y=30+t*660,30+rng.randint(-4,8)
        elif side==1:x,y=690+rng.randint(-8,4),30+t*1060
        elif side==2:x,y=30+t*660,1090+rng.randint(-8,4)
        else:x,y=30+rng.randint(-4,8),30+t*1060
        c.ellipse((x-1,y-1,x+1,y+1),(240,215,160,rng.randint(40,130)))


def title_plate(c,card):
    key=card.get("suit") or "major"; _,_,accent,_=WORLDS[key]
    c.rectangle((70,944,650,1062),(8,12,20,225),(*C(accent,1.05),235),4,16)
    font=ImageFont.truetype(FONT_BOLD,30*S); small=ImageFont.truetype(FONT_REG,15*S)
    c.text((360,986),card["name"].upper(),font,(244,235,215,255),"mm",1,(0,0,0,180))
    subtitle=(card.get("rank") or "MAJOR ARCANA").replace("-"," ").upper()
    if card.get("suit"):subtitle += f" · {card['suit'].upper()}"
    c.text((360,1028),subtitle,small,(*accent,255),"mm")
    sym=ImageFont.truetype(FONT_REG,27*S);c.text((360,78),str(card["symbol"]),sym,(245,228,186,245),"mm",1,(0,0,0,200))


def finish(image,card,rng):
    # Oil-glaze texture and vignette
    arr=np.array(image.convert("RGB"),dtype=np.float32); h,w=arr.shape[:2]; yy,xx=np.mgrid[0:h,0:w]
    dist=((xx-w/2)/(w*.75))**2+((yy-h/2)/(h*.72))**2
    vig=np.clip(1-dist*.28,.65,1)[...,None];arr*=vig
    grain=np.random.default_rng(seed(card["id"])+77).normal(0,3.5,(h,w,1));arr+=grain
    out=Image.fromarray(np.uint8(np.clip(arr,0,255)),"RGB")
    out=out.filter(ImageFilter.GaussianBlur(.22*S));out=ImageEnhance.Sharpness(out).enhance(1.65)
    out=out.resize((W,H),Image.Resampling.LANCZOS)
    return ImageEnhance.Contrast(out).enhance(1.06)


def render(card):
    rng=random.Random(seed(card["id"])); base=gradient_world(card,rng).convert("RGBA");c=Canvas(base)
    atmospheric_background(c,card,rng);c.d=ImageDraw.Draw(c.image,"RGBA")
    if card["arcana"]=="major":major_scene(c,card,rng)
    else:minor_narrative(c,card,rng)
    ornate_frame(c,card,rng);title_plate(c,card)
    return finish(c.image,card,rng)


def main():
    hashes=set()
    for i,card in enumerate(DEFAULT_CARDS,1):
        image=render(card);path=OUT/f"{card['slug']}.webp"
        image.save(path,"WEBP",quality=94,method=6)
        data=path.read_bytes();hashes.add(__import__('hashlib').sha256(data).hexdigest())
        print(f"[{i:02}/78] {path.name} {len(data):,} bytes")
    if len(hashes)!=78:raise RuntimeError("Artwork collision")
    print(f"generated {len(hashes)} unique fantasy-realistic Tarot paintings")

if __name__=="__main__":main()
