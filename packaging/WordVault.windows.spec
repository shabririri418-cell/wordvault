# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH).parent
analysis = Analysis(
    [str(project_root / "src" / "wordvault" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        str(project_root / "packaging" / "runtime_hooks" / "windows_qt_software.py")
    ],
    excludes=[],
    noarchive=False,
    optimize=0,
)

forbidden_names = {"ucrtbase.dll"}
analysis.binaries = type(analysis.binaries)(
    entry
    for entry in analysis.binaries
    if entry[0].lower() not in forbidden_names
    and "native\\libheif" not in entry[1].lower()
)

pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="_WordVaultCore",
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
)

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="文澜资料库-Windows预览版",
)
