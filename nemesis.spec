# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['nemesis.py'],
    pathex=[],
    binaries=[],
    datas=[('/workspace/prompts', 'prompts'), ('/workspace/start', 'start')],
    hiddenimports=['src.config', 'src.providers', 'src.tools', 'src.agent', 'src.mcp', 'src.prompts'],
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
    name='nemesis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
