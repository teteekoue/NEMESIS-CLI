# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['../../nemesis.py'],
    pathex=[],
    binaries=[],
    datas=[('prompts', 'prompts'), ('src', 'src')],
    hiddenimports=['httpx', 'httpx._transports.default', 'httpcore', 'h11', 'anyio', 'rich', 'rich.console', 'rich.markdown', 'rich.panel', 'prompt_toolkit', 'pydantic', 'yaml', 'textual', 'textual.app', 'textual.widgets', 'src.config', 'src.providers', 'src.tools', 'src.agent', 'src.mcp', 'src.ui', 'src.commands', 'src.tui'],
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
