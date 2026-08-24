"""Render the selected Magician's Key emblem into a multi-size Windows ICO."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

CANVAS = 512
GOLD = (245, 196, 81, 255)
GOLD_DARK = (212, 175, 55, 255)
NAVY = (5, 7, 17, 255)
BLUE = (26, 33, 72, 255)


def build_icon(destination: Path) -> None:
    image = Image.new("RGBA", (CANVAS, CANVAS), NAVY)
    draw = ImageDraw.Draw(image)
    draw.ellipse((24, 24, 488, 488), fill=BLUE, outline=GOLD, width=9)
    draw.ellipse((45, 45, 467, 467), outline=GOLD_DARK, width=4)

    # Solomonic ring: 72 markers at the cardinal circle.
    for degrees in range(0, 360, 5):
        import math
        angle = math.radians(degrees)
        x = 256 + 201 * math.cos(angle)
        y = 256 + 201 * math.sin(angle)
        draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=GOLD_DARK)

    # The Magician's Key: bow, shaft, teeth, and infinity sign.
    draw.ellipse((185, 62, 327, 204), outline=GOLD, width=16)
    draw.ellipse((234, 111, 278, 155), fill=NAVY, outline=GOLD_DARK, width=7)
    draw.rounded_rectangle((231, 184, 281, 381), radius=10, fill=GOLD)
    draw.rectangle((278, 316, 330, 344), fill=GOLD)
    draw.rectangle((278, 358, 314, 386), fill=GOLD_DARK)
    draw.arc((175, 190, 256, 260), start=195, end=525, fill=GOLD, width=10)
    draw.arc((256, 190, 337, 260), start=15, end=345, fill=GOLD, width=10)

    # Four elemental marks from the selected emblem, rendered without emoji fonts.
    draw.polygon(((147, 252), (162, 279), (132, 279)), fill=(255, 159, 67, 255))
    draw.ellipse((350, 246, 380, 286), fill=(60, 169, 239, 255))
    draw.arc((126, 325, 178, 367), start=200, end=340, fill=(78, 227, 160, 255), width=7)
    draw.polygon(((365, 330), (382, 361), (348, 361)), fill=(214, 155, 114, 255))

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    build_icon(Path(__file__).with_name("obus.ico"))
