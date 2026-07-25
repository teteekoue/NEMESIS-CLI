#!/usr/bin/env python3
"""Configuration NEMESIS-CLI."""
import os, json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

CONFIG_DIR = Path.home() / ".nemesis"
CONFIG_FILE = CONFIG_DIR / "config.json"
MCP_CONFIG_FILE = CONFIG_DIR / "mcp_servers.json"

@dataclass
class NemesisConfig:
    active_provider: str = "groq"
    active_model: str = ""
    workspace: str = "./workspace"
    auto_allow: bool = False
    debug: bool = False
    max_iterations: int = 100
    providers: Dict[str, dict] = field(default_factory=dict)
    sub_agent_apis: List[dict] = field(default_factory=list)
    dual_model: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for d in ["workspace", "logs", "tools_library"]:
        (CONFIG_DIR / d).mkdir(exist_ok=True)

def load_config():
    ensure_config_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f: return NemesisConfig.from_dict(json.load(f))
        except Exception: pass
    return NemesisConfig()

def save_config(cfg):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f: json.dump(cfg.to_dict(), f, indent=2, ensure_ascii=False)

def load_mcp_servers():
    if MCP_CONFIG_FILE.exists():
        try:
            with open(MCP_CONFIG_FILE) as f: return json.load(f)
        except Exception: pass
    return {}

def save_mcp_servers(s):
    ensure_config_dir()
    with open(MCP_CONFIG_FILE, "w") as f: json.dump(s, f, indent=2, ensure_ascii=False)
