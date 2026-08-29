# -*- mode: python ; coding: utf-8 -*-
"""Complete, portable PyInstaller specification for the OBus desktop runtime."""
from importlib.util import find_spec
from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve()
BACKEND_DIR = PROJECT_ROOT / "backend"


def optional_module_available(module: str) -> bool:
    """Only request optional native integrations that this build interpreter has."""

    return find_spec(module) is not None


hiddenimports = [
    "fastapi", "uvicorn", "uvicorn.main", "starlette", "h11", "httpcore", "anyio", "sniffio",
    "pystray", "pystray._win32", "PIL.Image", "PIL.ImageDraw", "obus_mcp_server", "backend",
    "backend.main", "backend.aui", "backend.aui_events", "backend.user_settings", "backend.workspace_context",
    "backend.run_receipts", "backend.warp_companion", "backend.tentacle_worms", "backend.credit_manager",
    "backend.room_models", "backend.room_council", "backend.room_runner", "backend.forum_runtime",
]

# The corresponding features remain unavailable when their local optional package
# is not installed; packaging must not fail merely because one is absent.
OPTIONAL_HIDDEN_IMPORTS = ["faster_whisper", "ctranslate2", "sounddevice", "av", "winpty"]
hiddenimports.extend(module for module in OPTIONAL_HIDDEN_IMPORTS if optional_module_available(module))

datas = []
binaries = []

# Include every static asset beside the bundled backend module.
static_dir = BACKEND_DIR / "static"
if static_dir.exists():
    for file_path in static_dir.rglob("*"):
        if file_path.is_file():
            rp = file_path.relative_to(static_dir)
            destination = Path("backend/static") / rp.parent
            datas.append((str(file_path), str(destination)))

# Retain backend modules that the desktop service resolves dynamically.
for py_file in BACKEND_DIR.rglob("*.py"):
    rp = py_file.relative_to(PROJECT_ROOT)
    datas.append((str(py_file), str(rp.parent)))

assets_dir = PROJECT_ROOT / "assets"
if assets_dir.exists():
    for asset in assets_dir.rglob("*"):
        if asset.is_file():
            relative_asset = asset.relative_to(assets_dir)
            if ".cache" in relative_asset.parts:
                continue
            datas.append((str(asset), str(Path("assets") / relative_asset.parent)))

ico_path = assets_dir / "obus_emblem.ico"
icon_arg = str(ico_path) if ico_path.exists() else None

# pywinpty ships a companion executable; retain it for frozen local terminals.
winpty_dir = None
if optional_module_available("winpty"):
    import winpty
    winpty_dir = Path(winpty.__file__).resolve().parent
if winpty_dir is not None:
    winpty_agent = winpty_dir / "winpty-agent.exe"
    if winpty_agent.exists():
        binaries.append((str(winpty_agent), "winpty"))


a = Analysis(
    [str(PROJECT_ROOT / "obus_launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name="Obus", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True, upx_exclude=[],
    runtime_tmpdir=None, console=False, disable_windowed_traceback=False,
    argv_emulation=False, icon=icon_arg,
)
