#!/usr/bin/env python3
"""NEMESIS-CLI v3.0 - Agent de codage IA moderne avec TUI Textual."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import NemesisConfig, load_config, save_config, ensure_config_dir
from src.providers import PROVIDER_REGISTRY


def run_setup():
    """Configuration interactive."""
    from rich.console import Console
    from rich.prompt import Prompt, Confirm

    console = Console()
    ensure_config_dir()

    logo = (
        "[bold #FF79C6] N E M E S I S"
        "[bold #BD93F9] -"
        "[bold #8BE9FD] C L I[/bold #8BE9FD]"
    )
    console.print(f"\n[bold bright_cyan]{logo}[/bold bright_cyan]")
    console.print("[system]  Configuration initiale v3.0[/system]\n")

    config = load_config()
    console.print("  Selectionnez un provider:")
    providers = list(PROVIDER_REGISTRY.keys())
    for i, p in enumerate(providers):
        console.print(f"    [cyan]{i+1}[/cyan]. {p}")

    choice = Prompt.ask(
        "  Provider",
        choices=[str(i + 1) for i in range(len(providers))],
        default="1"
    )
    selected = providers[int(choice) - 1]
    config.active_provider = selected

    if selected != "api_bridge":
        api_key = Prompt.ask("  API Key", password=True)
        model = Prompt.ask("  Modele", default=PROVIDER_REGISTRY[selected]().model)
        config.providers[selected] = {"api_key": api_key, "model": model}
        config.active_model = model
    else:
        host = Prompt.ask("  IP Bridge", default="192.168.1.67")
        port = Prompt.ask("  Port", default="8080")
        config.providers["api_bridge"] = {"base_url": f"http://{host}:{port}"}

    save_config(config)
    console.print("\n[success]  Configuration sauvegardee dans ~/.nemesis/config.json[/success]")
    console.print("[dim]  Lancez nemesis sans argument pour demarrer le TUI[/dim]\n")


def run_cli(debug=False):
    """Mode CLI (legacy prompt_toolkit + rich)."""
    from src.ui.theme import NEMESIS_THEME
    from src.tools.definitions import get_tool_definitions
    from src.tools.executor import ToolExecutor
    from src.agent.core import NemesisAgent
    from src.agent.modes import PlanMode, DualModelMode
    from src.mcp.manager import MCPManager
    from src.ui.renderer import OutputRenderer
    from src.ui.input_handler import NemesisInputHandler
    from src.commands.registry import CommandRegistry
    from src.commands.builtins import register_all_commands
    from src.prompts import get_system_prompt
    from rich.console import Console
    from rich.prompt import Confirm

    config = load_config()
    console = Console(theme=NEMESIS_THEME)
    renderer = OutputRenderer(console)

    name = config.active_provider
    cls = PROVIDER_REGISTRY.get(name)
    if not cls:
        console.print("[error] Provider introuvable. Lancez avec --setup[/error]")
        sys.exit(1)

    cfg = config.providers.get(name, {})
    provider = cls(
        api_key=cfg.get("api_key", ""),
        base_url=cfg.get("base_url", ""),
        model=config.active_model or cfg.get("model", ""),
        max_tokens=cfg.get("max_tokens", 8192),
        temperature=cfg.get("temperature", 0.7),
    )

    if not provider.validate_config() and name != "api_bridge":
        console.print("[error] API Key manquante. Lancez avec --setup[/error]")
        sys.exit(1)

    from src.config import load_mcp_servers
    mcp_manager = MCPManager()
    for srv_name, srv_cfg in load_mcp_servers().items():
        try:
            cmd = srv_cfg.get("command", "")
            if not cmd:
                continue
            parts = cmd.split()
            args = parts[1:] if len(parts) > 1 else []
            env = srv_cfg.get("env", {})
            mcp_manager.add_server(srv_name, parts[0], args, env)
        except Exception:
            pass

    tool_exec = ToolExecutor(workspace=config.workspace, mcp_manager=mcp_manager)
    system_prompt = get_system_prompt()
    agent = NemesisAgent(provider, system_prompt, get_tool_definitions(), tool_exec, config.workspace, debug)

    renderer.render_welcome("3.0.0", config.active_provider, config.active_model or provider.model)

    class AppCtx:
        def __init__(self):
            self.running = True
            self.plan_mode = False
            self.dual_mode = False

    ctx = AppCtx()

    def agent_callback(event, data):
        if event == "tool_call":
            renderer.render_tool_call(data["name"], {"args": data.get("args_preview", "")})
        elif event == "tool_result":
            renderer.render_tool_result(data["name"], {"success": data.get("success", False)})

    input_handler = NemesisInputHandler()

    while ctx.running:
        try:
            user_input = input_handler.get_input()
            if not user_input:
                continue

            if user_input.startswith("/"):
                parts = user_input.split(maxsplit=1)
                cmd = parts[0][1:].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if cmd in ("exit", "quit", "q"):
                    ctx.running = False
                elif cmd in ("clear", "c"):
                    agent.clear_history()
                elif cmd in ("plan",):
                    if arg in ("on", "off"):
                        ctx.plan_mode = arg == "on"
                    else:
                        ctx.plan_mode = not ctx.plan_mode
                    console.print(f"  Mode Plan: {'ON' if ctx.plan_mode else 'OFF'}")
                elif cmd in ("dual",):
                    if arg == "on" and config.dual_model:
                        ctx.dual_mode = True
                    elif arg == "off":
                        ctx.dual_mode = False
                    console.print(f"  Mode Dual: {'ON' if ctx.dual_mode else 'OFF'}")
                elif cmd in ("cost",):
                    usage = agent.get_token_usage()
                    renderer.render_token_usage(usage)
                elif cmd in ("status",):
                    console.print(f"  Provider: {config.active_provider}")
                    console.print(f"  Modele: {config.active_model or provider.model}")
                    console.print(f"  Plan: {'ON' if ctx.plan_mode else 'OFF'}")
                    console.print(f"  Dual: {'ON' if ctx.dual_mode else 'OFF'}")
                    console.print(f"  Messages: {len(agent.get_history())}")
                elif cmd in ("help", "h", "?"):
                    console.print("  /help /clear /exit /model /provider /plan /dual /cost /status /compact /undo")
                elif cmd in ("compact",):
                    agent.compact_history()
                    console.print("  Historique compacte")
                else:
                    console.print(f"  Commande inconnue: {cmd}")
                continue

            if ctx.plan_mode:
                pm = PlanMode(agent)
                plan = pm.create_plan(user_input, callback=agent_callback)
                if plan.get("steps"):
                    console.print("\n[system]  Plan genere:[/system]")
                    renderer.render_plan(plan["steps"])
                    if Confirm.ask("  Executer ce plan ?"):
                        pm.execute_all(callback=agent_callback)
            elif ctx.dual_mode:
                dm_cfg = config.dual_model
                if dm_cfg.get("model_a_api_key"):
                    cls_a = PROVIDER_REGISTRY.get(dm_cfg.get("model_a_provider", "groq"))
                    cls_b = PROVIDER_REGISTRY.get(dm_cfg.get("model_b_provider", "groq"))
                    if cls_a and cls_b:
                        prov_a = cls_a(
                            api_key=dm_cfg.get("model_a_api_key", ""),
                            model=dm_cfg.get("model_a_model", ""),
                        )
                        prov_b = cls_b(
                            api_key=dm_cfg.get("model_b_api_key", ""),
                            model=dm_cfg.get("model_b_model", ""),
                        )
                        te = ToolExecutor(workspace=config.workspace, mcp_manager=mcp_manager)
                        dm = DualModelMode(prov_a, prov_b, get_tool_definitions(), te, get_system_prompt())
                        result = dm.execute(user_input, callback=agent_callback)
                        if result.get("content"):
                            renderer.render_assistant_message(result["content"])
                    else:
                        renderer.render_error("Providers dual introuvables")
                else:
                    renderer.render_error("Configurez le mode dual: /dual setup")
            else:
                result = agent.chat(user_input, callback=agent_callback)
                if result.get("content"):
                    renderer.render_assistant_message(result["content"])
                if result.get("error"):
                    renderer.render_error(result["error"])
        except KeyboardInterrupt:
            continue
        except Exception as e:
            if debug:
                import traceback
                traceback.print_exc()
            renderer.render_error(str(e))

    mcp_manager.close_all()
    console.print("\n[dim]  Au revoir.[/dim]")


def run_tui(debug=False):
    """Mode TUI moderne avec Textual."""
    from src.tui.app import NemesisTUI

    config = load_config()

    if not config.providers.get(config.active_provider, {}).get("api_key") and config.active_provider != "api_bridge":
        from rich.console import Console
        Console().print("[error] API Key manquante. Lancez avec --setup[/error]")
        sys.exit(1)

    app = NemesisTUI(config=config, debug=debug)
    app.run()


def main():
    if "--version" in sys.argv or "-v" in sys.argv:
        print("NEMESIS-CLI v3.0.0")
        return

    if "--setup" in sys.argv:
        run_setup()
        return

    if "--cli" in sys.argv:
        run_cli(debug="--debug" in sys.argv)
        return

    run_tui(debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
