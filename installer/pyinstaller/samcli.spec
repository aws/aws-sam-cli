# -*- mode: python -*-
import sys ; sys.setrecursionlimit(sys.getrecursionlimit() * 5)
block_cipher = None
exe_name = 'sam'
analysis = Analysis(
    ['../../samcli/__main__.py'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=['./installer/pyinstaller'],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher
)
pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=True,
    name='sam'
)