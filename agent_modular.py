import os
import sys
import re
import time
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.text import Text
from rich.prompt import Prompt

# Ajout du chemin src pour les imports
sys.path.append(os.path.abspath("."))

from src.ui.theme import NEMESIS_THEME, UIColors
from src.ui.header import get_header
from src.ui.composer import Composer
from src.core.commands import registry
import src.core.default_commands 

from bridge_client import create_client_from_config
from tools import create_executor_from_config

class NemesisApp:
    def __init__(self, debug: bool = False):
        self.console = Console(theme=NEMESIS_THEME)
        self.composer = Composer(self.console)
        self.config_path = Path("config.yaml")
        self.config = None
        self.client = None
        self.executor = None
        self.version = "2.0.0-MODULAR"
        self.debug = debug
        self.auto_allow = False

    def _load_config(self, force: bool = False):
        if force or not self.config_path.exists():
            self.console.print("[system]Configuration de la connexion au Bridge...[/system]")
            host = Prompt.ask("IP Bridge", default="192.168.1.67")
            port = Prompt.ask("Port", default="8080")
            self.config = {
                'bridge': {'host': host, 'port': int(port)},
                'security': {'workspace': './workspace'}
            }
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f)
        else:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)

    def _initialize_ai(self):
        p_path = Path("prompt_system.txt")
        if not p_path.exists():
            return
        
        if Prompt.ask("[bold white]Envoyer le prompt système ?[/bold white]", choices=["o", "n"], default="o") == "n":
            self.console.print("[yellow]Initialisation sans prompt système.[/yellow]")
            return

        with open(p_path, 'r') as f:
            prompt = f.read()
        with Progress(SpinnerColumn(), TextColumn("[system]Synchronisation IA...[/system]"), transient=True) as p:
            p.add_task("init")
            self.client.send_message(prompt)

    def _parse_response(self, resp: str) -> Dict:
        parsed = {'text': resp, 'action': None}
        if resp.startswith("FEEDBACK:"):
            parsed['text'] = resp
            return parsed

        action_pattern = re.compile(r'```(?:[a-z]*)\s*?(<ACTION.*?>.*?</ACTION>)\s*?```', re.S | re.I)
        match = action_pattern.search(resp)
        if match:
            action_full = match.group(1)
            parsed['text'] = resp.replace(match.group(0), "").strip()
            type_match = re.search(r'<ACTION\s+type="([\w-]+)">', action_full, re.I)
            if type_match:
                action_type = type_match.group(1).lower()
                content_match = re.search(r'<ACTION.*?>\s*(.*?)\s*</ACTION>', action_full, re.S | re.I)
                action_content = content_match.group(1).strip() if content_match else ""
                parsed['action'] = {'type': action_type, 'content': action_content}
        else:
            parsed['text'] = resp.strip()
        return parsed

    def _format_feedback(self, action: Dict, res: Dict) -> str:
        output = res.get('stdout', res.get('content', ''))
        MAX_CHARS = 500000
        if len(output) > MAX_CHARS:
            output = output[:MAX_CHARS] + "\n\n[AVERTISSEMENT SYSTEME : Logs tronqués.]"
        return f"FEEDBACK:\nAction: {action['type']}\nSuccès: {res.get('success', False)}\nOutput:\n{output}"

    def _process_cycle(self, message: str):
        from src.core.default_commands import increment_message_count
        increment_message_count()
        current_input = message
        iteration = 0
        while iteration < 100:
            iteration += 1
            if self.debug:
                self.console.print(f"[debug]Iteration {iteration}: Envoi au Bridge...[/debug]")
            
            with Progress(SpinnerColumn(), TextColumn("[system]NEMESIS réfléchit...[/system]"), TimeElapsedColumn(), transient=True) as progress:
                progress.add_task("thinking")
                result = self.client.send_message(current_input)
            
            if not result['success']:
                self.console.print(f"[error]Bridge erreur: {result.get('error', 'inconnu')}[/error]")
                break
            
            parsed = self._parse_response(result['response'])
            if self.debug:
                self.console.print(f"[debug]Reponse recue ({len(result.get('response', ''))} chars)[/debug]")
            
            if parsed['text']:
                self.console.print(f"\n[ai]NEMESIS :[/ai]")
                self.console.print(Markdown(parsed['text']))
            
            if parsed['action']:
                act_type = parsed['action']['type']
                act_content = parsed['action']['content']
                
                self.console.print(Panel(
                    f"[action]ACTION :[/action] [command]{act_type.upper()}[/command]\n[dim]{act_content[:500]}[/dim]...",
                    border_style="magenta", title="Action Request"
                ))

                if not self.auto_allow:
                    choice = self.console.input("\n  [system]Autoriser ? (y/n/a) [/system]").lower()
                    if choice == "a": self.auto_allow = True
                    elif choice == "n": break
                
                final_res = {}
                for update in self.executor.execute_action(act_type, act_content):
                    if 'partial' in update:
                        self.console.print(Text(f"    {update['line']}", style="logs"), end="")
                    else:
                        final_res = update
                
                if final_res.get('success'):
                    self.console.print(f"[success]OK: {act_type.upper()}[/success]")
                else:
                    self.console.print(f"[error]ECHEC: {act_type.upper()}[/error]")
                
                current_input = self._format_feedback(parsed['action'], final_res)
                continue
            break

    def run(self):
        self.console.clear()
        
        if not self.config_path.exists():
            self._load_config(force=True)
        else:
            if Prompt.ask("[bold white]Utiliser la configuration existante ?[/bold white]", choices=["o", "n"], default="o") == "n":
                self._load_config(force=True)
            else:
                self._load_config()

        self.client = create_client_from_config(self.config)
        self.executor = create_executor_from_config(self.config, bridge=self.client)

        self.console.clear()
        self.console.print(get_header(self.version))
        
        self.console.print(Panel(
            f"[dim]Bridge :[/dim] [success]{self.client.host}:{self.client.port}[/success]",
            border_style="bright_cyan", expand=False
        ))

        if not self.client.test_connection():
            self.console.print("[error]Bridge injoignable.[/error]")
            return

        self._initialize_ai()

        try:
            while True:
                user_input = self.composer.get_input()
                if not user_input: continue

                if user_input.startswith("/"):
                    parts = user_input[1:].split()
                    if not parts:
                        self.composer.display_help_overlay()
                        continue
                    
                    cmd_name = parts[0]
                    cmd = registry.get_command(cmd_name)
                    if cmd:
                        res = cmd.handler()
                        if isinstance(res, str) and res.startswith("PROMPT_INTERNAL:"):
                            self._process_cycle(res.replace("PROMPT_INTERNAL:", "").strip())
                    else:
                        self.console.print(f"[error]Commande inconnue: /{cmd_name}[/error]")
                        self.composer.display_help_overlay()
                else:
                    self._process_cycle(user_input)

        except KeyboardInterrupt:
            self.console.print("\n[system]Au revoir ![/system]")

if __name__ == "__main__":
    debug_mode = "--debug" in sys.argv
    app = NemesisApp(debug=debug_mode)
    app.run()
