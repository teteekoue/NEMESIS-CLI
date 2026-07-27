#!/usr/bin/env python3
"""NEMESIS-CLI v4.0 - Agent de codage IA ultra-moderne inspiré de Claude Code."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import NemesisConfig, load_config, save_config, ensure_config_dir
from src.providers import PROVIDER_REGISTRY


def print_eagle_logo(console):
    """Affiche le logo aigle ASCII."""
    from rich.panel import Panel
    from rich.text import Text
    
    eagle = r"""
                    ___
               ____/   \____
              /             \
             |  (o)     (o)  |
             |       <       |   N E M E S I S
             |    \_____/    |      C L I  v4.0
             |  /         \  |
              \ \  _____  / /
               \_\|_____||/_/
                  |_____||
                  |_____||
                  |_____||
                  |_____||
                  |_____||
    """
    logo_text = Text(eagle, style="bold #7aa2f7")
    console.print(Panel(logo_text, border_style="#bd93f9", padding=(1, 2)))


def run_setup():
    """Configuration interactive."""
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel

    console = Console()
    ensure_config_dir()
    
    print_eagle_logo(console)
    console.print("\n[bold bright_cyan]  Configuration initiale v4.0[/bold bright_cyan]\n")

    config = load_config()
    console.print("  [dim]Selectionnez un provider:[/dim]")
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
    console.print("\n[green]✓[/green] [success]Configuration sauvegardee dans ~/.nemesis/config.json[/success]")
    console.print("[dim]  Lancez nemesis sans argument pour demarrer le TUI[/dim]\n")


def run_cli(debug=False):
    """Mode CLI moderne style Claude Code."""
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
    from src.ui.logo import get_eagle_logo
    from rich.console import Console
    from rich.prompt import Confirm
    from rich.panel import Panel
    from rich.markdown import Markdown

    config = load_config()
    console = Console(theme=NEMESIS_THEME)
    renderer = OutputRenderer(console)

    # Afficher logo aigle
    eagle = get_eagle_logo()
    console.print(Panel(eagle, border_style="#bd93f9", padding=(0, 2)))

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

    renderer.render_welcome("4.0.0", config.active_provider, config.active_model or provider.model)

    class AppCtx:
        def __init__(self):
            self.running = True
            self.plan_mode = False
            self.dual_mode = False
            self.auto_allow = False

    ctx = AppCtx()

    def agent_callback(event, data):
        if event == "tool_call":
            renderer.render_tool_call(data["name"], {"args": data.get("args_preview", "")})
        elif event == "tool_result":
            renderer.render_tool_result(data["name"], {"success": data.get("success", False)})
        elif event == "dual_round":
            console.print(f"\n[dim]  Dual Model - Round {data['round']}[/dim]")
        elif event == "review_result":
            status = "[green]APPROUVE[/green]" if data.get("approved") else "[yellow]EN REVISION[/yellow]"
            console.print(f"  Review: {status}")

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
                    console.print("[green]✓[/green] [dim]Historique efface[/dim]")
                elif cmd in ("plan",):
                    if arg in ("on", "off"):
                        ctx.plan_mode = arg == "on"
                    else:
                        ctx.plan_mode = not ctx.plan_mode
                    state = "[green]ACTIF[/green]" if ctx.plan_mode else "[dim]desactive[/dim]"
                    console.print(f"  Mode Plan: {state}")
                elif cmd in ("dual",):
                    if arg == "on" and config.dual_model:
                        ctx.dual_mode = True
                    elif arg == "off":
                        ctx.dual_mode = False
                    elif arg == "setup":
                        console.print("[system]  Configuration dual-modele...[/system]")
                        dm = config.dual_model
                        dm["model_a_provider"] = Prompt.ask("  Provider A", default="groq")
                        dm["model_a_api_key"] = Prompt.ask("  API Key A", password=True, default="")
                        dm["model_a_model"] = Prompt.ask("  Modele A", default="llama-3.3-70b-versatile")
                        dm["model_b_provider"] = Prompt.ask("  Provider B", default="groq")
                        dm["model_b_api_key"] = Prompt.ask("  API Key B", password=True, default="")
                        dm["model_b_model"] = Prompt.ask("  Modele B", default="llama-3.3-70b-versatile")
                        config.dual_model = dm
                        save_config(config)
                        console.print("[green]✓[/green] [success]Dual config sauvegarde[/success]")
                        return
                    state = "[green]ACTIF[/green]" if ctx.dual_mode else "[dim]desactive[/dim]"
                    console.print(f"  Mode Dual: {state}")
                elif cmd in ("cost",):
                    usage = agent.get_token_usage()
                    renderer.render_token_usage(usage)
                elif cmd in ("status",):
                    console.print(f"\n  [bold]NEMESIS-CLI v4.0[/bold]")
                    console.print(f"  Provider: {config.active_provider}")
                    console.print(f"  Modele: {config.active_model or provider.model}")
                    console.print(f"  Plan: {'[green]ON[/green]' if ctx.plan_mode else '[dim]OFF[/dim]'}")
                    console.print(f"  Dual: {'[green]ON[/green]' if ctx.dual_mode else '[dim]OFF[/dim]'}")
                    console.print(f"  Auto-Allow: {'[green]ON[/green]' if ctx.auto_allow else '[dim]OFF[/dim]'}")
                    console.print(f"  Messages: {len(agent.get_history())}")
                    console.print(f"  MCP Servers: {len(mcp_manager.list_servers())}")
                elif cmd in ("help", "h", "?"):
                    help_text = """
**Commandes disponibles:**
- `/help` - Afficher cette aide
- `/clear` ou `/c` - Effacer l'historique
- `/exit` ou `/quit` ou `/q` - Quitter
- `/model [provider/model]` - Afficher/changer le modèle
- `/provider [name]` - Lister/changer provider
- `/plan [on|off]` - Mode planification
- `/dual [setup|on|off]` - Mode dual-modèle
- `/mcp [list|add|remove]` - Gestion serveurs MCP
- `/config [set key value]` - Configuration
- `/cost` - Usage tokens
- `/status` - Statut session
- `/compact` - Compacter historique
- `/undo` - Annuler dernier échange
- `/auto` - Mode auto-allow tools
- `/agent [list|api add|api list]` - Sous-agents
"""
                    console.print(Markdown(help_text))
                elif cmd in ("compact",):
                    agent.compact_history()
                    console.print("[green]✓[/green] [dim]Historique compacte[/dim]")
                elif cmd in ("undo",):
                    hist = agent.get_history()
                    if len(hist) >= 4:
                        agent.messages = hist[:-4] if len(hist) > 6 else [hist[0]]
                        console.print("[green]✓[/green] [dim]Dernier echange annule[/dim]")
                    else:
                        console.print("[dim]  Rien a annuler[/dim]")
                elif cmd in ("auto",):
                    ctx.auto_allow = not ctx.auto_allow
                    state = "[green]ON[/green]" if ctx.auto_allow else "[dim]OFF[/dim]"
                    console.print(f"  Auto-allow: {state}")
                elif cmd in ("mcp",):
                    sub_args = arg.split() if arg else []
                    if not sub_args or sub_args[0] == "list":
                        servers = mcp_manager.list_servers()
                        if not servers:
                            console.print("  [dim]Aucun serveur MCP[/dim]")
                        else:
                            for s in servers:
                                console.print(f"  [cyan]{s}[/cyan]")
                        tools = mcp_manager.get_all_tools()
                        if tools:
                            console.print(f"  [dim]{len(tools)} outils MCP disponibles[/dim]")
                    elif sub_args[0] == "add" and len(sub_args) >= 3:
                        srv_name, cmd_str = sub_args[1], sub_args[2]
                        if mcp_manager.add_server(srv_name, cmd_str, [], {}):
                            console.print(f"[green]✓[/green] [success]Serveur MCP '{srv_name}' ajoute[/success]")
                        else:
                            console.print(f"[red]✗[/red] [error]Echec ajout '{srv_name}'[/error]")
                    elif sub_args[0] == "remove" and len(sub_args) >= 2:
                        mcp_manager.remove_server(sub_args[1])
                        console.print(f"  Serveur MCP '{sub_args[1]}' supprime")
                elif cmd in ("model",):
                    if arg:
                        if "/" in arg:
                            prov, model = arg.split("/", 1)
                            config.active_provider = prov
                            config.active_model = model
                        else:
                            config.active_model = arg
                        save_config(config)
                        console.print(f"[green]✓[/green] [success]Modele: {config.active_provider}/{config.active_model}[/success]")
                    else:
                        console.print(f"  Provider: {config.active_provider}")
                        console.print(f"  Modele: {config.active_model or provider.model}")
                elif cmd in ("provider",):
                    if arg:
                        if arg in PROVIDER_REGISTRY:
                            config.active_provider = arg
                            save_config(config)
                            console.print(f"[green]✓[/green] [success]Provider: {arg}[/success]")
                        else:
                            console.print(f"[red]✗[/red] [error]Provider inconnu: {arg}[/error]")
                    else:
                        for pname in PROVIDER_REGISTRY:
                            marker = " [green]◄[/green]" if pname == config.active_provider else ""
                            console.print(f"  [cyan]{pname}[/cyan]{marker}")
                elif cmd in ("config",):
                    sub_args = arg.split() if arg else []
                    if sub_args and sub_args[0] == "set" and len(sub_args) >= 3:
                        key, val = sub_args[1], sub_args[2]
                        if hasattr(config, key):
                            setattr(config, key, val)
                            save_config(config)
                            console.print(f"[green]✓[/green] [success]{key} = {val}[/success]")
                    else:
                        for k, v in config.to_dict().items():
                            console.print(f"  [cyan]{k}:[/cyan] {v}")
                elif cmd in ("agent",):
                    sub_args = arg.split() if arg else []
                    # Gestion simplifiée des sous-agents
                    console.print("  [dim]Gestion des sous-agents (feature complète dans TUI)[/dim]")
                else:
                    console.print(f"  [red]Commande inconnue: {cmd}[/red] - tapez /help")
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
                if dm_cfg and dm_cfg.get("model_a_api_key"):
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
        print("NEMESIS-CLI v4.0.0")
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
