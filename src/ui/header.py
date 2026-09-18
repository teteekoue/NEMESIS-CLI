"""Branding and session header for the NEMESIS-CLI terminal UI."""

from __future__ import annotations

from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .theme import Catppuccin


ASCII_LOGO = r""" _   _ _____ __  __ _____ ____ ___ ____
| \ | | ____|  \/  | ____/ ___|_ _/ ___|
|  \| |  _| | |\/| |  _| \___ \| |\___ \
| |\  | |___| |  | | |___ ___) | | ___) |
|_| \_|_____|_|  |_|_____|____/___|____/
                 NEMESIS-CLI"""


def _value(value: object, fallback: str = "—") -> str:
    text = str(value or "").strip()
    return text or fallback


def get_header(
    version: str | None = None,
    provider: str = "",
    target: str = "",
    model: str = "",
    workspace: str = "",
    connected: bool | None = None,
):
    """Render the product banner and the most useful session parameters.

    ``version`` remains accepted for callers from older integrations but is
    intentionally not rendered: the CLI branding must never be version-bound.
    """
    del version
    status = "connected" if connected is True else "offline" if connected is False else "not tested"
    status_color = (
        Catppuccin.GREEN if connected is True
        else Catppuccin.RED if connected is False
        else Catppuccin.YELLOW
    )

    logo = Text(ASCII_LOGO, style=f"bold {Catppuccin.MAUVE}")
    tagline = Text("l'agent autonome de codage", style=f"bold {Catppuccin.BLUE}")

    table = Table(box=box.SIMPLE, show_header=False, expand=True, padding=(0, 1))
    table.add_column("key", style=f"bold {Catppuccin.SUBTEXT0}", no_wrap=True)
    table.add_column("value", style=Catppuccin.TEXT, overflow="ellipsis")
    table.add_row("provider", _value(provider, "NEMAPI"))
    table.add_row("model", _value(model))
    table.add_row("endpoint", _value(target))
    table.add_row("workspace", _value(workspace))
    table.add_row("status", Text(status, style=f"bold {status_color}"))

    hints = Text()
    hints.append("/help", style=f"bold {Catppuccin.PEACH}")
    hints.append(" commands  ·  ", style=Catppuccin.OVERLAY0)
    hints.append("/status", style=f"bold {Catppuccin.PEACH}")
    hints.append(" session  ·  ", style=Catppuccin.OVERLAY0)
    hints.append("Ctrl+C", style=f"bold {Catppuccin.PEACH}")
    hints.append(" interrupt", style=Catppuccin.OVERLAY0)

    body = Group(
        Align.center(logo),
        Align.center(tagline),
        table,
        hints,
    )
    return Panel(
        body,
        border_style=Catppuccin.MAUVE,
        padding=(1, 2),
        box=box.ROUNDED,
    )
