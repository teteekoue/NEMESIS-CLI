# -*- mode: python ; coding: utf-8 -*-
block_cipher = None
import sys
from pathlib import Path

datas = [('prompts', 'prompts')]
hiddenimports = ['httpx', 'h11', 'anyio', 'rich', 'prompt_toolkit', 'pydantic', 'pydantic_core', 'yaml', 'pyperclip', 'certifi', 'idna', 'sniffio']

a = Analysis(['nemesis.py'], pathex=[str(Path(__file__).parent)], binaries=[], datas=datas,
    hiddenimports=hiddenimports, excludes=['matplotlib', 'numpy', 'pandas', 'PIL', 'tkinter', 'unittest'],
    noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='nemesis', debug=False, strip=False, upx=True, console=True)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name='nemesis')
