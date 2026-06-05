from rich.theme import Theme
from rich.style import Style

# Définition du thème Nemesis inspiré par Gemini CLI
# Utilisation de jetons sémantiques pour faciliter la maintenance
NEMESIS_THEME = Theme({
    "user": "bold bright_cyan",
    "ai": "bold bright_blue",
    "action": "bold magenta",
    "command": "cyan",
    "logs": "italic dim white",
    "success": "bold green",
    "error": "bold red",
    "system": "bold yellow",
    "debug": "dim yellow",
    "header.title": "bold white",
    "header.subtitle": "italic dim white",
    "header.version": "bright_black",
    "input.prompt": "bold bright_cyan",
    "input.slash": "bold magenta",
    "border.active": "bright_blue",
    "border.dim": "bright_black"
})

class UIColors:
    PRIMARY = "bright_blue"
    SECONDARY = "bright_cyan"
    ACCENT = "magenta"
    SUCCESS = "green"
    ERROR = "red"
    WARNING = "yellow"
    DIM = "bright_black"
