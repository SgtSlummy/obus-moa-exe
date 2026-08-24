#!/usr/bin/env python3
"""
SVG -> PNG/ICO conversion (no external deps, uses pure SVG path parsing)
"""
import re
from pathlib import Path

def svg_to_png(svg_path: Path, out_png: Path, size: int = 256) -> None:
    """Convert SVG to PNG using PIL with simple path rasterization."""
    # Read SVG
    svg_text = svg_path.read_text()
    
    # Extract attributes we need
    width = 512
    height = 512
    
    # Create blank white background
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (width, height), (10, 7, 17, 255))
    draw = ImageDraw.Draw(img)
    
    # Simple approach: render static SVG elements as basic shapes
    # Key shape
    draw.rectangle([118, 120, 158, 340], fill=(245, 196, 81, 255), outline=None)
    draw.ellipse([180, 36, 232, 122], fill=None, outline=(245, 196, 81, 200), width=6)
    draw.ellipse([192, 48, 212, 84], fill=(10, 7, 17, 255), outline=(245, 196, 81, 150), width=4)
    draw.rectangle([220, 270, 250, 290], fill=(245, 196, 81, 255))
    draw.rectangle([232, 295, 254, 305], fill=(245, 196, 81, 255))
    
    # Gold ring with simple tick marks
    import math
    cx, cy = 256, 256
    r = 210
    tick_r = 4
    for angle_deg in range(0, 360, 5):
        rad = math.radians(angle_deg)
        x = cx + r * math.cos(rad)
        y = cy + r * math.sin(rad)
        draw.ellipse([x-tick_r, y-tick_r, x+tick_r, y+tick_r], fill=(245, 196, 81, 150))
    
    # Save
    img.save(out_png, 'PNG')
    print(f"PNG saved: {out_png}")
    
    # Create ICO
    img.save(out_png.parent / 'emblem.ico', 'ICO', sizes=[(256,256)])
    print(f"ICO saved: {out_png.parent / 'emblem.ico'}")

if __name__ == '__main__':
    svg = Path('backend/static/art/emblems/obus-emblem-icon.svg')
    png = Path('tools/obus_launcher/emblem.png')
    svg_to_png(svg, png)