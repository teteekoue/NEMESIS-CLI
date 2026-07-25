#!/usr/bin/env python3
"""NEMESIS-CLI v3.0 - Agent de codage IA moderne."""
import os, sys, json, time
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.prompt import Prompt, Confirm

from src.config import NemesisConfig, load_config, save_config, ensure_config_dir, load_mcp_servers, save_mcp_servers
from src.providers import PROVIDER_REGISTRY
from src.tools.definitions import get_tool_definitions
from src.tools.executor import ToolExecutor
from src.agent.core import NemesisAgent
from src.agent.sub_agent import SubAgentManager
from src.agent.modes import PlanMode, DualModelMode
from src.mcp.manager import MCPManager
from src.ui.theme import NEMESIS_THEME, Colors
from src.ui.logo import get_full_logo
from src.ui.renderer import OutputRenderer
from src.ui.input_handler import NemesisInputHandler
from src.commands.registry import CommandRegistry
from src.commands.builtins import register_all_commands
from src.prompts import get_system_prompt


class NemesisApp:
    def __init__(self, debug=False):
        self.console = Console(theme=NEMESIS_THEME)
        self.renderer = OutputRenderer(self.console)
        self.config = load_config()
        self.debug = debug
        self.running = True
        self.auto_allow = self.config.auto_allow
        self.plan_mode = False
        self.dual_mode = False
        self.provider = None
        self.agent = None
        self.mcp_manager = MCPManager()
        self.sub_agent_mgr = SubAgentManager(workspace=self.config.workspace)
        self.command_registry = CommandRegistry()
        self.input_handler = None
        self.total_usage = {}
        self.message_count = 0

    def _create_provider(self, name=None):
        name = name or self.config.active_provider
        cls = PROVIDER_REGISTRY.get(name)
        if not cls: return None
        cfg = self.config.providers.get(name, {})
        return cls(
            api_key=cfg.get("api_key", ""),
            base_url=cfg.get("base_url", ""),
            model=self.config.active_model or cfg.get("model", ""),
            max_tokens=cfg.get("max_tokens", 8192),
            temperature=cfg.get("temperature", 0.7),
        )

    def setup(self):
        """Configuration interactive au premier lancement."""
        ensure_config_dir()
        self.console.print(f"[bold bright_cyan]{get_full_logo()}[/bold bright_cyan]")
        self.console.print("[system]  Configuration initiale NEMESIS-CLI v3.0[/system]\n")

        self.console.print("  Sélectionnez un provider:")
        providers = list(PROVIDER_REGISTRY.keys())
        for i, p in enumerate(providers):
            self.console.print(f"    [cyan]{i+1}[/cyan]. {p}")
        choice = Prompt.ask("  Provider", choices=[str(i+1) for i in range(len(providers))], default="1")
        selected = providers[int(choice) - 1]
        self.config.active_provider = selected

        if selected != "api_bridge":
            api_key = Prompt.ask("  API Key", password=True)
            model = Prompt.ask("  Modèle", default=PROVIDER_REGISTRY[selected]().model)
            self.config.providers[selected] = {"api_key": api_key, "model": model}
            self.config.active_model = model
        else:
            host = Prompt.ask("  IP Bridge", default="192.168.1.67")
            port = Prompt.ask("  Port", default="8080")
            self.config.providers["api_bridge"] = {"base_url": f"http://{host}:{port}"}

        save_config(self.config)
        self.console.print("\n[success]  ✓ Configuration sauvegardée dans ~/.nemesis/config.json[/success]\n")

    def _init_components(self):
        self.provider = self._create_provider()
        if not self.provider:
            self.console.print("[error]  Provider introuvable. Lancez avec --setup[/error]")
            sys.exit(1)
        if not self.provider.validate_config() and self.config.active_provider != "api_bridge":
            self.console.print("[error]  API Key manquante. Lancez avec --setup[/error]")
            sys.exit(1)

        self.mcp_manager = MCPManager()
        for srv_name, srv_cfg in load_mcp_servers().items():
            try:
                cmd = srv_cfg.get("command", "")
                args = cmd.split()[1:]
                env = srv_cfg.get("env", {})
                self.mcp_manager.add_server(srv_name, cmd.split()[0] if cmd else "", args, env)
            except: pass

        tool_exec = ToolExecutor(workspace=self.config.workspace, mcp_manager=self.mcp_manager)
        system_prompt = get_system_prompt()
        self.agent = NemesisAgent(self.provider, system_prompt, get_tool_definitions(), tool_exec, self.config.workspace, self.debug)

        register_all_commands(self.command_registry, self)
        self.input_handler = NemesisInputHandler(commands=self.command_registry.get_names())

    def run(self):
        debug = "--debug" in sys.argv
        setup = "--setup" in sys.argv
        if setup:
            app = NemesisApp(debug)
            app.setup()
            return

        self._init_components()
        self.renderer.render_welcome("3.0.0", self.config.active_provider, self.config.active_model or self.provider.model)

        while self.running:
            try:
                user_input = self.input_handler.get_input()
                if not user_input:
                    continue
                if user_input.startswith("/"):
                    self._handle_command(user_input)
                    continue
                self._process_message(user_input)
            except KeyboardInterrupt:
                continue
            except Exception as e:
                if self.debug:
                    import traceback
                    traceback.print_exc()
                self.renderer.render_error(str(e))

        self.mcp_manager.close_all()
        self.console.print("\n[dim]  Au revoir. [/dim]")

    def _handle_command(self, cmd_str):
        parts = cmd_str.split(maxsplit=1)
        cmd_name = parts[0][1:].lower()
        args = parts[1].split() if len(parts) > 1 else []
        cmd = self.command_registry.get(cmd_name)
        if cmd:
            ctx = {"app": self, "agent": self.agent, "config": self.config, "ui": self.renderer, "args": args}
            result = cmd.handler(ctx)
            if result:
                self.console.print(str(result))
        else:
            self.console.print(f"[error]  Commande inconnue: {cmd_name}. /help pour l'aide.[/error]")

    def _process_message(self, message):
        if self.plan_mode:
            from src.agent.modes import PlanMode
            pm = PlanMode(self.agent)
            plan = pm.create_plan(message, callback=self._agent_callback)
            if plan.get("steps"):
                self.console.print("\n[system]  Plan généré:[/system]")
                self.renderer.render_plan(plan["steps"])
                if Confirm.ask("  Exécuter ce plan ?"):
                    pm.execute_all(callback=self._agent_callback)

        elif self.dual_mode:
            dm_cfg = self.config.dual_model
            if dm_cfg.get("model_a_api_key"):
                prov_a = self._create_provider(dm_cfg.get("model_a_provider", "groq"))
                prov_b = self._create_provider(dm_cfg.get("model_b_provider", "groq"))
                if prov_a and prov_b:
                    tool_exec = ToolExecutor(workspace=self.config.workspace, mcp_manager=self.mcp_manager)
                    dm = DualModelMode(prov_a, prov_b, get_tool_definitions(), tool_exec, get_system_prompt())
                    result = dm.execute(message, callback=self._agent_callback)
                    if result.get("content"):
                        self.renderer.render_assistant_message(result["content"])
                else:
                    self.renderer.render_error("Impossible de créer les providers dual")
            else:
                self.renderer.render_error("Configurez le mode dual: /dual setup")
        else:
            result = self.agent.chat(message, callback=self._agent_callback)
            if result.get("content"):
                self.renderer.render_assistant_message(result["content"])
            if result.get("error"):
                self.renderer.render_error(result["error"])
            self.total_usage = self.agent.get_token_usage()

    def _agent_callback(self, event, data):
        if event == "tool_call":
            self.renderer.render_tool_call(data["name"], {"args": data.get("args_preview", "")})
        elif event == "tool_result":
            self.renderer.render_tool_result(data["name"], {"success": data.get("success", False)})
        elif event == "debug":
            if self.debug:
                self.console.print(f"[dim]  [DBG] {data.get('msg','')}[/dim]")


if __name__ == "__main__":
    NemesisApp(debug="--debug" in sys.argv).run()
