# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for OBus MOA EXE"""
from pathlib import Path

PROJECT_ROOT = r"C:\Users\Hermes\Documents\obus-moa-exe"
BACKEND_DIR = Path(PROJECT_ROOT) / "backend"

# Hidden imports for FastAPI stack
hiddenimports = [
    "fastapi", "uvicorn", "uvicorn.main", "starlette",
    "jinja2", "jinja2.environment", "jinja2.loaders", "jinja2.exceptions",
    "markupsafe", "itsdangerous", "click", "h11", "httpcore", "anyio",
    "sniffio", "json", "dataclasses", "datetime", "typing",
    "backend.main", "backend.credit_manager", "backend",
]

datas = []

# Include static files beside the bundled backend module.
static_dir = BACKEND_DIR / "static"
if static_dir.exists():
    for f in static_dir.rglob("*"):
        if f.is_file():
            rp = f.relative_to(static_dir)
            destination = Path("backend/static") / rp.parent
            datas.append((str(f), str(destination)))

# Include backend Python files
for py_file in BACKEND_DIR.rglob("*.py"):
    rp = py_file.relative_to(PROJECT_ROOT)
    datas.append((str(py_file), str(rp.parent)))

# Include root Python files (launcher)
for py_file in Path(PROJECT_ROOT).glob("*.py"):
    if py_file.name not in ["OBus.spec", "pyinstaller.spec"]:
        datas.append((str(py_file), "."))

# Check for emblem/ICO
ico_path = Path(PROJECT_ROOT) / "assets" / "obus_emblem.ico"
icon_arg = str(ico_path) if ico_path.exists() else None

# Analysis - using launcher as entry point
a = Analysis(
    [str(Path(PROJECT_ROOT) / "obus_launcher.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Keep standard-library networking dependencies used by urllib/uvicorn.
    excludes=["tkinter"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Single-file EXE configuration
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="OBus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=icon_arg,
)