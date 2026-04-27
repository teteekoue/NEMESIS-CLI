#!/usr/bin/env python3
"""
NEMESIS CLI - Version Gemini Stable Colorée
Usage: python agent.py [--debug]
"""
import os
import sys
import re
import time
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.markdown import Markdown
from rich.theme import Theme
from rich.text import Text

from bridge_client import create_client_from_config
from tools import create_executor_from_config

# Thème visuel
custom_theme = Theme({
    "user": "bold bright_cyan",
    "ai": "bold bright_blue",
    "action": "bold magenta",
    "command": "cyan",
    "logs": "italic dim white",
    "success": "bold green",
    "error": "bold red",
    "system": "bold yellow",
    "debug": "dim yellow"
})

console = Console(theme=custom_theme)

class NemesisCLI:
    def __init__(self, config_path: str = "config.yaml", debug: bool = False):
        self.config_path = Path(config_path)
        self.config = None
        self.client = None
        self.executor = None
        self.auto_allow = False
        self.last_input = ""
        self.debug = debug

    def _debug_log(self, msg: str):
        if self.debug:
            console.print(f"[debug][DEBUG] {msg}[/debug]")

    def run(self):
        try:
            console.clear()

            if not self.config_path.exists():
                self._load_config(force=True)
            else:
                if Prompt.ask("[bold white]Utiliser la configuration existante ?[/bold white]", choices=["o", "n"], default="o") == "n":
                    self._load_config(force=True)
                else:
                    self._load_config()

            self.client = create_client_from_config(self.config)
            self.executor = create_executor_from_config(self.config, bridge=self.client)

            console.print(Panel(
                f"[system]NEMESIS CLI[/system]\n"
                f"[dim]• Bridge :[/dim] [success]{self.client.host}:{self.client.port}[/success]\n"
                f"[dim]• Debug :[/dim] [success]{'ON' if self.debug else 'OFF'}[/success]\n",
                border_style="bright_cyan", expand=False
            ))

            if not self.client.test_connection():
                console.print("[error]❌ Bridge injoignable.[/error]")
                return

            console.print("[success]✔ Prêt.[/success]\n")

            if Prompt.ask("[bold white]Nouveau prompt ?[/bold white]", choices=["o", "n"], default="o") == "o":
                self._initialize_ai()

            self._interactive_loop()
        except KeyboardInterrupt:
            console.print("\n[system]👋 Au revoir ![/system]")
            sys.exit(0)

    def _load_config(self, force: bool = False) -> bool:
        if force or not self.config_path.exists():
            host = Prompt.ask("IP Bridge", default="192.168.1.67")
            port = Prompt.ask("Port", default="8080")
            self.config = {'bridge': {'host': host, 'port': int(port)}, 'security': {'workspace': './workspace'}}
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f)
        else:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        return True

    def _initialize_ai(self):
        p_path = Path("prompt_system.txt")
        if not p_path.exists():
            return
        with open(p_path, 'r') as f:
            prompt = f.read()
        with Progress(SpinnerColumn(), TextColumn("[system]Synchronisation IA...[/system]"), transient=True) as p:
            p.add_task("init")
            self.client.send_message(prompt)

    def _interactive_loop(self):
        while True:
            user_input = Prompt.ask(f"\n[user]👤 Vous[/user]")
            if user_input.lower() in ['q', 'exit', 'quit']:
                break
            self.last_input = user_input
            self._process_cycle(user_input)

    def _process_cycle(self, message: str):
        current_input = message
        iteration = 0
        start_time = time.time()
        while iteration < 100:
            iteration += 1
            self._debug_log(f"Iteration {iteration} - Envoi au Bridge...")
            with Progress(SpinnerColumn(), TextColumn("[system]NEMESIS réfléchit...[/system]"), TimeElapsedColumn(), transient=True) as progress:
                progress.add_task("thinking")
                result = self.client.send_message(current_input)
            self._debug_log(f"Reponse Bridge: success={result.get('success')}, len={len(result.get('response',''))}")
            if not result['success']:
                console.print(f"[error]❌ Bridge erreur: {result.get('error', 'inconnu')}[/error]")
                break
            parsed = self._parse_response(result['response'])
            self._debug_log(f"Parsed: action={parsed['action']['type'] if parsed['action'] else 'None'}")
            if parsed['text']:
                console.print()
                console.print(f"[ai]🤖 NEMESIS :[/ai]")
                console.print(Markdown(parsed['text']))
                console.print()
            if parsed['action']:
                act_type = parsed['action']['type']
                act_content = parsed['action']['content']
                console.print(f"[action]⚡ ACTION :[/action] [command]{act_type.upper()}[/command]")
                console.print(f"[dim]Contenu :[/dim]\n[command]{act_content}[/command]\n")

                if not self.auto_allow:
                    choice = Prompt.ask("  [system]Autoriser ?[/system]", choices=["y", "n", "a"], default="y")
                    if choice == "a":
                        self.auto_allow = True
                    elif choice == "n":
                        break
                final_res = {}
                for update in self.executor.execute_action(act_type, act_content):
                    if 'partial' in update:
                        log_line = Text(f"    {update['line']}", style="logs")
                        console.print(log_line, end="")
                    else:
                        final_res = update
                console.print()
                self._debug_log(f"Action result: success={final_res.get('success')}")
                if final_res.get('success'):
                    console.print(f"[success]✔ {act_type.upper()} OK[/success]")
                else:
                    console.print(f"[error]✘ {act_type.upper()} ÉCHOUÉ[/error]")
                current_input = self._format_feedback(parsed['action'], final_res)
                continue
            break

        elapsed = time.time() - start_time
        mins, secs = divmod(int(elapsed), 60)
        console.print(f"\n[system]⏱ Temps total: {mins:02d}:{secs:02d}[/system]")

    def _parse_response(self, resp: str) -> Dict:
        parsed = {'text': resp, 'action': None}
        # Supprime les blocs de code markdown pour eviter les fausses actions
        cleaned = re.sub(r'```.*?```', '', resp, flags=re.S)
        a = re.search(r'<ACTION\s+type="([\w-]+)">(.*?)</ACTION>', cleaned, re.S | re.I)
        if a:
            parsed['action'] = {'type': a.group(1).lower(), 'content': a.group(2).strip()}
        clean_text = re.sub(r'<ACTION.*?>.*?</ACTION>', '', resp, flags=re.S | re.I)
        parsed['text'] = clean_text.strip()
        return parsed

    def _format_feedback(self, action: Dict, res: Dict) -> str:
        output = res.get('stdout', res.get('content', ''))
        MAX_CHARS = 500000
        if len(output) > MAX_CHARS:
            output = output[:MAX_CHARS] + "\n\n[AVERTISSEMENT SYSTEME : Logs tronques. Utilisez 'read' sur les fichiers de log pour voir la suite.]"
        return f"FEEDBACK:\nAction: {action['type']}\nSucces: {res.get('success', False)}\nOutput:\n{output}"


if __name__ == "__main__":
    debug_mode = "--debug" in sys.argv
    NemesisCLI(debug=debug_mode).run()
