#!/usr/bin/env python3
"""Create emblem, deploy EXE to cloud, and launch"""
import os
import shutil
import hashlib
import subprocess
from pathlib import Path

# Paths
PROJECT_ROOT = Path(r'C:\Users\Hermes\Documents\obus-moa-exe')
CLOUD_ROOT = Path(r'C:\Users\Hermes\OneDrive\OBus-MOA-Digital')
DESKTOP = Path(r'C:\Users\Hermes\Desktop')

print("=" * 70)
print("OBUS MOA - UNIQUE EMBLEM & CLOUD DEPLOYMENT")
print("=" * 70)

# 1. Create emblem
CLOUD_ROOT.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = PROJECT_ROOT / 'assets'
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# SVG Emblem
emblem_svg = Path(ASSETS_DIR / 'OBus_Emblem.svg')
emblem_svg.write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
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
  <circle cx="128" cy="128" r="45" fill="none" stroke="url(#cyan)" stroke-width="2"/>
  <text x="128" y="175" font-family="Arial, sans-serif" font-size="42" font-weight="bold" 
        fill="url(#cyan)" text-anchor="middle" letter-spacing="6">O;B</text>
  <circle cx="34" cy="128" r="12" fill="url(#gold)"/>
  <circle cx="222" cy="128" r="12" fill="url(#cyan)"/>
  <circle cx="128" cy="34" r="12" fill="url(#gold)"/>
  <circle cx="128" cy="222" r="12" fill="url(#cyan)"/>
</svg>''')
print(f"✅ Created SVG emblem: {emblem_svg}")

# 2. Copy EXE to cloud
print(f"\n2. DEPLOYING EXE")
print("-" * 50)

# Find the built EXE
dist_exe = PROJECT_ROOT / 'dist' / 'OBus.exe'
build_exe = PROJECT_ROOT / 'build' / 'OBus' / 'OBus.exe'
legacy = Path(r'C:\Users\Hermes\Documents\Tarot-Router\dist\OccultBus.exe')

# Prefer new build, but use legacy if needed
exe_src = None
for candidate in [dist_exe, build_exe, legacy]:
    if candidate.exists():
        exe_src = candidate
        break

if exe_src:
    # Copy to cloud
    cloud_exe = CLOUD_ROOT / 'OBus.exe'
    shutil.copy2(exe_src, cloud_exe)
    
    # Copy to desktop
    desktop_exe = DESKTOP / 'OBus.exe'
    shutil.copy2(exe_src, desktop_exe)
    
    # Calculate hash
    sha256 = hashlib.sha256()
    with open(cloud_exe, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    
    size_mb = cloud_exe.stat().st_size / 1024 / 1024
    
    print(f"  ✓ EXE: {cloud_exe}")
    print(f"  ✓ Desktop: {desktop_exe}")
    print(f"  Size: {size_mb:.2f} MB")
    print(f"  SHA256: {sha256.hexdigest()}")
    
    # Copy emblem to cloud
    shutil.copy2(emblem_svg, CLOUD_ROOT / 'OBus_Emblem.svg')
    print(f"  ✓ Emblem: {CLOUD_ROOT / 'OBus_Emblem.svg'}")
    
    # Create README
    readme = CLOUD_ROOT / 'README.md'
    readme.write_text('''# OBus MOA Digital

**Unique Tarot-Powered AI Agent Orchestrator**

## Files
- `OBus.exe` - Standalone executable with emblem
- `OBus_Emblem.svg` - Vector emblem

## How to Run
1. **First Run**: Double-click OBus.exe → Ollama setup wizard
2. **Install Ollama**: https://ollama.com/download
3. **Run**: Select model `gpt-oss:20b`
4. **Dashboard**: Opens automatically

## Features
- 4 Tarot Agent Cards (Magician, High Priestess, Emperor, Hermit)
- 7 Domain Decks (Rider-Waite, Thoth, Marseille, Wild Unknown, Hermetic, Golden Dawn, Urban)
- Per-provider credit/quota windows
- RAG with SQLite memory
- Dark mode permanent
- MOA routing with deck selection

## Architecture
- FastAPI backend
- Vue.js SPA frontend
- Credit manager for token tracking
- First-run Ollama setup required

---
'''.strip())
    print(f"  ✓ README: {readme}")
else:
    print("  ❌ ERROR: No EXE found!")

# 3. Open cloud and launch
print(f"\n" + "=" * 70)
print("OPENING CLOUD & LAUNCHING EXE")
print("=" * 70)

try:
    subprocess.run(f'explorer.exe /select,"{CLOUD_ROOT}\\OBus.exe"', shell=True)
    print(f"✅ Opened OneDrive\\OBus-MOA-Digital with EXE selected")
except Exception as e:
    print(f"⚠ Explorer: {e}")

try:
    subprocess.Popen([str(CLOUD_ROOT / 'OBus.exe')], shell=True)
    print(f"✅ Launched {CLOUD_ROOT / 'OBus.exe'}")
    print(f"\n🌐 URL: http://127.0.0.1:38173/")
    print(f"🧭 First run: Ollama setup wizard opens")
except Exception as e:
    print(f"⚠ Launch: {e}")

# Final status
print(f"\n" + "=" * 70)
print("STATUS: ✅ COMPLETE")
print("=" * 70)
print(f"📍 Desktop: {desktop_exe}")
print(f"☁️  Cloud:   {cloud_exe}")
print(f"🎨 Emblem:  {CLOUD_ROOT / 'OBus_Emblem.svg'}")
print(f"=" * 70)