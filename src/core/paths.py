"""Central path resolution for NEMESIS CLI (install dir vs user config)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

# Package / install root (directory containing agent.py)
INSTALL_DIR = Path(__file__).resolve().parent.parent.parent

# User-writable config & state
USER_CONFIG_DIR = Path(
    os.environ.get("NEMESIS_CONFIG_DIR", Path.home() / ".config" / "nemesis-cli")
).expanduser()

DEFAULT_WORKSPACE = Path(
    os.environ.get("NEMESIS_WORKSPACE", Path.home() / "nemesis-workspace")
).expanduser()

# Filenames
CONFIG_NAME = "config.yaml"
MCP_CONFIG_NAME = "mcp_config.yaml"
AGENTS_NAME = "agents.json"
PROMPT_NAME = "prompt_system.txt"
TOOLS_LIBRARY_NAME = "tools_library"


def ensure_user_dirs() -> Path:
    """Create user config directory and seed defaults from install if missing."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _seed_if_missing(CONFIG_NAME)
    _seed_if_missing(MCP_CONFIG_NAME)
    # tools_library: seed empty structure or copy bundled skills
    user_lib = USER_CONFIG_DIR / TOOLS_LIBRARY_NAME
    install_lib = INSTALL_DIR / TOOLS_LIBRARY_NAME
    if not user_lib.exists() and install_lib.is_dir():
        try:
            shutil.copytree(install_lib, user_lib)
        except OSError:
            user_lib.mkdir(parents=True, exist_ok=True)
    elif not user_lib.exists():
        user_lib.mkdir(parents=True, exist_ok=True)
    return USER_CONFIG_DIR


def _seed_if_missing(name: str) -> None:
    dest = USER_CONFIG_DIR / name
    if dest.exists():
        return
    src = INSTALL_DIR / name
    if src.is_file():
        try:
            shutil.copy2(src, dest)
        except OSError:
            pass


def config_path() -> Path:
    ensure_user_dirs()
    return USER_CONFIG_DIR / CONFIG_NAME


def mcp_config_path() -> Path:
    ensure_user_dirs()
    user = USER_CONFIG_DIR / MCP_CONFIG_NAME
    if user.exists():
        return user
    install = INSTALL_DIR / MCP_CONFIG_NAME
    return install if install.exists() else user


def agents_path() -> Path:
    ensure_user_dirs()
    return USER_CONFIG_DIR / AGENTS_NAME


def prompt_system_path() -> Path:
    """Prefer install prompt (read-only package data), fallback to cwd/user."""
    for candidate in (
        INSTALL_DIR / PROMPT_NAME,
        USER_CONFIG_DIR / PROMPT_NAME,
        Path.cwd() / PROMPT_NAME,
    ):
        if candidate.is_file():
            return candidate
    return INSTALL_DIR / PROMPT_NAME


def tools_library_path() -> Path:
    ensure_user_dirs()
    return USER_CONFIG_DIR / TOOLS_LIBRARY_NAME


def resolve_workspace(config: Optional[dict] = None) -> Path:
    """Resolve workspace directory from config or defaults; ensure it exists."""
    ws = None
    if isinstance(config, dict):
        sec = config.get("security") or {}
        if isinstance(sec, dict) and sec.get("workspace"):
            ws = Path(str(sec["workspace"])).expanduser()
    if ws is None:
        ws = DEFAULT_WORKSPACE
    if not ws.is_absolute():
        # Relative paths are relative to HOME, not install dir
        ws = (Path.home() / ws).resolve()
    try:
        ws.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return ws
