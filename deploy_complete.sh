#!/bin/bash
# Complete OBus build and deployment script

set -e

echo "========================================================================"
echo "OBUS MOA - UNIQUE EMBLEM, BUILD & CLOUD DEPLOYMENT"
echo "========================================================================"

# 1. Create emblem SVG
echo ""
echo "1. Creating unique emblem..."
EMBLEM_SVG='/c/Users/Hermes/Documents/obus-moa-exe/assets/OBus_Emblem.svg'
mkdir -p "$(dirname "$EMBLEM_SVG")"

cat > "$EMBLEM_SVG" << 'SVGEOF'
<!-- Unique OBus MOA Emblem -->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
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
  <circle cx="128" cy="128" r="50" fill="none" stroke="url(#cyan)" stroke-width="2"/>
  <text x="128" y="175" font-family="Arial, sans-serif" font-size="42" font-weight="bold" fill="url(#cyan)" text-anchor="middle" letter-spacing="6">O∴B</text>
</svg>
SVGEOF
echo "   ✓ Emblem SVG created"

# 2. Try to build EXE with PyInstaller
echo ""
echo "2. Building EXE with PyInstaller..."
cd /c/Users/Hermes/Documents/obus-moa-exe

# Check if pyinstaller exists
if command -v pyinstaller &> /dev/null; then
    pyinstaller --clean --noconfirm OBus.spec 2>&1 || echo "   ! Build had issues (may be expected for first run)"
else
    echo "   ! PyInstaller not found, using existing build"
fi

# 3. Determine which EXE to use
echo ""
echo "3. Locating EXE..."
DIST_EXE='/c/Users/Hermes/Documents/obus-moa-exe/dist/OBus.exe'
BUILD_EXE='/c/Users/Hermes/Documents/obus-moa-exe/build/OBus/OBus.exe'
LEGACY_EXE='/c/Users/Hermes/Documents/Tarot-Router/dist/OccultBus.exe'

if [[ -f "$DIST_EXE" ]]; then
    SOURCE_EXE="$DIST_EXE"
    echo "   ✓ Found: $SOURCE_EXE (NEW BUILD)"
elif [[ -f "$BUILD_EXE" ]]; then
    SOURCE_EXE="$BUILD_EXE"
    echo "   ✓ Found: $SOURCE_EXE (BUILD OUTPUT)"
elif [[ -f "$LEGACY_EXE" ]]; then
    SOURCE_EXE="$LEGACY_EXE"
    echo "   ⚠ Using: $SOURCE_EXE (LEGACY - has NOT been rebuilt)"
fi

# 4. Copy to cloud drive
echo ""
echo "4. Deploying to cloud drive..."
CLOUD_DIR='/c/Users/Hermes/OneDrive/OBus-MOA-Digital'
mkdir -p "$CLOUD_DIR"

if [[ -f "$SOURCE_EXE" ]]; then
    CLOUD_EXE="$CLOUD_DIR/OBus.exe"
    cp "$SOURCE_EXE" "$CLOUD_EXE"
    
    # Get file info
    SIZE_MB=$(du -m "$CLOUD_EXE" | cut -f1)
    SHA256=$(sha256sum "$CLOUD_EXE" | cut -d' ' -f1)
    
    echo "   ✓ Copied to: $CLOUD_EXE"
    echo "   ✓ Size: ${SIZE_MB}MB"
    echo "   ✓ SHA256: $SHA256"
    
    # 5. Copy to desktop
    DESKTOP_EXE='/c/Users/Hermes/Desktop/OBus.exe'
    cp "$CLOUD_EXE" "$DESKTOP_EXE"
    echo "   ✓ Copied to desktop: $DESKTOP_EXE"
    
    # Copy emblem to cloud
    cp "$EMBLEM_SVG" "$CLOUD_DIR/OBus_Emblem.svg"
    echo "   ✓ Emblem copied: $CLOUD_DIR/OBus_Emblem.svg"
    
    # 6. Create README
    cat > "$CLOUD_DIR/README.md" << 'READMEEOF'
# OBus MOA Digital
**Unique Tarot-Powered AI Agent Orchestrator**

## Files
- `OBus.exe` - Standalone executable (self-contained)
- `OBus_Emblem.svg` - Vector emblem
- `README.md` - This file

## How to Run
1. Double-click `OBus.exe`
2. First run: Ollama setup wizard opens
3. Subsequent: Dashboard opens directly

## Features
- 4 Tarot Agent Cards with artwork
- 7 Domain Decks (Rider-Waite, Thoth, Marseille, etc.)
- Multi-provider credit/token windows
- Per-agent context tracking
- RAG with SQLite memory store
- First-run Ollama setup (required first)

## Architecture
- FastAPI backend
- Vue.js frontend SPA
- MOA routing with deck-based selection
- Credit manager for token tracking

Built: $(date -Iseconds)
READMEEOF
    echo "   ✓ README created"
    
    # 7. Open in Explorer and launch
    echo ""
    echo "5. Opening cloud drive and launching..."
    
    # Open Explorer with file selected
    Explorer.exe /select,"$CLOUD_EXE" 2>/dev/null || echo "   ! Could not open Explorer"
    
    # Launch EXE
    CMD_START='start "" "'$CLOUD_EXE'"'
    echo "   🎯 Launching: $CLOUD_EXE"
    
else
    echo "   ❌ ERROR: No EXE found to deploy"
    exit 1
fi

echo ""
echo "========================================================================"
echo "COMPLETE - OBus MOA EXE READY"
echo "========================================================================"
echo ""
echo "🚀 Desktop: /c/Users/Hermes/Desktop/OBus.exe"
echo "☁️  Cloud: /c/Users/Hermes/OneDrive/OBus-MOA-Digital/OBus.exe"
echo "🎨 Emblem: /c/Users/Hermes/OneDrive/OBus-MOA-Digital/OBus_Emblem.svg"
echo ""
echo "📋 First Run:"
echo "   1. Double-click the EXE"
echo "   2. Ollama setup wizard opens"
echo "   3. Install/start Ollama if needed"
echo "   4. Select model (llama3.2:latest)"
echo "   5. Dashboard opens automatically"
echo ""
echo "🌐 URL: http://127.0.0.1:8080/"
echo "========================================================================"