#!/usr/bin/env python3
"""Script de build CI — appelé dans le Docker container."""
import subprocess, os, sys, shutil
from pathlib import Path

ROOT = Path(os.environ.get("NEMESIS_ROOT", "/src"))
VERSION = os.environ.get("NEMESIS_VERSION", "3.0.0")
DEB_ARCH = os.environ.get("DEB_ARCH", "amd64")
PYINST_ARCH = os.environ.get("PYINST_ARCH", "x86_64")
DIST = ROOT / f"dist_{DEB_ARCH}"
BUILD = ROOT / f"build_{DEB_ARCH}"

shutil.rmtree(BUILD, ignore_errors=True)
shutil.rmtree(DIST, ignore_errors=True)
DIST.mkdir(parents=True)
BUILD.mkdir(parents=True)

# --- Générer le spec onefile ---
spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
PROJ = Path("{ROOT}")

a = Analysis(
    [str(PROJ / "nemesis.py")],
    pathex=[str(PROJ)],
    binaries=[],
    datas=[(str(PROJ / "prompts"), "prompts"), (str(PROJ / "src"), "src")],
    hiddenimports=[
        "httpx","httpx._transports","httpx._transports.default",
        "httpcore","httpcore._async","httpcore._sync",
        "h11","anyio","anyio._backends","anyio._backends._asyncio",
        "rich","rich.console","rich.markdown","rich.panel",
        "rich.table","rich.text","rich.tree","rich.syntax",
        "rich.theme","rich.prompt",
        "prompt_toolkit","prompt_toolkit.completion",
        "prompt_toolkit.history","prompt_toolkit.auto_suggest",
        "prompt_toolkit.key_binding","prompt_toolkit.styles",
        "pydantic","pydantic_core","yaml","pyperclip",
        "certifi","idna","sniffio","fnmatch",
        "src","src.config","src.prompts",
        "src.providers","src.providers.base",
        "src.tools","src.tools.definitions","src.tools.executor",
        "src.agent","src.agent.core","src.agent.sub_agent","src.agent.modes",
        "src.mcp","src.mcp.client","src.mcp.manager",
        "src.ui","src.ui.theme","src.ui.logo","src.ui.renderer","src.ui.input_handler",
        "src.commands","src.commands.registry","src.commands.builtins",
    ],
    excludes=["matplotlib","numpy","pandas","PIL","tkinter","unittest","test"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

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
'''

spec_path = BUILD / "nemesis.spec"
spec_path.write_text(spec_content)

# --- PyInstaller onefile (spec configure le mode, pas besoin de --onefile) ---
print(f"=== PyInstaller onefile {DEB_ARCH} ({PYINST_ARCH}) ===")
cmd = [
    sys.executable, "-m", "PyInstaller", "--clean",
    f"--distpath={BUILD}/dist",
    f"--workpath={BUILD}/work",
    str(spec_path),
]

# Si target-arch est demandé, on le passe (ne marche qu'avec le bon Python)
if PYINST_ARCH and os.environ.get("SET_TARGET_ARCH") == "1":
    cmd.extend(["--target-arch", PYINST_ARCH])

result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr[-2000:])
    sys.exit(1)

# --- Vérifier le binaire ---
binary_src = BUILD / "dist" / "nemesis"
if not binary_src.exists():
    print(f"ERREUR: binaire non trouvé: {binary_src}")
    sys.exit(1)
print(f"Binaire: {binary_src.stat().st_size / (1024*1024):.1f} MB")

# --- Assembler le paquet .deb ---
PKG = BUILD / f"pkg/nemesis-cli_{VERSION}_{DEB_ARCH}"
if PKG.exists():
    shutil.rmtree(PKG)
PKG.mkdir(parents=True)
(PKG / "DEBIAN").mkdir(exist_ok=True)
(PKG / "usr/bin").mkdir(parents=True)

shutil.copy2(str(binary_src), str(PKG / "usr/bin" / "nemesis"))
os.chmod(str(PKG / "usr/bin" / "nemesis"), 0o755)

size_kb = sum(f.stat().st_size for f in PKG.rglob("*") if f.is_file()) // 1024
control = f"""Package: nemesis-cli
Version: {VERSION}
Section: utils
Priority: optional
Architecture: {DEB_ARCH}
Installed-Size: {size_kb}
Depends: libc6 (>= 2.31), libssl3, ca-certificates
Maintainer: teteekoue <teteekoue@users.noreply.github.com>
Description: NEMESIS-CLI - Agent de codage IA autonome
 NEMESIS est un agent de codage autonome multi-fournisseurs
 (Groq, NVIDIA NIM, OpenRouter, Fireworks, Cohere, API Bridge,
 Custom OpenAI) avec integration MCP, mode plan, mode dual-modele,
 sous-agents, et interface CLI moderne theme Dracula.
"""
(PKG / "DEBIAN" / "control").write_text(control)

(PKG / "DEBIAN" / "postinst").write_text(
    "#!/bin/bash\n"
    "mkdir -p /root/.nemesis 2>/dev/null || true\n"
    "mkdir -p \"$HOME/.nemesis\" 2>/dev/null || true\n"
)
os.chmod(str(PKG / "DEBIAN" / "postinst"), 0o755)

# --- dpkg-deb ---
DIST.mkdir(parents=True, exist_ok=True)
deb_path = DIST / f"nemesis-cli_{VERSION}_{DEB_ARCH}.deb"
result = subprocess.run(["dpkg-deb", "--build", str(PKG), str(deb_path)],
                       capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("dpkg-deb stderr:", result.stderr)
    sys.exit(1)

size_mb = deb_path.stat().st_size / (1024 * 1024)
print(f"\n=== OK: {deb_path.name} ({size_mb:.1f} MB) ===")
