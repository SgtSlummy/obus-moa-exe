#!/usr/bin/env python3
"""Create emblem, deploy EXE to cloud, and launch"""
import os, shutil, subprocess, hashlib
from pathlib import Path

# Paths
PROJECT_ROOT = Path(r'C:\Users\Hermes\Documents\obus-moa-exe')
CLOUD_ROOT = Path(r'C:\Users\Hermes\OneDrive\OBus-MOA-Digital')
DESKTOP = Path(r'C:\Users\Hermes\Desktop')

# Ensure cloud directory exists
CLOUD_ROOT.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("OBUS MOA - EMBLEM, DEPLOY & LAUNCH")
print("=" * 70)

# 1. Create SVG emblem
print("\n1. CREATING UNIQUE EMBLEM")
print("-" * 50)

emblem_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <defs>
    <radialGradient id="bg" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#0a0033"/>
      <stop offset="100%" stop-color="#070418"/>
    </radialGradient>
    <linearGradient id="gold" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFD700"/>
      <stop offset="100%" stop-color="#FFC845"/>
    </linearGradient>
    <linearGradient id="cyan" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#00E5FF"/>
      <stop offset="100%" stop-color="#00B8D4"/>
    </linearGradient>
  </defs>
  <circle cx="128" cy="128" r="120" fill="url(#bg)"/>
  <circle cx="128" cy="128" r="115" fill="none" stroke="#151030" stroke-width="6"/>
  <polygon points="128,48 153,96 128,144 103,96" fill="url(#gold)" stroke="#FFD700" stroke-width="4"/>
  <polygon points="128,48 114,72 95,96 128,112 161,96 180,72" fill="none" stroke="url(#gold)" stroke-width="4"/>
  <text x="128" y="175" font-family="Arial" font-size="42" font-weight="bold" fill="url(#cyan)" text-anchor="middle" letter-spacing="6">OBUS</text>
  <circle cx="34" cy="128" r="12" fill="url(#gold)"/>
  <circle cx="222" cy="128" r="12" fill="url(#cyan)"/>
  <circle cx="128" cy="34" r="12" fill="url(#gold)"/>
  <circle cx="128" cy="222" r="12" fill="url(#cyan)"/>
</svg>'''

svg_path = CLOUD_ROOT / 'OBus_Emblem.svg'
with open(svg_path, 'w', encoding='utf-8') as f:
    f.write(emblem_svg)
print(f"  ✓ SVG emblem: {svg_path}")

# Try to create ICO with Pillow
try:
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (256, 256), (10, 0, 51, 255))
    d = ImageDraw.Draw(img)
    d.ellipse([8, 8, 248, 248], fill=(10, 0, 51, 255), outline=(198, 158, 58, 255), width=5)
    d.ellipse([30, 30, 226, 226], outline=(60, 44, 110, 255), width=3)
    cx, cy = 128, 128
    d.line([(cx, 100), (cx, 156)], fill=(0, 225, 255, 255), width=6)
    d.ellipse((108, 86, 148, 114), outline=(0, 225, 255, 255), width=4)
    d.rectangle((118, 154, 138, 166), fill=(0, 225, 255, 255))
    d.rectangle((134, 146, 154, 154), fill=(0, 225, 255, 255))
    for i in range(12):
        import math
        a = i * 2 * math.pi / 12
        x = cx + math.cos(a) * 103
        y = cy + math.sin(a) * 103
        d.ellipse((x-4, y-4, x+4, y+4), fill=(245, 197, 66, 255) if i % 2 == 0 else (0, 225, 255, 255))
    d.text((128, 180), "OBUS", fill=(255, 245, 210, 255), anchor="mm")
    ico_path = CLOUD_ROOT / 'OBus_Emblem.ico'
    img.save(ico_path, format='ICO')
    print(f"  ✓ ICO emblem: {ico_path}")
except ImportError:
    print("  ⚠ Pillow not available, SVG only")

# 2. Find and copy EXE
print(f"\n2. COPYING EXE TO CLOUD")
print("-" * 50)

dist_exe = PROJECT_ROOT / 'dist' / 'OBus.exe'
build_exe = PROJECT_ROOT / 'build' / 'OBus' / 'OBus.exe'
legacy = Path(r'C:\Users\Hermes\Documents\Tarot-Router\dist\OccultBus.exe')

exe_src = None
for c in [dist_exe, build_exe]:
    if c.exists():
        exe_src = c
        break
if not exe_src:
    exe_src = legacy

if exe_src:
    cloud_exe = CLOUD_ROOT / 'OBus.exe'
    desktop_exe = DESKTOP / 'OBus.exe'
    
    shutil.copy2(exe_src, cloud_exe)
    shutil.copy2(exe_src, desktop_exe)
    
    size_mb = cloud_exe.stat().st_size / 1024 / 1024
    sha256 = hashlib.sha256()
    with open(cloud_exe, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    
    print(f"  ✓ Cloud EXE: {cloud_exe}")
    print(f"  ✓ Desktop:   {desktop_exe}")
    print(f"  Size:        {size_mb:.2f} MB")
    print(f"  SHA256:      {sha256.hexdigest()[:32]}...")
else:
    print("  ❌ No EXE found!")
    cloud_exe = None

# 3. Open explorer and launch
print(f"\n" + "=" * 70)
print("OPENING CLOUD & LAUNCHING")
print("=" * 70)

if cloud_exe and cloud_exe.exists():
    # Open Explorer selecting file
    subprocess.run(f'explorer.exe /select,"{cloud_exe}"', shell=True)
    print(f"\n✅ Opened OneDrive\\OBus-MOA-Digital with EXE selected")
    
    # Launch EXE
    subprocess.Popen([str(cloud_exe)], shell=True)
    print(f"✅ Launched: {cloud_exe}")
    print(f"\n🌐 Dashboard: http://127.0.0.1:8080/")
    print(f"🧭 First run: Ollama setup wizard")

print(f"\n" + "=" * 70)
print("COMPLETE")
print("=" * 70)
if cloud_exe:
    print(f"☁️  Cloud:  {cloud_exe}")
    print(f"🏠 Desktop: {DESKTOP / 'OBus.exe'}")
    print(f"🎨 Emblem: {CLOUD_ROOT / 'OBus_Emblem.svg'}")
print("=" * 70)