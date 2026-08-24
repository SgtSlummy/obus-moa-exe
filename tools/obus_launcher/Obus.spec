# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/Hermes/Documents/obus-moa-exe/tools/obus_launcher/obus_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/Hermes/Documents/obus-moa-exe/backend/static', 'backend/static')],
    hiddenimports=['backend.main'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Obus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/Hermes/Documents/obus-moa-exe/tools/obus_launcher/obus.ico'],
)
