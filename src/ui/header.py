"""NEMESIS — Minimal modern header.

No ASCII art. Clean, professional branding with status indicators.
"""

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from .theme import Catppuccin


def get_header(version="2.1.0", provider="", target=""):
    """Render a clean, modern header panel."""

    # Brand — minimal, just the name
    brand = Text()
    brand.append("NEMESIS", style=f"bold {Catppuccin.MAUVE}")
    brand.append("  CLI", style=f"bold {Catppuccin.BLUE}")
    brand.append(f"  v{version}", style=f"{Catppuccin.OVERLAY0}")

    # Tagline
    tagline = Text("autonomous coding agent", style=f"italic {Catppuccin.SUBTEXT0}")

    # Connection info (compact)
    info_parts = []
    if provider:
        info_parts.append(Text(f" {provider}", style=f"{Catppuccin.GREEN}"))
    if target:
        info_parts.append(Text(f"→ {target}", style=f"{Catppuccin.SUBTEXT0}"))
    if info_parts:
        info = Text("  ").join(info_parts)
    else:
        info = Text("ready", style=f"{Catppuccin.SUBTEXT0}")

    # Layout: brand left, info right
    inner = Columns(
        [Align.left(brand), Align.right(info)],
        expand=True,
    )

    body = Group(
        inner,
        Align.left(tagline),
    )

    return Panel(
        body,
        border_style=Catppuccin.SURFACE1,
        padding=(0, 2),
        width=None,
        subtitle=None,
    )
