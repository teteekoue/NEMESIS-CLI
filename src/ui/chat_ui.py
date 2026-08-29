"""NEMESIS Chat UI — slim, professional, terminal-adaptive.

No emojis. Responsive panels sized to the current terminal width.
"""

from __future__ import annotations

import time
from typing import List, Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED, SQUARE, SIMPLE
from rich.live import Live
from rich.align import Align
from rich.style import Style
from rich.rule import Rule

from .theme import Catppuccin


MAX_BASH_LINES = 400
MAX_READ_FILE_LINES = 800


def _term_width(console: Console) -> int:
    """Usable width: full terminal minus small margin, min 36."""
    try:
        w = console.size.width
    except Exception:
        w = 80
    return max(36, w - 2)


def _content_width(console: Console) -> int:
    """Slightly narrower content width for readable bubbles."""
    tw = _term_width(console)
    # Use almost full width on narrow terminals; cap only on very wide ones
    return max(36, min(tw, 140))


def _timestamp() -> str:
    return time.strftime("%H:%M:%S")


def _render_markdown(text: str) -> Markdown:
    try:
        return Markdown(
            text,
            code_theme="monokai",
            inline_code_style=Style(color=Catppuccin.PEACH),
        )
    except Exception:
        return Markdown(text)


def _truncate(s: str, n: int = 90) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


class Bubble:
    """Single chat message. Full-width panel, no overflow."""

    def __init__(self, content: str, sender: str, timestamp: Optional[float] = None):
        self.content = content or ""
        self.sender = sender
        self.ts = timestamp or time.time()
        self.is_user = sender.lower() in ("user", "you")

    def render(self, console: Console) -> Panel:
        time_str = time.strftime("%H:%M", time.localtime(self.ts))
        w = _content_width(console)
        border = Catppuccin.GREEN if self.is_user else Catppuccin.BLUE
        name_style = f"bold {border}"

        title = Text()
        title.append(self.sender, style=name_style)
        title.append(f"  {time_str}", style=Catppuccin.OVERLAY0)

        body = _render_markdown(self.content) if self.content.strip() else Text(" ", style=Catppuccin.OVERLAY0)

        return Panel(
            body,
            title=title,
            title_align="left",
            border_style=border,
            padding=(0, 1),
            width=w,
            box=ROUNDED,
            expand=False,
        )


class LiveTerminal:
    """Real-time command output frame."""

    def __init__(self, console: Console, title: str = "bash"):
        self.console = console
        self.title = title
        self.lines: List[str] = []
        self._live: Optional[Live] = None

    def __enter__(self):
        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=20,
            transient=True,
            vertical_overflow="ellipsis",
        )
        self._live.__enter__()
        return self

    def __exit__(self, *args):
        if self._live:
            self._live.__exit__(*args)

    def add_line(self, line: str):
        self.lines.append(line.rstrip("\n"))
        if len(self.lines) > MAX_BASH_LINES:
            self.lines = self.lines[-MAX_BASH_LINES:]
        if self._live:
            self._live.update(self._render())

    def _render(self) -> Panel:
        w = _content_width(self.console)
        content = "\n".join(self.lines) if self.lines else " "
        return Panel(
            Text(content, style=Catppuccin.TEXT),
            title=Text(f" {self.title} ", style=f"bold {Catppuccin.PEACH}"),
            border_style=Catppuccin.SURFACE1,
            padding=(0, 1),
            width=w,
            box=SQUARE,
        )


class ChatUI:
    """Slim chat interface."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.messages: List[Bubble] = []
        self._last_sender: Optional[str] = None

    def add_message(self, content: str, sender: str, timestamp: Optional[float] = None):
        bubble = Bubble(content, sender, timestamp)
        self.messages.append(bubble)
        if self._last_sender and self._last_sender != sender:
            self.console.print()
        self._last_sender = sender
        self.console.print(bubble.render(self.console))

    def thinking(self, message: str = "thinking..."):
        from rich.progress import Progress, SpinnerColumn, TextColumn

        with Progress(
            SpinnerColumn(spinner_name="line", style=Catppuccin.BLUE),
            TextColumn(f"[{Catppuccin.SUBTEXT0}]{message}[/]"),
            console=self.console,
            transient=True,
            refresh_per_second=12,
        ) as progress:
            progress.add_task("think", total=None)
            yield

    def tool_start(self, tool_name: str, params: dict):
        """Compact tool-call frame sized to terminal."""
        w = _content_width(self.console)
        table = Table(
            box=SIMPLE,
            border_style=Catppuccin.SURFACE1,
            width=w,
            show_header=False,
            show_edge=True,
            pad_edge=False,
            padding=(0, 1),
            collapse_padding=True,
            expand=True,
        )
        key_w = min(18, max(8, w // 5))
        table.add_column("key", style=f"bold {Catppuccin.MAUVE}", justify="right", no_wrap=True, width=key_w)
        table.add_column("value", style=Catppuccin.SUBTEXT0, overflow="fold", ratio=1)

        table.title = Text(f" {tool_name} ", style=f"bold {Catppuccin.MAUVE}")

        if params:
            for k, v in list(params.items())[:12]:
                table.add_row(str(k), _truncate(str(v), max(40, w - key_w - 8)))
        else:
            table.add_row("-", "(no params)")
        self.console.print(table)

    def tool_result(self, result: dict, tool_name: str = ""):
        w = _content_width(self.console)

        if hasattr(result, "success"):
            success = bool(result.success)
        elif isinstance(result, dict):
            success = bool(result.get("success", False))
        else:
            success = False

        color = Catppuccin.GREEN if success else Catppuccin.RED
        status = "ok" if success else "fail"

        # read_file : afficher seulement un message de confirmation, pas le contenu
        if tool_name == "read_file":
            self.console.print(
                Panel(
                    Text("Fichier lu avec succes" if success else f"Echec de lecture: {result.get('error', '')}",
                         style=color),
                    border_style=color,
                    padding=(0, 1),
                    width=w,
                    box=SQUARE,
                    title=Text(f" {tool_name} · {status} ", style=f"bold {color}"),
                    title_align="left",
                )
            )
            return

        # edit : afficher un diff structuré avec rouge/vert
        if tool_name == "edit":
            self._display_edit_diff(result, w, color, status)
            return

        output = ""
        if tool_name == "grep" and hasattr(result, "matches"):
            if result.matches:
                output = "\n".join(str(m) for m in result.matches)
        elif tool_name == "list_dir" and hasattr(result, "output"):
            output = result.output or ""
        elif isinstance(result, dict):
            output = result.get("output") or result.get("stdout") or ""
            if not output and result.get("error"):
                output = str(result["error"])

        output = (output or "").rstrip()
        display_tools = {
            "grep", "list_dir", "web_fetch", "web_search",
            "mcp_list", "mcp_tools_list", "mcp_call", "glob", "git", "todo",
            "list_agents", "check_reports", "skills_list", "delegate_task",
            "apply_patch",
        }

        if tool_name != "bash":
            if tool_name in display_tools and output:
                lines = output.splitlines()
                max_lines = 200
                if len(lines) > max_lines:
                    display = "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
                else:
                    display = output
                self.console.print(
                    Panel(
                        Text(display, style=Catppuccin.TEXT),
                        border_style=color,
                        padding=(0, 1),
                        width=w,
                        box=SQUARE,
                        title=Text(f" {tool_name} · {status} ", style=f"bold {color}"),
                        title_align="left",
                    )
                )
            else:
                self.console.print(Text(f"  {tool_name}: {status}", style=color))
            return

        # bash : afficher la sortie directement dans un panel
        if not output:
            self.console.print(
                Panel(
                    Text("(aucune sortie)", style=Catppuccin.OVERLAY0),
                    border_style=color,
                    padding=(0, 1),
                    width=w,
                    box=SQUARE,
                    title=Text(f" bash · {status} ", style=f"bold {color}"),
                    title_align="left",
                )
            )
            return

        lines = output.splitlines()
        hidden = 0
        if len(lines) > MAX_BASH_LINES:
            hidden = len(lines) - MAX_BASH_LINES
            lines = lines[-MAX_BASH_LINES:]
        display = "\n".join(lines)
        if hidden:
            display = f"... {hidden} earlier line(s) hidden\n" + display
        self.console.print(
            Panel(
                Text(display, style=Catppuccin.TEXT),
                border_style=color,
                padding=(0, 1),
                width=w,
                box=SQUARE,
                title=Text(f" bash · {status} ", style=f"bold {color}"),
                title_align="left",
            )
        )

    def _display_edit_diff(self, result: dict, w: int, color: str, status: str):
        """Affiche un diff structuré pour l'édition."""
        from rich.text import Text
        from rich.panel import Panel

        edits = result.get("edits", [])
        message = result.get("message", "Modification effectuee")
        
        if not edits:
            self.console.print(
                Panel(
                    Text(message, style=color),
                    border_style=color,
                    padding=(0, 1),
                    width=w,
                    box=SQUARE,
                    title=Text(f" edit · {status} ", style=f"bold {color}"),
                    title_align="left",
                )
            )
            return

        content = Text("")
        for edit in edits:
            if hasattr(edit, "old_string"):
                old_str = edit.old_string
                new_str = edit.new_string
                old_line = getattr(edit, "old_line", 0)
                new_line = getattr(edit, "new_line", 0)
            else:
                old_str = edit.get("old_string", "")
                new_str = edit.get("new_string", "")
                old_line = edit.get("old_line", 0)
                new_line = edit.get("new_line", 0)

            old_lines = old_str.split("\n")
            for i, line in enumerate(old_lines):
                line_num = old_line + i if old_line else i + 1
                content.append(f"-{line_num} {line}\n", style=Catppuccin.RED)

            new_lines = new_str.split("\n")
            for i, line in enumerate(new_lines):
                line_num = new_line + i if new_line else i + 1
                content.append(f"+{line_num} {line}\n", style=Catppuccin.GREEN)

            content.append("\n", style=Catppuccin.OVERLAY0)

        if not content:
            content = Text("(aucun changement visible)", style=Catppuccin.OVERLAY0)

        self.console.print(
            Panel(
                content,
                border_style=color,
                padding=(0, 1),
                width=w,
                box=SQUARE,
                title=Text(f" edit · {status} ", style=f"bold {color}"),
                title_align="left",
            )
        )

    def tool_error(self, error: str):
        w = _content_width(self.console)
        self.console.print(
            Panel(
                Text(str(error), style=Catppuccin.RED),
                border_style=Catppuccin.RED,
                padding=(0, 1),
                width=w,
                box=SQUARE,
                title=Text(" error ", style=f"bold {Catppuccin.RED}"),
                title_align="left",
            )
        )

    def auth_prompt(self, tool_name: str, params: dict) -> Panel:
        """Mini frame for tool authorization."""
        w = min(_content_width(self.console), 72)
        lines = [
            Text(f"Tool: ", style=Catppuccin.SUBTEXT0) + Text(tool_name, style=f"bold {Catppuccin.MAUVE}"),
        ]
        if params:
            for k, v in list(params.items())[:8]:
                lines.append(
                    Text(f"  {k}: ", style=Catppuccin.OVERLAY0)
                    + Text(_truncate(str(v), max(30, w - 12)), style=Catppuccin.TEXT)
                )
        lines.append(Text(""))
        lines.append(
            Text("y", style=f"bold {Catppuccin.GREEN}")
            + Text(" once   ", style=Catppuccin.SUBTEXT0)
            + Text("a", style=f"bold {Catppuccin.BLUE}")
            + Text(" always   ", style=Catppuccin.SUBTEXT0)
            + Text("n", style=f"bold {Catppuccin.RED}")
            + Text(" deny", style=Catppuccin.SUBTEXT0)
        )
        return Panel(
            Group(*lines),
            title=Text(" authorization ", style=f"bold {Catppuccin.YELLOW}"),
            title_align="left",
            border_style=Catppuccin.YELLOW,
            padding=(0, 1),
            width=w,
            box=ROUNDED,
        )

    def live_terminal(self, title: str = "bash") -> LiveTerminal:
        return LiveTerminal(self.console, title)

    def task_summary(self, elapsed: float, tool_count: int = 0):
        if elapsed >= 60:
            mins, secs = divmod(int(elapsed), 60)
            time_str = f"{mins:02d}:{secs:02d}"
        else:
            time_str = f"{elapsed:.1f}s"
        parts = [f"done in {time_str}"]
        if tool_count:
            parts.append(f"{tool_count} tool(s)")
        self.console.print(Text("  " + " · ".join(parts), style=Catppuccin.OVERLAY0))

    def welcome(self, version: str = "2.1.0", provider: str = "", target: str = ""):
        w = _content_width(self.console)
        brand = Text()
        brand.append("NEMESIS", style=f"bold {Catppuccin.MAUVE}")
        brand.append(f"  v{version}", style=Catppuccin.OVERLAY0)

        lines = [
            brand,
            Text("autonomous coding agent", style=f"italic {Catppuccin.SUBTEXT0}"),
        ]
        if provider:
            lines.append(Text(f"{provider}  ->  {target}", style=Catppuccin.GREEN))
        lines.append(Text("type /help for commands", style=Catppuccin.OVERLAY0))

        self.console.print(
            Panel(
                Group(*lines),
                border_style=Catppuccin.SURFACE1,
                padding=(1, 2),
                width=w,
                box=ROUNDED,
            )
        )
        self.console.print()

    def clear(self):
        self.console.clear()
