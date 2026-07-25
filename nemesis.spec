# -*- mode: python ; coding: utf-8 -*-
block_cipher = None
import sys
from pathlib import Path

PROJECT_DIR = Path(SPECPATH)

# Tout empaqueter: prompts, src, requirements
a = Analysis(
    ['nemesis.py'],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=[
        ('prompts', 'prompts'),
        ('src', 'src'),
    ],
    hiddenimports=[
        'httpx', 'httpx._transports', 'httpx._transports.default',
        'httpcore', 'httpcore._async', 'httpcore._sync',
        'h11', 'anyio', 'anyio._backends',
        'anyio._backends._asyncio',
        'rich', 'rich.console', 'rich.markdown', 'rich.panel',
        'rich.table', 'rich.text', 'rich.tree', 'rich.syntax',
        'rich.theme', 'rich.prompt',
        'prompt_toolkit', 'prompt_toolkit.completion',
        'prompt_toolkit.history', 'prompt_toolkit.auto_suggest',
        'prompt_toolkit.key_binding', 'prompt_toolkit.styles',
        'pydantic', 'pydantic_core',
        'yaml', 'pyperclip',
        'certifi', 'idna', 'sniffio',
        'fnmatch',
        'src', 'src.config', 'src.prompts',
        'src.providers', 'src.providers.base',
        'src.tools', 'src.tools.definitions', 'src.tools.executor',
        'src.agent', 'src.agent.core', 'src.agent.sub_agent', 'src.agent.modes',
        'src.mcp', 'src.mcp.client', 'src.mcp.manager',
        'src.ui', 'src.ui.theme', 'src.ui.logo', 'src.ui.renderer', 'src.ui.input_handler',
        'src.commands', 'src.commands.registry', 'src.commands.builtins',
    ],
    excludes=['matplotlib', 'numpy', 'pandas', 'PIL', 'tkinter', 'unittest', 'test'],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='nemesis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='nemesis',
)
