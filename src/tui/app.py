import sys
import time
from pathlib import Path
import threading
import queue

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Input, Static, Label, RichLog,
    Button, TextArea, Switch
)
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from ..config import NemesisConfig, load_config, save_config
from ..providers import PROVIDER_REGISTRY
from ..tools.definitions import get_tool_definitions
from ..tools.executor import ToolExecutor
from ..agent.core import NemesisAgent
from ..agent.modes import PlanMode, DualModelMode
from ..mcp.manager import MCPManager
from ..prompts import get_system_prompt
from ..ui.theme import Colors
from .css import TUI_CSS
from .theme import THEME_COLORS


class ChatMessage(Widget):
    """A single chat message bubble."""

    def __init__(self, role: str, content: str, timestamp: float = None):
        super().__init__()
        self.role = role
        self.content = content
        self.timestamp = timestamp or time.time()
        self.height = "auto"

    def compose(self) -> ComposeResult:
        from rich.markdown import Markdown
        from rich.text import Text

        if self.role == "user":
            label = Label("  YOU", classes="msg-user")
        elif self.role == "assistant":
            label = Label("  NEMESIS", classes="msg-assistant")
        elif self.role == "tool":
            label = Label(f"  ⚙ {self.content}", classes="msg-tool")
        elif self.role == "tool_result":
            label = Label(f"    ✓ {self.content}", classes="msg-tool-result")
        elif self.role == "error":
            label = Label(f"  ✗ {self.content}", classes="msg-error")
        elif self.role == "system":
            label = Label(f"  {self.content}", classes="msg-system")
        else:
            label = Label(f"  {self.content}")

        yield label

    def render_status(self, status: str):
        if status == "running":
            self.add_class("running")
        elif status == "done":
            self.remove_class("running")


class Sidebar(Widget):
    """Session info sidebar."""

    providers = reactive(0)
    model = reactive("")
    messages = reactive(0)
    tokens = reactive(0)
    plan_mode = reactive(False)
    dual_mode = reactive(False)
    mcp_servers = reactive(0)

    def compose(self) -> ComposeResult:
        yield Label("⚡ NEMESIS-CLI", id="sidebar-title")
        yield Label("")

        yield Label("PROVIDER", classes="sidebar-section")
        yield Label("", id="prov-label", classes="sidebar-value")

        yield Label("MODEL", classes="sidebar-section")
        yield Label("", id="model-label", classes="sidebar-value")

        yield Label("")
        yield Label("SESSION", classes="sidebar-section")
        yield Label("", id="msg-label", classes="sidebar-value")
        yield Label("", id="tok-label", classes="sidebar-value")

        yield Label("")
        yield Label("MODES", classes="sidebar-section")
        yield Label("", id="plan-label", classes="sidebar-value")
        yield Label("", id="dual-label", classes="sidebar-value")

        yield Label("")
        yield Label("MCP", classes="sidebar-section")
        yield Label("", id="mcp-label", classes="sidebar-value")

    def watch_providers(self, value):
        label = self.query_one("#prov-label", Label)
        label.update(f"  {value}" if value else "  -")

    def watch_model(self, value):
        label = self.query_one("#model-label", Label)
        label.update(f"  {value}" if value else "  -")

    def watch_messages(self, value):
        label = self.query_one("#msg-label", Label)
        label.update(f"  Messages: {value}")

    def watch_tokens(self, value):
        label = self.query_one("#tok-label", Label)
        label.update(f"  Tokens: {value:,}")

    def watch_plan_mode(self, value):
        label = self.query_one("#plan-label", Label)
        if value:
            label.update("  Plan [green]ON[/]")
        else:
            label.update("  Plan [dim]OFF[/]")

    def watch_dual_mode(self, value):
        label = self.query_one("#dual-label", Label)
        if value:
            label.update("  Dual [green]ON[/]")
        else:
            label.update("  Dual [dim]OFF[/]")

    def watch_mcp_servers(self, value):
        label = self.query_one("#mcp-label", Label)
        label.update(f"  {value} serveurs")


class CommandPalette(Widget):
    """Slash command overlay."""

    def __init__(self):
        super().__init__()
        self.commands = [
            ("/help", "Afficher l'aide"),
            ("/clear", "Effacer l'historique"),
            ("/plan", "Mode plan on/off"),
            ("/dual", "Mode dual on/off"),
            ("/model", "Afficher/changer le modele"),
            ("/provider", "Lister/changer provider"),
            ("/mcp", "Gestion MCP"),
            ("/config", "Configuration"),
            ("/cost", "Usage tokens"),
            ("/status", "Statut session"),
            ("/compact", "Compacter historique"),
            ("/undo", "Annuler dernier echange"),
            ("/exit", "Quitter"),
        ]

    def compose(self) -> ComposeResult:
        for cmd, desc in self.commands:
            yield Label(f"  {cmd}  [dim]{desc}[/dim]")


class NemesisTUI(App):
    CSS = TUI_CSS
    CSS_PATH = None
    BINDINGS = [
        Binding("escape", "focus_input", "Focus", show=False),
        Binding("ctrl+c", "quit", "Quit", show=True),
    ]

    def __init__(self, config: NemesisConfig = None, debug_mode: bool = False):
        super().__init__()
        self.config = config or load_config()
        self._debug_mode = debug_mode
        self.running = True
        self.plan_mode = False
        self.dual_mode = False
        self.provider = None
        self.agent = None
        self.mcp_manager = MCPManager()
        self.tool_executor = None
        self.total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self._agent_queue = queue.Queue()
        self._agent_thread = None
        self._ping_timer = None
        self.message_count = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="app-grid"):
            with Vertical(id="chat-area"):
                yield VerticalScroll(id="chat-scroll")
                with Vertical(id="input-bar"):
                    yield Input(
                        placeholder="Message NEMESIS... (/) for commands",
                        id="input",
                    )
                    yield Label("[dim]Esc: focus  |  Ctrl+C: quit  |  /help: commands[/dim]", classes="command-hint")
            yield Sidebar(id="sidebar")
        yield Footer()

    def on_mount(self) -> None:
        self._init_components()
        self.sidebar = self.query_one(Sidebar)
        self.chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
        self.input_widget = self.query_one("#input", Input)

        self._update_sidebar()
        self._add_welcome()

    def _init_components(self):
        name = self.config.active_provider
        cls = PROVIDER_REGISTRY.get(name)
        if not cls:
            self._add_message("system", f"Provider '{name}' introuvable. Lancez --setup")
            return

        cfg = self.config.providers.get(name, {})
        self.provider = cls(
            api_key=cfg.get("api_key", ""),
            base_url=cfg.get("base_url", ""),
            model=self.config.active_model or cfg.get("model", ""),
            max_tokens=cfg.get("max_tokens", 8192),
            temperature=cfg.get("temperature", 0.7),
        )

        if not self.provider.validate_config() and name != "api_bridge":
            self._add_message("error", f"API Key manquante pour {name}. Lancez --setup")
            return

        try:
            from ..config import load_mcp_servers
            for srv_name, srv_cfg in load_mcp_servers().items():
                try:
                    cmd = srv_cfg.get("command", "")
                    if not cmd:
                        continue
                    parts = cmd.split()
                    args = parts[1:]
                    env = srv_cfg.get("env", {})
                    self.mcp_manager.add_server(srv_name, parts[0], args, env)
                except Exception:
                    pass
        except Exception:
            pass

        self.tool_executor = ToolExecutor(
            workspace=self.config.workspace,
            mcp_manager=self.mcp_manager
        )

        system_prompt = get_system_prompt()
        self.agent = NemesisAgent(
            self.provider,
            system_prompt,
            get_tool_definitions(),
            self.tool_executor,
            self.config.workspace,
            self._debug_mode,
        )

    def _update_sidebar(self):
        try:
            self.sidebar.providers = self.config.active_provider
            self.sidebar.model = self.config.active_model or (self.provider.model if self.provider else "-")
            self.sidebar.messages = len(self.agent.get_history()) if self.agent else 0
            self.sidebar.tokens = self.total_usage.get("total_tokens", 0)
            self.sidebar.plan_mode = self.plan_mode
            self.sidebar.dual_mode = self.dual_mode
            self.sidebar.mcp_servers = len(self.mcp_manager.list_servers())
        except Exception:
            pass

    def _add_welcome(self):
        self._add_raw_message("welcome", "", "")

    def _add_message(self, role: str, content: str):
        msg = ChatMessage(role, content)
        self.chat_scroll.mount(msg)
        self.chat_scroll.scroll_end(animate=False)

    def _add_raw_message(self, role: str, content: str, prefix: str = ""):
        if role == "welcome":
            from rich.markdown import Markdown

            logo = "⚡ NEMESIS-CLI v3.0"
            msg = Static(
                f"[bold #7aa2f7]{logo}[/]\n[dim]Tapez /help pour les commandes[/dim]",
                id="welcome"
            )
            sub = Static(
                f"[dim]{self.config.active_provider} / {self.config.active_model or (self.provider.model if self.provider else '-')}[/dim]",
                id="welcome-sub"
            )
            self.chat_scroll.mount(msg)
            self.chat_scroll.mount(sub)
            return

        self._add_message(role, content)

    def _process_command(self, cmd_text: str):
        parts = cmd_text.strip().split()
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        if cmd == "/exit" or cmd == "/quit" or cmd == "/q":
            self.running = False
            self.exit()
        elif cmd == "/clear" or cmd == "/c":
            if self.agent:
                self.agent.clear_history()
            self.chat_scroll.remove_children()
            self._add_welcome()
            self._add_message("system", "Historique efface")
            self._update_sidebar()
        elif cmd == "/help" or cmd == "/h" or cmd == "/?":
            commands = [
                "/help        Afficher l'aide",
                "/clear       Effacer l'historique",
                "/exit        Quitter",
                "/model       Afficher/changer le modele",
                "/provider    Lister/changer provider",
                "/plan        Mode plan on/off",
                "/dual        Mode dual setup/on/off",
                "/mcp         Gestion MCP servers",
                "/config      Gestion configuration",
                "/cost        Usage tokens",
                "/status      Statut session",
                "/compact     Compacter l'historique",
                "/undo        Annuler dernier echange",
                "/agent       Sous-agents",
            ]
            self._add_message("system", "\n".join(commands))
        elif cmd == "/plan":
            if args and args[0] in ("on", "off"):
                self.plan_mode = args[0] == "on"
            else:
                self.plan_mode = not self.plan_mode
            state = "ACTIVE" if self.plan_mode else "desactive"
            self._add_message("system", f"Mode Plan: {state}")
            self._update_sidebar()
        elif cmd == "/dual":
            if not args or args[0] == "status":
                state = "ACTIVE" if self.dual_mode else "desactive"
                self._add_message("system", f"Mode Dual: {state}")
            elif args[0] == "on":
                if self.config.dual_model:
                    self.dual_mode = True
                    self._add_message("system", "Mode Dual active")
                else:
                    self._add_message("error", "Configurez d'abord: /dual setup")
            elif args[0] == "off":
                self.dual_mode = False
                self._add_message("system", "Mode Dual desactive")
            self._update_sidebar()
        elif cmd == "/model":
            if args:
                val = " ".join(args)
                if "/" in val:
                    prov, model = val.split("/", 1)
                    self.config.active_provider = prov
                    self.config.active_model = model
                else:
                    self.config.active_model = val
                save_config(self.config)
                self._add_message("system", f"Modele: {self.config.active_provider}/{self.config.active_model}")
                self._init_components()
            else:
                self._add_message("system", f"Provider: {self.config.active_provider}\nModele: {self.config.active_model or (self.provider.model if self.provider else '-')}")
        elif cmd == "/provider":
            if args:
                if args[0] in PROVIDER_REGISTRY:
                    self.config.active_provider = args[0]
                    save_config(self.config)
                    self._init_components()
                    self._add_message("system", f"Provider change pour: {args[0]}")
                else:
                    self._add_message("error", f"Provider inconnu: {args[0]}")
            else:
                lines = []
                for name in PROVIDER_REGISTRY:
                    marker = " ◄" if name == self.config.active_provider else ""
                    lines.append(f"  {name}{marker}")
                self._add_message("system", "\n".join(lines))
            self._update_sidebar()
        elif cmd == "/cost":
            if self.agent:
                usage = self.agent.get_token_usage()
                self._add_message("system", f"Tokens - Prompt: {usage.get('prompt_tokens', 0):,} | Completion: {usage.get('completion_tokens', 0):,} | Total: {usage.get('total_tokens', 0):,}")
        elif cmd == "/status":
            info = [
                f"Version: 3.0.0",
                f"Provider: {self.config.active_provider}",
                f"Modele: {self.config.active_model or (self.provider.model if self.provider else '-')}",
                f"Plan Mode: {'ON' if self.plan_mode else 'OFF'}",
                f"Dual Mode: {'ON' if self.dual_mode else 'OFF'}",
                f"Messages: {len(self.agent.get_history()) if self.agent else 0}",
                f"MCP Servers: {len(self.mcp_manager.list_servers())}",
                f"Tokens: {self.total_usage.get('total_tokens', 0):,}",
            ]
            self._add_message("system", "\n".join(info))
        elif cmd == "/compact":
            if self.agent:
                self.agent.compact_history()
                self._add_message("system", "Historique compacte")
        elif cmd == "/undo":
            if self.agent:
                hist = self.agent.get_history()
                if len(hist) <= 1:
                    self._add_message("system", "Rien a annuler")
                else:
                    for _ in range(min(4, len(hist) - 1)):
                        self.agent.messages.pop()
                        if self.agent.messages[-1]["role"] == "user":
                            break
                    self._add_message("system", "Dernier echange annule")
        elif cmd == "/config":
            lines = [f"  {k}: {v}" for k, v in self.config.to_dict().items()
                     if k not in ("providers", "dual_model")]
            self._add_message("system", "\n".join(lines))
        elif cmd == "/mcp":
            if not args or args[0] == "list":
                servers = self.mcp_manager.list_servers()
                if servers:
                    self._add_message("system", "Serveurs MCP:\n" + "\n".join(f"  {s}" for s in servers))
                else:
                    self._add_message("system", "Aucun serveur MCP")
        else:
            self._add_message("error", f"Commande inconnue: {cmd}. /help pour l'aide.")

    def _process_message(self, user_input: str):
        if not self.agent:
            self._add_message("error", "Agent non initialise. Verifiez la configuration.")
            return

        self._add_message("user", user_input)
        self.message_count += 1
        self._update_sidebar()

        def run_agent():
            try:
                if self.plan_mode:
                    pm = PlanMode(self.agent)
                    plan = pm.create_plan(user_input, callback=None)
                    if plan.get("steps"):
                        steps_text = "\n".join(
                            f"  {s['id']}. [{s.get('done', False) and 'x' or ' '}] {s['description']}"
                            for s in plan["steps"]
                        )
                        self._agent_queue.put(("message", "system", f"Plan genere:\n{steps_text}"))
                        results = pm.execute_all(callback=None)
                        for r in results:
                            content = r.get("result", {}).get("content", "")
                            if content:
                                self._agent_queue.put(("message", "assistant", content))
                    else:
                        self._agent_queue.put(("message", "assistant", plan.get("plan", "Plan vide")))
                elif self.dual_mode:
                    dm_cfg = self.config.dual_model
                    if dm_cfg.get("model_a_api_key"):
                        from ..providers import PROVIDER_REGISTRY as PR
                        cls_a = PR.get(dm_cfg.get("model_a_provider", "groq"))
                        cls_b = PR.get(dm_cfg.get("model_b_provider", "groq"))
                        if cls_a and cls_b:
                            prov_a = cls_a(
                                api_key=dm_cfg.get("model_a_api_key", ""),
                                model=dm_cfg.get("model_a_model", ""),
                            )
                            prov_b = cls_b(
                                api_key=dm_cfg.get("model_b_api_key", ""),
                                model=dm_cfg.get("model_b_model", ""),
                            )
                            te = ToolExecutor(workspace=self.config.workspace, mcp_manager=self.mcp_manager)
                            dm = DualModelMode(prov_a, prov_b, get_tool_definitions(), te, get_system_prompt())
                            result = dm.execute(user_input, callback=None)
                            if result.get("content"):
                                self._agent_queue.put(("message", "assistant", result["content"]))
                            if result.get("status") == "approved":
                                self._agent_queue.put(("message", "system", "Solution approuvee!"))
                            else:
                                self._agent_queue.put(("message", "system", f"Max rounds ({result.get('rounds', 0)}) atteint"))
                        else:
                            self._agent_queue.put(("message", "error", "Providers dual introuvables"))
                    else:
                        self._agent_queue.put(("message", "error", "Configurez le mode dual: /dual setup"))
                else:
                    result = self.agent.chat(user_input, callback=self._tool_callback)
                    if result.get("content"):
                        self._agent_queue.put(("message", "assistant", result["content"]))
                    if result.get("error"):
                        self._agent_queue.put(("message", "error", result["error"]))
                    self.total_usage = self.agent.get_token_usage()
                self._agent_queue.put(("done", None, None))
            except Exception as e:
                self._agent_queue.put(("message", "error", str(e)))
                self._agent_queue.put(("done", None, None))

        self._agent_thread = threading.Thread(target=run_agent, daemon=True)
        self._agent_thread.start()

        self.set_interval(0.1, self._check_agent_queue)

    def _tool_callback(self, event, data):
        if event == "tool_call":
            self._agent_queue.put(("tool", data["name"], data.get("args_preview", "")))
        elif event == "tool_result":
            self._agent_queue.put(("tool_result", data["name"], str(data.get("success", False))))

    def _check_agent_queue(self):
        try:
            while True:
                msg_type, arg1, arg2 = self._agent_queue.get_nowait()
                if msg_type == "done":
                    self._update_sidebar()
                    break
                elif msg_type == "message":
                    self._add_message(arg1, arg2)
                elif msg_type == "tool":
                    self._add_message("tool", f"{arg1} {arg2[:80] if arg2 else ''}")
                elif msg_type == "tool_result":
                    success = arg2 == "True"
                    prefix = "OK" if success else "FAIL"
                    self._add_message("tool_result", f"{prefix}: {arg1}")
        except queue.Empty:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        if text.startswith("/"):
            self._process_command(text)
        else:
            self._process_message(text)

        event.input.value = ""

    def action_focus_input(self) -> None:
        self.query_one("#input", Input).focus()

