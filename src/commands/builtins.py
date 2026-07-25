from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

console = Console()

def register_all_commands(registry, app=None):
    @registry.register("help", "Afficher l'aide", "/help", "general", ["h", "?"])
    def cmd_help(ctx):
        t = Table(title="Commandes NEMESIS", box=None, padding=(0, 2), show_header=False)
        cats = ctx["app"].command_registry.list_by_category()
        cat_names = {"general": "Général", "agent": "Agent", "config": "Configuration", "debug": "Debug"}
        for cat, cmds in cats.items():
            console.print(f"\n  [bold]{cat_names.get(cat, cat)}[/bold]")
            for c in sorted(cmds, key=lambda x: x.name):
                console.print(f"    [magenta]/{c.name}[/magenta]  [dim]{c.description}[/dim]")

    @registry.register("clear", "Effacer l'historique", "/clear", "general", ["c"])
    def cmd_clear(ctx):
        ctx["app"].agent.clear_history()
        console.print("[success]  ✓ Historique effacé[/success]")

    @registry.register("exit", "Quitter", "/exit", "general", ["quit", "q"])
    def cmd_exit(ctx):
        ctx["app"].running = False

    @registry.register("model", "Afficher/changer le modèle", "/model [provider/model]", "config")
    def cmd_model(ctx):
        args = ctx.get("args", [])
        app = ctx["app"]
        if not args:
            console.print(f"  [cyan]Provider:[/cyan] {app.config.active_provider}")
            console.print(f"  [cyan]Modèle:[/cyan] {app.config.active_model or app.provider.model}")
            return
        val = " ".join(args)
        if "/" in val:
            prov, model = val.split("/", 1)
            app.config.active_provider = prov
            app.config.active_model = model
        else:
            app.config.active_model = val
        app.config = app.config
        console.print(f"[success]  ✓ Modèle: {app.config.active_provider}/{app.config.active_model}[/success]")

    @registry.register("provider", "Lister/changer provider", "/provider [name]", "config")
    def cmd_provider(ctx):
        args = ctx.get("args", [])
        if args:
            ctx["app"].config.active_provider = args[0]
            console.print(f"[success]  ✓ Provider: {args[0]}[/success]")
        else:
            from src.providers import PROVIDER_REGISTRY
            for name in PROVIDER_REGISTRY:
                marker = " ◄" if name == ctx["app"].config.active_provider else ""
                console.print(f"  [cyan]{name}[/cyan]{marker}")

    @registry.register("plan", "Mode plan on/off", "/plan [on|off]", "agent")
    def cmd_plan(ctx):
        args = ctx.get("args", [])
        app = ctx["app"]
        if args and args[0] in ("on", "off"):
            app.plan_mode = args[0] == "on"
        else:
            app.plan_mode = not app.plan_mode
        state = "[success]ACTIVÉ[/success]" if app.plan_mode else "[dim]désactivé[/dim]"
        console.print(f"  Mode Plan: {state}")

    @registry.register("dual", "Mode dual-modèle", "/dual [setup|on|off|status]", "agent")
    def cmd_dual(ctx):
        args = ctx.get("args", [])
        app = ctx["app"]
        if not args or args[0] == "status":
            console.print(f"  Mode Dual: {'[success]ON[/success]' if app.dual_mode else '[dim]OFF[/dim]'}")
            return
        if args[0] == "on":
            if app.config.dual_model:
                app.dual_mode = True
                console.print("[success]  ✓ Mode dual activé[/success]")
            else:
                console.print("[error]  Configurez d'abord: /dual setup[/error]")
        elif args[0] == "off":
            app.dual_mode = False
            console.print("  Mode dual désactivé")
        elif args[0] == "setup":
            console.print("[system]  Configuration dual-modèle...[/system]")
            dm = app.config.dual_model
            dm["model_a_provider"] = Prompt.ask("  Provider A") or "groq"
            dm["model_a_api_key"] = Prompt.ask("  API Key A", password=True) or ""
            dm["model_a_model"] = Prompt.ask("  Modèle A") or ""
            dm["model_b_provider"] = Prompt.ask("  Provider B") or "groq"
            dm["model_b_api_key"] = Prompt.ask("  API Key B", password=True) or ""
            dm["model_b_model"] = Prompt.ask("  Modèle B") or ""
            app.config.dual_model = dm
            console.print("[success]  ✓ Dual config sauvegardé. /dual on pour activer.[/success]")

    @registry.register("mcp", "Gestion MCP", "/mcp [list|add|remove]", "config")
    def cmd_mcp(ctx):
        args = ctx.get("args", [])
        mgr = ctx["app"].mcp_manager
        if not args or args[0] == "list":
            servers = mgr.list_servers()
            if not servers:
                console.print("  [dim]Aucun serveur MCP[/dim]")
                return
            for s in servers: console.print(f"  [cyan]{s}[/cyan]")
            tools = mgr.get_all_tools()
            if tools:
                console.print(f"  [dim]{len(tools)} outils MCP disponibles[/dim]")
        elif args[0] == "add" and len(args) >= 3:
            name, cmd = args[1], args[2]
            env = {}
            if mgr.add_server(name, cmd, env=env):
                console.print(f"[success]  ✓ Serveur MCP '{name}' ajouté[/success]")
            else:
                console.print(f"[error]  ✗ Échec ajout '{name}'[/error]")
        elif args[0] == "remove" and len(args) >= 2:
            mgr.remove_server(args[1])
            console.print(f"  Serveur MCP '{args[1]}' supprimé")

    @registry.register("compact", "Compacter l'historique", "/compact", "general")
    def cmd_compact(ctx):
        ctx["app"].agent.compact_history()
        console.print("[success]  ✓ Historique compacté[/success]")

    @registry.register("cost", "Afficher l'usage tokens", "/cost", "debug")
    def cmd_cost(ctx):
        usage = ctx["app"].agent.get_token_usage()
        ctx["app"].renderer.render_token_usage(usage)

    @registry.register("status", "Statut complet", "/status", "general")
    def cmd_status(ctx):
        app = ctx["app"]
        info = [
            ("Version", "3.0.0"), ("Provider", app.config.active_provider),
            ("Modèle", app.config.active_model or app.provider.model),
            ("Plan Mode", "ON" if app.plan_mode else "OFF"),
            ("Dual Mode", "ON" if app.dual_mode else "OFF"),
            ("Auto-Allow", "ON" if app.auto_allow else "OFF"),
            ("Messages", str(len(app.agent.get_history()))),
            ("MCP Servers", str(len(app.mcp_manager.list_servers()))),
        ]
        t = Table(title="Statut NEMESIS", box=None, padding=(0, 2), show_header=False)
        for k, v in info: t.add_row(f"[cyan]{k}[/cyan]", v)
        console.print(t)

    @registry.register("config", "Configuration", "/config [set key value]", "config")
    def cmd_config(ctx):
        args = ctx.get("args", [])
        if args and args[0] == "set" and len(args) >= 3:
            key, val = args[1], args[2]
            if hasattr(ctx["app"].config, key):
                setattr(ctx["app"].config, key, val)
                console.print(f"[success]  ✓ {key} = {val}[/success]")
        else:
            for k, v in ctx["app"].config.to_dict().items():
                console.print(f"  [cyan]{k}:[/cyan] {v}")

    @registry.register("agent", "Sous-agents", "/agent [list|api add|api list]", "agent")
    def cmd_agent(ctx):
        args = ctx.get("args", [])
        mgr = ctx["app"].sub_agent_mgr
        if not args or args[0] == "list":
            agents = mgr.list_agents()
            if not agents: console.print("  [dim]Aucun sous-agent actif[/dim]")
            for a in agents:
                console.print(f"  [{a['status']}] {a['id']} ({a['role']}) - {a['task'][:60]}")
        elif args[0] == "api" and len(args) >= 2:
            if args[1] == "list":
                for api in mgr.available_apis:
                    console.print(f"  [cyan]{api['name']}[/cyan] - {api['provider']} / {api.get('model','')}")
            elif args[1] == "add" and len(args) >= 5:
                mgr.configure_api(args[2], args[3], args[4], args[5] if len(args) > 5 else "", args[6] if len(args) > 6 else "")
                console.print(f"[success]  ✓ API sous-agent '{args[2]}' configurée[/success]")

    @registry.register("undo", "Annuler dernier échange", "/undo", "general")
    def cmd_undo(ctx):
        hist = ctx["app"].agent.get_history()
        if len(hist) >= 4:
            ctx["app"].agent.messages = hist[:-4] if len(hist) > 6 else [hist[0]]
            console.print("[success]  ✓ Dernier échange annulé[/success]")
        else:
            console.print("[dim]  Rien à annuler[/dim]")

    @registry.register("auto", "Mode auto-allow", "/auto", "config")
    def cmd_auto(ctx):
        ctx["app"].auto_allow = not ctx["app"].auto_allow
        state = "[success]ON[/success]" if ctx["app"].auto_allow else "[dim]OFF[/dim]"
        console.print(f"  Auto-allow: {state}")

    return registry
