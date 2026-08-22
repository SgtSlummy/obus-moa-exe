# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for OBus - Fully contained MOA executable."""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Get project root
project_root = Path(__file__).parent.parent

# Python modules to bundle
hiddenimports = [
    'tarot_router',
    'tarot_moa', 
    'tarot_agents',
    'tarot_rag',
    'solomons_keys',
    'occultbus_api',
    'tarot_mcp',
    'fastapi',
    'uvicorn',
    'uvicorn.main',
    'uvicorn.protocols',
    'uvicorn._uvloop',
    'starlette',
    'jinja2',
    'markupsafe',
    'sqlite3',
    'aiofiles',
    'httptools',
    'uvloop',
    'watchfiles',
    ' sniffio',
    'anyio',
    'httpcore',
    'certifi',
    'charset_normalizer',
    'idna',
    'requests',
    'urllib3',
    'h11',
]

# Data files to include
datas = []

# Include core runtime modules
datas += collect_data_files('obus')

# Include configuration templates
config_dir = project_root / 'config'
if config_dir.exists():
    for f in config_dir.glob('*.json'):
        datas.append((str(f), f'config/{f.name}'))

# Include knowledge artifacts
knowledge_dir = project_root / 'knowledge'
if knowledge_dir.exists():
    for f in knowledge_dir.rglob('*'):
        if f.is_file() and not f.name.startswith('.'):
            datas.append((str(f), f'knowledge/{f.relative_to(knowledge_dir)}'))

# Include static frontend
static_dir = project_root / 'backend' / 'static'
if static_dir.exists():
    for f in static_dir.rglob('*'):
        if f.is_file():
            datas.append((str(f), f'static/{f.relative_to(static_dir)}'))

# Python binaries
binaries = []

# Analysis
a = Analysis(
    ['backend/main.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'email',
        'http',
        'urllib',
        'xml',
        'pydoc',
        'doctest',
        'argparse',
        'difflib',
        'inspect',
        'sqlite3',  # Include via hiddenimports instead
    ],
    noarchive=False,
    optimize=1,
)

# PYZ archive
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# EXE configuration
exe = EXE(
    pyz,
    a.binaries,
    a.datas,
    [],
    name='OBus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for development
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if available: 'assets/icon.ico'
)

# Collateral files (for --onedir mode fallback)
collateral = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OBus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console version for troubleshooting
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)