"""Professional, compact session header for the NEMESIS terminal UI."""

from typing import Optional

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .theme import Catppuccin


def _value(value: object, fallback: str = "—") -> str:
    text = str(value or "").strip()
    return text or fallback


def get_header(
    version: Optional[str] = None,
    provider: str = "",
    target: str = "",
    model: str = "",
    workspace: str = "",
    connected: Optional[bool] = None,
):
    """Render an information-dense header without decorative ASCII art."""
    del version
    state, state_color = (
        ("connected", Catppuccin.GREEN) if connected is True
        else ("offline", Catppuccin.RED) if connected is False
        else ("ready", Catppuccin.YELLOW)
    )

    title = Text()
    title.append("NEMESIS", style=f"bold {Catppuccin.MAUVE}")
    title.append("  controlled coding agent", style=Catppuccin.SUBTEXT0)
    title.append("   ")
    title.append(state, style=f"bold {state_color}")

    details = Table.grid(expand=True, padding=(0, 1))
    details.add_column(style=f"bold {Catppuccin.OVERLAY0}", no_wrap=True)
    details.add_column(style=Catppuccin.TEXT, overflow="ellipsis")
    details.add_column(style=f"bold {Catppuccin.OVERLAY0}", no_wrap=True)
    details.add_column(style=Catppuccin.TEXT, overflow="ellipsis")
    details.add_row("provider", _value(provider, "NEMAPI"), "model", _value(model))
    details.add_row("endpoint", _value(target), "workspace", _value(workspace))

    hints = Text()
    hints.append("/help", style=f"bold {Catppuccin.PEACH}")
    hints.append(" commands   ", style=Catppuccin.OVERLAY0)
    hints.append("/doctor", style=f"bold {Catppuccin.PEACH}")
    hints.append(" diagnostics   ", style=Catppuccin.OVERLAY0)
    hints.append("Ctrl+C", style=f"bold {Catppuccin.PEACH}")
    hints.append(" interrupt", style=Catppuccin.OVERLAY0)

    return Panel(
        Group(title, details, hints),
        border_style=Catppuccin.SURFACE1,
        padding=(1, 2),
        box=box.ROUNDED,
    )
