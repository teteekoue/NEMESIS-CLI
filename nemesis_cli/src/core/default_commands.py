from typing import Dict, List, Callable, Optional
import sys
import os
import yaml
import time
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from nemesis_cli.src.core.commands import registry
from nemesis_cli.src.core.skills_manager import SkillManager
from nemesis_cli.src.core.utils import ensure_workspace_structure
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt

console = Console()
skill_mgr = SkillManager()

# --- État Global pour les stats ---
SESSION_START = datetime.now()
MESSAGE_COUNT = 0

def increment_message_count():
    global MESSAGE_COUNT
    MESSAGE_COUNT += 1

@registry.register("help", "Affiche la liste des commandes disponibles")
def help_command():
    from nemesis_cli.src.ui.composer import Composer
    comp = Composer(console)
    comp.display_help_overlay()

@registry.register("clear", "Efface l'ecran du terminal")
def clear_command():
    console.clear()
    from nemesis_cli.src.ui.header import get_header
    console.print(get_header("2.0.0-MODULAR"))

@registry.register("exit", "Quitte l'application")
def exit_command():
    console.print("[yellow]Fermeture de Nemesis CLI...[/yellow]")
    sys.exit(0)

@registry.register("stats", "Affiche les statistiques de la session actuelle")
def stats_command():
    uptime = datetime.now() - SESSION_START
    table = Table(title="Statistiques de Session", border_style="bright_blue")
    table.add_column("Metrique", style="cyan")
    table.add_column("Valeur", style="white")
    table.add_row("Debut de session", SESSION_START.strftime("%H:%M:%S"))
    table.add_row("Uptime", str(uptime).split('.')[0])
    table.add_row("Messages envoyes", str(MESSAGE_COUNT))
    console.print(table)

@registry.register("config", "Affiche la configuration actuelle du Bridge")
def config_command():
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        table = Table(title="Configuration Actuelle", border_style="bright_cyan")
        table.add_column("Parametre", style="cyan")
        table.add_column("Valeur", style="white")
        bridge = config_data.get('bridge', {})
        table.add_row("Host Bridge", bridge.get('host', 'N/A'))
        table.add_row("Port Bridge", str(bridge.get('port', 'N/A')))
        table.add_row("Workspace", config_data.get('security', {}).get('workspace', 'N/A'))
        console.print(table)
    else:
        console.print("[error]Fichier de configuration introuvable.[/error]")

@registry.register("about", "Informations sur Nemesis CLI")
def about_command():
    text = Text.assemble(
        ("NEMESIS CLI\n", "bold bright_cyan"),
        ("L'agent de codage à votre portée (Windows).\n\n", "italic white"),
        ("Version : ", "dim"), ("2.0.0-MODULAR\n", "bold white"),
        ("Auteur : ", "dim"), ("Nemesis Team\n", "white"),
        ("\nInspire par le design de Gemini CLI.", "grey50")
    )
    console.print(Panel(text, border_style="bright_blue", expand=False))

@registry.register("tools", "Liste les outils systeme disponibles pour l'agent")
def tools_command():
    tools_list = [
        ("bash", "Execution de commandes shell PowerShell (synchrone/asynchrone)"),
        ("replace", "Modification intelligente de fichiers par blocs"),
        ("read", "Lecture de fichiers avec partage via lien public"),
        ("write", "Creation ou ecrasement complet de fichiers"),
        ("list_dir", "Exploration de dossiers"),
        ("validate", "Verification de syntaxe Python"),
        ("upload", "Upload de fichiers vers des services publics")
    ]
    table = Table(title="Outils Disponibles", border_style="magenta")
    table.add_column("Outil", style="bold magenta")
    table.add_column("Description", style="white")
    for name, desc in tools_list:
        table.add_row(name, desc)
    console.print(table)

@registry.register("doctor", "Vérifie la santé du système et les dépendances")
def doctor_command():
    table = Table(title="Diagnostic Système - NEMESIS CLI", border_style="bright_cyan")
    table.add_column("Composant", style="cyan")
    table.add_column("Statut", style="white")
    table.add_column("Détails", style="dim")

    # 1. Vérification des dépendances système
    tools_check = {
        "git": "Requis pour installer des skills",
        "powershell.exe": "Shell par défaut pour l'agent"
    }
    
    for tool, desc in tools_check.items():
        path = shutil.which(tool)
        status = "[green]✔ OK[/green]" if path else "[red]✘ MANQUANT[/red]"
        table.add_row(tool, status, desc)

    # 2. Vérification du Bridge
    config_path = Path("config.yaml")
    cfg = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f)
        from nemesis_cli.bridge_client import create_client_from_config
        client = create_client_from_config(cfg)
        try:
            if client.test_connection():
                table.add_row("Bridge Connection", "[green]✔ OK[/green]", f"{client.host}:{client.port}")
            else:
                table.add_row("Bridge Connection", "[red]✘ ECHEC[/red]", "Bridge injoignable")
        except:
            table.add_row("Bridge Connection", "[red]✘ ERREUR[/red]", "Erreur lors du test")
    
    # 3. Workspace
    ws_path = cfg.get("security", {}).get("workspace", "./workspace") if config_path.exists() else "./workspace"
    ws = Path(ws_path)
    if ws.exists() and ws.is_dir():
        table.add_row("Workspace", "[green]✔ OK[/green]", str(ws.resolve()))
    else:
        table.add_row("Workspace", "[yellow]! ABSENT[/yellow]", "Sera créé au besoin")

    console.print(table)

@registry.register("param", "Modifie les paramètres de configuration (IP, Port, Workspace)")
def param_command():
    config_path = Path("config.yaml")
    cfg = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f) or {}

    console.print("\n[bold magenta]Configuration des Paramètres[/bold magenta]")
    
    # Bridge
    bridge = cfg.get("bridge", {})
    new_host = Prompt.ask("IP Bridge", default=bridge.get("host", "192.168.1.67"))
    new_port = Prompt.ask("Port Bridge", default=str(bridge.get("port", "8080")))
    
    # Workspace
    security = cfg.get("security", {})
    new_ws = Prompt.ask("Chemin du Workspace", default=security.get("workspace", "./workspace"))

    # Update config
    cfg["bridge"] = {"host": new_host, "port": int(new_port)}
    cfg["security"] = {"workspace": new_ws}

    with open(config_path, "w") as f:
        yaml.dump(cfg, f)
    
    # Initialisation du nouveau workspace si nécessaire
    ensure_workspace_structure(new_ws)
    
    console.print("[success]Configuration mise à jour avec succès.[/success]")
    console.print("[yellow]Note: Certains changements nécessitent un rechargement interne.[/yellow]")
    
    return "RELOAD_CONFIG"

from nemesis_cli.src.core.utils import get_resource_path, ensure_workspace_structure
from nemesis_cli.src.core.agent_manager import AgentClient
import json

# Registre global des agents avec persistence
BASE_DIR = Path(os.path.abspath(".")).resolve()
AGENTS_FILE = BASE_DIR / "agents.json"
ACTIVE_AGENTS: Dict[str, AgentClient] = {}

def load_agents():
    if AGENTS_FILE.exists():
        try:
            with open(AGENTS_FILE, "r") as f:
                data = json.load(f)
                for name, info in data.items():
                    ACTIVE_AGENTS[name] = AgentClient(name, info["api_key"])
        except Exception as e:
            console.print(f"[error]Erreur chargement agents : {e}[/error]")

def save_agents():
    data = {name: {"api_key": ag.client.api_key} for name, ag in ACTIVE_AGENTS.items()}
    with open(AGENTS_FILE, "w") as f:
        json.dump(data, f)

# Charger au démarrage
load_agents()

@registry.register("agents", "Gere les agents subordonnes pour deleguer des taches")
def agents_command():
    while True:
        console.print("\n[bold magenta]Gestion des Agents Subordonnes (Groq)[/bold magenta]")
        console.print(f"Agents : {', '.join(ACTIVE_AGENTS.keys()) if ACTIVE_AGENTS else 'Aucun'}")
        console.print("\n1. Ajouter un agent")
        console.print("2. Chat interactif avec un agent")
        console.print("3. Supprimer un agent")
        console.print("q. Retour")
        
        choice = console.input("\nChoix > ").strip().lower()
        if choice == "1":
            name = console.input("Nom : ").strip()
            api_key = console.input("Clé API : ").strip()
            ACTIVE_AGENTS[name] = AgentClient(name, api_key)
            save_agents()
            console.print(f"[success]Agent '{name}' ajouté.[/success]")
            
        elif choice == "2":
            name = console.input("Nom de l'agent : ").strip()
            if name not in ACTIVE_AGENTS:
                console.print("[error]Agent inconnu.[/error]")
                continue
            
            agent = ACTIVE_AGENTS[name]
            console.print(f"[system]Mode chat avec {name} (tapez 'q' pour quitter).[/system]")
            while True:
                user_msg = console.input(f"\n[user]👤 {name} > [/user]")
                if user_msg == "q": break
                
                response = agent.send_message(user_msg)
                console.print(f"\n[ai]🤖 {name} :[/ai]\n{response}")
                
                # Exécution automatique si action détectée
                if "<ACTION" in response:
                    console.print("[system]Action détectée. Exécution en cours...[/system]")
                    from nemesis_cli.tools import ActionExecutor
                    executor = ActionExecutor()
                    # Extraction simple
                    import re
                    match = re.search(r'<ACTION type="([^"]+)">\n?(.*?)\n?</ACTION>', response, re.S)
                    if match:
                        act_type, act_content = match.groups()
                        for update in executor.execute_action(act_type, act_content):
                            if 'stdout' in update:
                                console.print(f"[logs]Feedback : {update['stdout']}[/logs]")
                                # Feedback automatique à l'agent
                                agent.send_message(f"FEEDBACK : {update['stdout']}", role="user")
        
        elif choice == "3":
            name = console.input("Nom à supprimer : ").strip()
            if name in ACTIVE_AGENTS:
                del ACTIVE_AGENTS[name]
                save_agents()
                console.print("[success]Supprimé.[/success]")
        elif choice == "q":
            break



@registry.register("nemesis.md", "Genere un fichier NEMESIS.md pour le suivi du projet actuel")
def nemesis_md_command():
    console.print("[yellow]Instruction de generation du NEMESIS.md envoyee a l'IA...[/yellow]")
    return "PROMPT_INTERNAL: Genere un fichier NEMESIS.md a la racine pour documenter ce projet (objectifs, structure, technologies, etat d'avancement). Utilise l'action 'write'."

@registry.register("skills", "Gere les competences (skills) de l'agent")
def skills_command():
    while True:
        installed = skill_mgr.list_installed()
        console.print("\n[bold magenta]Gestion des Skills (Claude-Compatible)[/bold magenta]")
        console.print(f"1. Liste des skills installes ({len(installed)})")
        console.print("2. Installer via URL (GitHub/ZIP)")
        console.print("3. Importer un dossier local")
        console.print("q. Retour")
        
        choice = console.input("\nChoix > ").strip().lower()
        
        if choice == "1":
            if not installed:
                console.print("[yellow]Aucun skill additionnel installe.[/yellow]")
            else:
                table = Table(title="Skills Installes", border_style="magenta")
                table.add_column("Nom", style="bold magenta")
                table.add_column("Version", style="dim")
                table.add_column("Description", style="white")
                for s in installed:
                    table.add_row(s["name"], s["version"], s["description"])
                console.print(table)
        elif choice == "2":
            url = console.input("URL du skill (.git ou .zip) : ").strip()
            if url:
                success, msg = skill_mgr.install_from_url(url)
                if success: console.print(f"[success]{msg}[/success]")
                else: console.print(f"[error]{msg}[/error]")
        elif choice == "3":
            path = console.input("Chemin du dossier local : ").strip()
            if path:
                success, msg = skill_mgr.install_from_local(path)
                if success: console.print(f"[success]{msg}[/success]")
                else: console.print(f"[error]{msg}[/error]")
        elif choice == "q":
            break
        else:
            console.print("[error]Option invalide.[/error]")
