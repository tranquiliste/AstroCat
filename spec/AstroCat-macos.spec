# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None
project_root = Path.cwd()

a = Analysis(
    [str(project_root / "app" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "data"), "data"),
        (str(project_root / "assets" / "images"), "assets/images"),
        (str(project_root / "app" / "locales"), "app/locales"),
        (str(project_root / "app" / "database_schema.sql"), "."),
        (str(project_root / "scripts" / "migrate_user_notes.py"), "scripts"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AstroCat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(project_root / "build_assets" / "Astrocat_icon.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AstroCat",
)

app = BUNDLE(
    coll,
    name="AstroCat.app",
    icon=str(project_root / "build_assets" / "Astrocat_icon.icns"),
    bundle_identifier=None,
)
