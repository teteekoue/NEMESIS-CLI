#!/usr/bin/env python3
"""NEMESIS-CLI v5.0 - Agent de codage IA ultra-moderne - Interface CLI simple et élégante."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config import NemesisConfig, load_config, save_config, ensure_config_dir


def print_eagle_logo():
    """Affiche le logo aigle ASCII."""
    logo = """
                    ___
               ____/   \\____
              /             \\
             |  (o)     (o)  |
             |       <       |   N E M E S I S
             |    \\_____/    |      C L I  v5.0
             |  /         \\  |
              \\ \\  _____  / /
               \\_\\|_____||/_/
                  |_____||
                  |_____||
                  |_____||
                  |_____||
                  |_____||
    """
    print(logo)


def print_banner():
    """Affiche une ligne de séparation."""
    print("─" * 80)


def print_error(msg):
    """Affiche un message d'erreur."""
    print(f"  ✗ {msg}")


def print_success(msg):
    """Affiche un message de succès."""
    print(f"  ✓ {msg}")


def print_info(msg):
    """Affiche un message d'information."""
    print(f"  • {msg}")


def print_system(msg):
    """Affiche un message système."""
    print(f"  » {msg}")


def run_setup():
    """Configuration interactive."""
    from src.providers import PROVIDER_REGISTRY
    
    ensure_config_dir()
    
    print_eagle_logo()
    print_banner()
    print("\n  Configuration initiale v5.0\n")
    print_banner()

    config = load_config()
    print("\n  Sélectionnez un provider:")
    providers = list(PROVIDER_REGISTRY.keys())
    for i, p in enumerate(providers):
        print(f"    {i+1}. {p}")

    try:
        choice = input("\n  Provider [1/2/3/4/5/6/7] (1): ").strip() or "1"
        selected = providers[int(choice) - 1]
    except (ValueError, IndexError):
        selected = providers[0]
    
    config.active_provider = selected

    if selected != "api_bridge":
        api_key = input("  API Key: ").strip()
        default_model = PROVIDER_REGISTRY[selected]().model
        model = input(f"  Modele ({default_model}): ").strip() or default_model
        config.providers[selected] = {"api_key": api_key, "model": model}
        config.active_model = model
    else:
        host = input("  IP Bridge (192.168.1.67): ").strip() or "192.168.1.67"
        port = input("  Port (8080): ").strip() or "8080"
        config.providers["api_bridge"] = {"base_url": f"http://{host}:{port}"}

    save_config(config)
    print("\n  ✓ Configuration sauvegardee dans ~/.nemesis/config.json")
    print("  Lancez 'nemesis' sans argument pour demarrer\n")


def run_cli(debug=False):
    """Mode CLI moderne style Aider/Claude Code - Interface simple et élégante."""
    from src.tools.definitions import get_tool_definitions
    from src.tools.executor import ToolExecutor
    from src.agent.core import NemesisAgent
    from src.agent.modes import PlanMode, DualModelMode
    from src.mcp.manager import MCPManager
    from src.commands.builtins import register_all_commands
    from src.prompts import get_system_prompt
    
    config = load_config()
    
    # Afficher logo
    print_eagle_logo()
    print_banner()
    print(f"  NEMESIS-CLI v5.0")
    print(f"  Provider: {config.active_provider}")
    print(f"  Modele: {config.active_model or 'auto'}")
    print(f"  Workspace: {config.workspace}")
    print(f"  Tapez /help pour la liste des commandes")
    print_banner()

    from src.providers import PROVIDER_REGISTRY
    name = config.active_provider
    cls = PROVIDER_REGISTRY.get(name)
    if not cls:
        print_error("Provider introuvable. Lancez avec --setup")
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
        print_error("API Key manquante. Lancez avec --setup")
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

    class AppCtx:
        def __init__(self):
            self.running = True
            self.plan_mode = False
            self.dual_mode = False
            self.auto_allow = False

    ctx = AppCtx()

    def render_tool_call(name, data):
        print(f"\n  [OUTIL] {name}")
        if data.get("args"):
            for k, v in data["args"].items():
                val_str = str(v)[:100] + "..." if len(str(v)) > 100 else str(v)
                print(f"      {k}: {val_str}")

    def render_tool_result(name, data):
        status = "[OK]" if data.get("success") else "[ECHEC]"
        print(f"  {status} [RESULTAT] {name}")

    def render_message(content):
        """Affiche le message de l'assistant de manière élégante."""
        print()
        # Nettoyage basique du contenu
        lines = content.split('\n')
        for line in lines:
            # Retirer les balises markdown trop aggressives pour un affichage clean
            cleaned = line
            # Conserver le code entre ``` mais sans les backticks
            if cleaned.strip().startswith('```'):
                continue
            print(f"  {cleaned}")
        print()

    while ctx.running:
        try:
            # Input simple et élégant
            print()
            user_input = input("  nemesis ❯ ").strip()
            
            if not user_input:
                continue

            if user_input.startswith("/"):
                parts = user_input.split(maxsplit=1)
                cmd = parts[0][1:].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if cmd in ("exit", "quit", "q"):
                    print("\n  Au revoir.")
                    ctx.running = False
                    
                elif cmd in ("clear", "c"):
                    agent.clear_history()
                    print_success("Historique efface")
                    
                elif cmd == "plan":
                    if arg in ("on", "off"):
                        ctx.plan_mode = arg == "on"
                    else:
                        ctx.plan_mode = not ctx.plan_mode
                    state = "ACTIF" if ctx.plan_mode else "desactive"
                    print_system(f"Mode Plan: {state}")
                    
                elif cmd == "dual":
                    if arg == "on" and config.dual_model:
                        ctx.dual_mode = True
                    elif arg == "off":
                        ctx.dual_mode = False
                    elif arg == "setup":
                        print_system("Configuration dual-modele...")
                        dm = config.dual_model
                        try:
                            dm["model_a_provider"] = input("  Provider A (groq): ").strip() or "groq"
                            dm["model_a_api_key"] = input("  API Key A: ").strip()
                            dm["model_a_model"] = input("  Modele A (llama-3.3-70b-versatile): ").strip() or "llama-3.3-70b-versatile"
                            dm["model_b_provider"] = input("  Provider B (groq): ").strip() or "groq"
                            dm["model_b_api_key"] = input("  API Key B: ").strip()
                            dm["model_b_model"] = input("  Modele B (llama-3.3-70b-versatile): ").strip() or "llama-3.3-70b-versatile"
                            config.dual_model = dm
                            save_config(config)
                            print_success("Dual config sauvegarde")
                        except KeyboardInterrupt:
                            print("\n  Configuration annulee")
                            return
                    state = "ACTIF" if ctx.dual_mode else "desactive"
                    print_system(f"Mode Dual: {state}")
                    
                elif cmd == "cost":
                    usage = agent.get_token_usage()
                    print(f"\n  Usage tokens:")
                    print(f"    Input:  {usage.get('input_tokens', 0)}")
                    print(f"    Output: {usage.get('output_tokens', 0)}")
                    print(f"    Total:  {usage.get('total_tokens', 0)}")
                    
                elif cmd == "status":
                    print(f"\n  NEMESIS-CLI v5.0")
                    print(f"  Provider: {config.active_provider}")
                    print(f"  Modele: {config.active_model or provider.model}")
                    print(f"  Plan: {'ON' if ctx.plan_mode else 'OFF'}")
                    print(f"  Dual: {'ON' if ctx.dual_mode else 'OFF'}")
                    print(f"  Auto-Allow: {'ON' if ctx.auto_allow else 'OFF'}")
                    print(f"  Messages: {len(agent.get_history())}")
                    print(f"  MCP Servers: {len(mcp_manager.list_servers())}")
                    
                elif cmd in ("help", "h", "?"):
                    help_text = """
**Commandes disponibles:**

  **Navigation:**
    /help, /?       - Afficher cette aide
    /clear, /c      - Effacer l'historique
    /exit, /quit    - Quitter

  **Mode:**
    /plan [on|off]  - Mode planification
    /dual [setup|on|off] - Mode dual-modèle
    /auto           - Mode auto-allow tools

  **Configuration:**
    /model [prov/model] - Afficher/changer modèle
    /provider [name]    - Lister/changer provider
    /config [set k v]   - Configuration générale
    /mcp [list|add|rm]  - Gestion serveurs MCP

  **Session:**
    /status         - Statut session
    /cost           - Usage tokens
    /compact        - Compacter historique
    /undo           - Annuler dernier échange

  **Agents:**
    /agent [cmd]    - Gestion sous-agents
"""
                    print(help_text)
                    
                elif cmd == "compact":
                    agent.compact_history()
                    print_success("Historique compacte")
                    
                elif cmd == "undo":
                    hist = agent.get_history()
                    if len(hist) >= 4:
                        agent.messages = hist[:-4] if len(hist) > 6 else [hist[0]]
                        print_success("Dernier echange annule")
                    else:
                        print_info("Rien a annuler")
                        
                elif cmd == "auto":
                    ctx.auto_allow = not ctx.auto_allow
                    state = "ON" if ctx.auto_allow else "OFF"
                    print_system(f"Auto-allow: {state}")
                    
                elif cmd == "mcp":
                    sub_args = arg.split() if arg else []
                    if not sub_args or sub_args[0] == "list":
                        servers = mcp_manager.list_servers()
                        if not servers:
                            print_info("Aucun serveur MCP")
                        else:
                            for s in servers:
                                print(f"    • {s}")
                        tools = mcp_manager.get_all_tools()
                        if tools:
                            print_info(f"{len(tools)} outils MCP disponibles")
                    elif sub_args[0] == "add" and len(sub_args) >= 3:
                        srv_name, cmd_str = sub_args[1], sub_args[2]
                        if mcp_manager.add_server(srv_name, cmd_str, [], {}):
                            print_success(f"Serveur MCP '{srv_name}' ajoute")
                        else:
                            print_error(f"Echec ajout '{srv_name}'")
                    elif sub_args[0] == "remove" and len(sub_args) >= 2:
                        mcp_manager.remove_server(sub_args[1])
                        print_info(f"Serveur MCP '{sub_args[1]}' supprime")
                        
                elif cmd == "model":
                    if arg:
                        if "/" in arg:
                            prov, model = arg.split("/", 1)
                            config.active_provider = prov
                            config.active_model = model
                        else:
                            config.active_model = arg
                        save_config(config)
                        print_success(f"Modele: {config.active_provider}/{config.active_model}")
                    else:
                        print_info(f"Provider: {config.active_provider}")
                        print_info(f"Modele: {config.active_model or provider.model}")
                        
                elif cmd == "provider":
                    if arg:
                        if arg in PROVIDER_REGISTRY:
                            config.active_provider = arg
                            save_config(config)
                            print_success(f"Provider: {arg}")
                        else:
                            print_error(f"Provider inconnu: {arg}")
                    else:
                        for pname in PROVIDER_REGISTRY:
                            marker = " ◄" if pname == config.active_provider else ""
                            print(f"    {pname}{marker}")
                            
                elif cmd == "config":
                    sub_args = arg.split() if arg else []
                    if sub_args and sub_args[0] == "set" and len(sub_args) >= 3:
                        key, val = sub_args[1], sub_args[2]
                        if hasattr(config, key):
                            setattr(config, key, val)
                            save_config(config)
                            print_success(f"{key} = {val}")
                    else:
                        for k, v in config.to_dict().items():
                            print(f"    {k}: {v}")
                            
                elif cmd == "agent":
                    sub_args = arg.split() if arg else []
                    print_info("Gestion des sous-agents")
                    # Feature complète dans documentation
                    
                else:
                    print_error(f"Commande inconnue: {cmd} - tapez /help")
                continue

            # Mode Plan
            if ctx.plan_mode:
                pm = PlanMode(agent)
                plan = pm.create_plan(user_input, callback=lambda e, d: None)
                if plan.get("steps"):
                    print_system("Plan genere:")
                    for i, step in enumerate(plan["steps"], 1):
                        print(f"    {i}. {step.get('description', 'Étape')}")
                    try:
                        resp = input("\n  Executer ce plan ? (y/n): ").strip().lower()
                        if resp in ("y", "yes", "o", "oui"):
                            pm.execute_all(callback=lambda e, d: None)
                    except KeyboardInterrupt:
                        print("\n  Execution annulee")
                        
            # Mode Dual
            elif ctx.dual_mode:
                dm_cfg = config.dual_model
                if dm_cfg and dm_cfg.get("model_a_api_key"):
                    from src.providers import PROVIDER_REGISTRY
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
                        result = dm.execute(user_input, callback=lambda e, d: None)
                        if result.get("content"):
                            render_message(result["content"])
                    else:
                        print_error("Providers dual introuvables")
                else:
                    print_error("Configurez le mode dual: /dual setup")
                    
            # Mode Normal
            else:
                def callback(event, data):
                    if event == "tool_call":
                        render_tool_call(data["name"], {"args": data.get("args_preview", "")})
                    elif event == "tool_result":
                        render_tool_result(data["name"], {"success": data.get("success", False)})
                    elif event == "dual_round":
                        print_system(f"Dual Model - Round {data['round']}")
                    elif event == "review_result":
                        status = "APPROUVE" if data.get("approved") else "EN REVISION"
                        print_system(f"Review: {status}")

                result = agent.chat(user_input, callback=callback)
                if result.get("content"):
                    render_message(result["content"])
                if result.get("error"):
                    print_error(result["error"])
                    
        except KeyboardInterrupt:
            print("\n")
            continue
        except Exception as e:
            if debug:
                import traceback
                traceback.print_exc()
            print_error(str(e))

    mcp_manager.close_all()
    print_info("Session terminee")


def main():
    if "--version" in sys.argv or "-v" in sys.argv:
        print("NEMESIS-CLI v5.0.0")
        return

    if "--setup" in sys.argv:
        run_setup()
        return

    # Plus de mode TUI - tout est en CLI
    run_cli(debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
