import os
import sys
import re
import time
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.text import Text
from rich.prompt import Prompt

# Ajout du chemin src pour les imports
sys.path.append(os.path.abspath("."))

from src.ui.theme import NEMESIS_THEME, UIColors
from src.ui.header import get_header
from src.ui.composer import Composer
from src.core.commands import registry
=======
from src.core.utils import get_resource_path, ensure_workspace_structure
>>>>>>> 5380d9a25d4e84c58e2a84c467fbc6e2b0173307
import src.core.default_commands 

from bridge_client import create_client_from_config
from tools import create_executor_from_config

class NemesisApp:
    def __init__(self, debug: bool = False):
        self.console = Console(theme=NEMESIS_THEME)
        self.composer = Composer(self.console)
        self.config_path = Path("config.yaml")
        self.config = None
        self.client = None
        self.executor = None
        self.version = "2.0.0-MODULAR"
        self.debug = debug
        self.auto_allow = False
        self.last_interrupt = 0

    def _load_config(self, force: bool = False):
        if force or not self.config_path.exists():
<<<<<<< HEAD
            self.console.print("[system]Configuration de la connexion au Bridge...[/system]")
            host = Prompt.ask("IP Bridge", default="192.168.1.67")
            port = Prompt.ask("Port", default="8080")
            self.config = {
                "bridge": {"host": host, "port": int(port)},
                "security": {"workspace": "./workspace"}