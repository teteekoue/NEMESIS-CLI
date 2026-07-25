from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.text import Text
from rich.tree import Tree
from rich.syntax import Syntax
from rich import box
from .theme import Colors


class OutputRenderer:
    def __init__(self, console: Console):
        self.console = console

    def render_welcome(self, version, provider, model):
        from .logo import get_full_logo
        self.console.print(f"\n[bold bright_cyan]{get_full_logo()}[/bold bright_cyan]")
        self.console.print(f"  [dim]v{version} | {provider} / {model}[/dim]")
        self.console.print(f"  [dim]Tapez /help pour les commandes[/dim]\n")

    def render_assistant_message(self, content: str):
        try:
            md = Markdown(content)
            self.console.print(Panel(md, border_style=Colors.PURPLE, padding=(0, 1), expand=False))
        except Exception:
            self.console.print(Panel(content, border_style=Colors.PURPLE, padding=(0, 1), expand=False))

    def render_tool_call(self, name, data):
        args_preview = str(data.get("args", ""))[:120]
        self.console.print(f"  [tool]\u2699 {name}[/tool] [dim]{args_preview}[/dim]")

    def render_tool_result(self, name, data):
        if data.get("success"):
            self.console.print(f"  [success]\u2713 {name}[/success]")
        else:
            self.console.print(f"  [error]\u2717 {name}[/error]")

    def render_error(self, message: str):
        self.console.print(f"  [error]\u2717 Erreur: {message}[/error]")

    def render_plan(self, steps):
        tree = Tree("[bold]Plan d'ex\u00e9cution[/bold]")
        for step in steps:
            status = "\u2713" if step.get("done") else "\u25cb"
            tree.add(f"[dim]{status}[/dim] {step.get('description', '')}")
        self.console.print(tree)

    def render_token_usage(self, usage: dict):
        t = Table(title="Usage Tokens", box=None, padding=(0, 2), show_header=False)
        t.add_row("[cyan]Prompt:[/cyan]", str(usage.get("prompt_tokens", 0)))
        t.add_row("[cyan]Completion:[/cyan]", str(usage.get("completion_tokens", 0)))
        t.add_row("[cyan]Total:[/cyan]", str(usage.get("total_tokens", 0)))
        self.console.print(t)

    def render_code_block(self, code: str, language: str = "python"):
        try:
            syntax = Syntax(code, language, theme="monokai", line_numbers=True)
            self.console.print(Panel(syntax, border_style=Colors.BLUE, padding=(0, 1), expand=False))
        except Exception:
            self.console.print(Panel(code, border_style=Colors.BLUE, expand=False))

    def render_info(self, message: str):
        self.console.print(f"  [system]\u2139 {message}[/system]")

    def render_success(self, message: str):
        self.console.print(f"  [success]\u2713 {message}[/success]")
