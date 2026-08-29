import os
import sys
import time
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich import box

from src.ui.theme import NEMESIS_THEME
from src.ui.header import get_header
from src.ui.composer import Composer
from src.core.commands import registry
import src.core.default_commands  # noqa: F401 — enregistre les commandes /
from providers import create_provider
from tools import create_executor_from_config
from action_parser import ActionParser


class NemesisApp:
    def __init__(self, debug: bool = False):
        self.version = "2.1.0"
        self.console = Console(theme=NEMESIS_THEME)
        self.composer = Composer(version=self.version)
        self._console = self.console  # alias for direct access
        # User config lives in ~/.config/nemesis-cli (not install dir)
        from src.core.paths import (
            config_path,
            mcp_config_path,
            ensure_user_dirs,
            resolve_workspace,
            INSTALL_DIR,
            USER_CONFIG_DIR,
        )
        ensure_user_dirs()
        self.install_dir = INSTALL_DIR
        self.user_config_dir = USER_CONFIG_DIR
        self.config_path = config_path()
        self.mcp_config_path = mcp_config_path()
        self.config = None
        self.client = None
        self.executor = None
        self.parser = ActionParser()
        self.debug = debug
        self.auto_allow = False
        self.last_interrupt = 0
        self.session_start = 0.0
        self._conn_ok = None
        self._prompt_sent = False
        # Système d'autorisation pour les outils
        self._authorized_tools = set()  # Outils autorisés pour cette session (mode 'a')
        self._last_auth_choice = None  # Dernier choix d'autorisation
        # Stockage des sorties de commandes pour affichage différé
        self._hidden_outputs = {}  # Dict: {output_id: {"command": str, "output": str, "success": bool}}
        self._output_counter = 0  # Compteur pour générer les IDs de sortie
        # Flag pour gérer l'interruption propre
        self._interrupted = False  # True si l'utilisateur a interrompu la tâche en cours

    def _load_config(self):
        from src.core.paths import resolve_workspace, DEFAULT_WORKSPACE

        config_exists = self.config_path.exists()
        needs_save = False

        if config_exists:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                self.config = loaded if isinstance(loaded, dict) else {}
        else:
            self.config = {}
            needs_save = True

        # MCP stays in its own file — never merge into provider config
        # (tools load mcp_config.yaml via MCPManager)

        # Valeurs par defaut pour les sections manquantes ou invalides
        if not isinstance(self.config.get("provider"), dict) or not self.config["provider"]:
            self.config["provider"] = {"type": "bridge"}
            needs_save = True
        if not isinstance(self.config.get("bridge"), dict):
            self.config["bridge"] = {"host": "192.168.1.67", "port": 8080}
            needs_save = True
        if not isinstance(self.config.get("security"), dict):
            self.config["security"] = {"workspace": str(DEFAULT_WORKSPACE)}
            needs_save = True
        elif not self.config["security"].get("workspace"):
            self.config["security"]["workspace"] = str(DEFAULT_WORKSPACE)
            needs_save = True

        # S'assurer que provider.type existe
        if "type" not in self.config["provider"]:
            self.config["provider"]["type"] = "bridge"
            needs_save = True

        # Normalize workspace path and ensure directory exists
        ws = resolve_workspace(self.config)
        self.config["security"]["workspace"] = str(ws)

        # Sauvegarder si des valeurs par defaut ont ete ajoutees
        if needs_save:
            self._save_config()

    def _save_config(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        # Never persist MCP server blocks inside main config
        clean = {
            k: v
            for k, v in (self.config or {}).items()
            if k in ("provider", "bridge", "security", "nemapi_v3", "nemapi", "openai", "groq", "xai", "openrouter")
            or (isinstance(v, dict) and "type" in (self.config.get("provider") or {}) and k == "provider")
        }
        # Keep full config but strip known MCP-only keys that may have been merged historically
        to_save = dict(self.config or {})
        for mcp_key in list(to_save.keys()):
            if mcp_key in ("calculator", "github") and isinstance(to_save.get(mcp_key), dict):
                if "command" in to_save[mcp_key] and "type" not in to_save[mcp_key]:
                    to_save.pop(mcp_key, None)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(to_save, f, default_flow_style=False, allow_unicode=True)

    def reconfigure_provider(self, new_config: Dict[str, Any]):
        """Reconfigure le provider a chaud (appelle par /provider)."""
        old_conversation = self.client.get_conversation() if self.client else []
        try:
            new_client = create_provider(new_config)
            conn_ok = new_client.test_connection()
            if not conn_ok:
                return False, "Connexion impossible avec la nouvelle config"

            self.client = new_client
            self.client.set_conversation(old_conversation)
            self.config = new_config
            self._conn_ok = True
            self._prompt_sent = False
            self._save_config()
            return True, "Provider reconfigure"
        except Exception as e:
            return False, str(e)

    def _show_commands(self):
        """Affiche la liste des commandes disponibles."""
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        
        # Créer un tableau plus élégant
        table = Table(
            title="[bold bright_cyan]Commandes Disponibles[/bold bright_cyan]",
            border_style="bright_cyan",
            box=box.DOUBLE_EDGE,
            show_header=True,
            header_style="bold bright_cyan"
        )
        table.add_column("[bold yellow]Commande[/bold yellow]", style="bold yellow", width=20)
        table.add_column("[white]Description[/white]", style="white", width=60)
        
        # Trier les commandes par nom
        sorted_commands = sorted(registry.list_commands(), key=lambda c: c.name)
        
        for cmd in sorted_commands:
            cmd_name = f"[bold cyan]/{cmd.name}[/bold cyan]"
            desc = cmd.description or "[dim]Aucune description[/dim]"
            table.add_row(cmd_name, desc)
        
        # Ajouter un pied de tableau
        table.add_row("", "[dim]Tapez /help pour plus d'informations[/dim]", style="dim")
        
        self.console.print(Panel(table, border_style="bright_cyan", padding=(1, 2)))

    def _handle_interrupt(self):
        now = time.time()
        if now - self.last_interrupt < 2:
            # Double Ctrl+C : fermeture forcée
            self.console.print("\n[error]Fermeture forcee...[/error]")
            sys.exit(0)
        else:
            # Premier Ctrl+C : interrompre la tâche en cours
            self._interrupted = True
            self.last_interrupt = now
            self.console.print("\n[yellow] Tâche interrompue. Tapez Ctrl+C encore pour forcer la fermeture.[/yellow]")

    def _parse_response(self, resp: str) -> Dict:
        """Parse une réponse LLM via le parseur multi-niveaux (ActionParser).

        Supporte 6 niveaux : YAML, JSON strict, JSON relaxé,
        blocs nus, XML, regex fallback.
        """
        return self.parser.parse(resp)

    def _ask_for_authorization(self, tool_name: str, action_content: Dict) -> bool:
        """Ask the user to authorize a tool call. Returns True if allowed."""
        if tool_name in self._authorized_tools:
            return True

        params = action_content if isinstance(action_content, dict) else {"value": action_content}
        self.console.print()
        if hasattr(self.composer, "display_auth"):
            self.composer.display_auth(tool_name, params)
        else:
            self.console.print(f"[yellow]Authorize tool:[/yellow] {tool_name}")

        while True:
            try:
                choice = self.composer.prompt_input(title=self.composer.AUTH_TITLE if hasattr(self.composer, "AUTH_TITLE") else "authorization [y/n/a]")
                if choice:
                    choice = choice.strip().lower()
                    if choice in ("y", "yes"):
                        self._last_auth_choice = "y"
                        return True
                    if choice in ("n", "no"):
                        self._last_auth_choice = "n"
                        return False
                    if choice in ("a", "always"):
                        self._authorized_tools.add(tool_name)
                        self._last_auth_choice = "a"
                        self.console.print(f"[green]  '{tool_name}' authorized for this session[/green]")
                        return True
                self.console.print("[dim]  reply y, n, or a[/dim]")
            except (EOFError, KeyboardInterrupt):
                self.console.print("[yellow]  cancelled[/yellow]")
                return False

    def _format_feedback(self, action: Dict, res: Dict) -> str:
        output = res.get('stdout', res.get('content', ''))
        MAX_CHARS = 10_000_000  # 10 Mo - augmente de 500 Ko
        if len(output) > MAX_CHARS:
            output = output[:MAX_CHARS] + "\n\n[AVERTISSEMENT SYSTEME : Logs tronques.]"
        tool_name = action['type']
        success = res.get('success', False)
        
        # S'assurer que output n'est jamais vide - au minimum un message par défaut
        if not output:
            output = "[Aucune sortie capturee - la commande a peut-etre echoue ou n'a produit aucune sortie]"
        
        return f"FEEDBACK:\nTool: {tool_name}\nSucces: {success}\nOutput:\n{output}"

    def _process_cycle(self, message: str):
        from src.core.default_commands import increment_message_count
        
        # Réinitialiser le flag d'interruption au début d'un nouveau cycle
        self._interrupted = False

        # Tester la connexion au premier message si pas encore fait
        if self._conn_ok is None:
            self._conn_ok = self.client.test_connection()

        if self._conn_ok is False:
            self.console.print("[error]Aucun provider connecte. Utilisez /provider pour en configurer un.[/error]")
            return

        # Envoi du prompt systeme au premier message (une seule fois par session)
        if not self._prompt_sent:
            self._prompt_sent = True
            from src.core.paths import prompt_system_path
            p_path = prompt_system_path()
            if p_path.exists():
                # Toujours demander l'autorisation avant d'envoyer le prompt système
                choix = self.console.input("[yellow]Envoyer le prompt systeme ? (y/n) [/yellow]").strip().lower()
                if choix == "y":
                    with open(p_path, "r", encoding="utf-8") as f:
                        self.client.send_message(f.read())
                else:
                    self.console.print("[dim]Prompt système non envoyé.[/dim]")

        increment_message_count()

        # Afficher le message de l'utilisateur en bulle
        self.composer.display_user_message(message)

        current_input = message
        current_role = "user"
        iteration = 0
        max_tool_iterations = 999
        last_tool_name = None
        last_response_hash = None
        start_time = time.time()

        while iteration < max_tool_iterations:
            # Vérifier si interruption demandée
            if self._interrupted:
                self._interrupted = False
                self.console.print("[yellow] Tâche interrompue par l'utilisateur.[/yellow]")
                break
                
            iteration += 1
            if self.debug:
                self.console.print(f"[debug]Iteration {iteration}/{max_tool_iterations}: Envoi (role={current_role})...[/debug]")

            # Thinking animation during LLM call
            anim = self.composer.display_thinking(
                "NEMESIS is thinking..." if iteration == 1 else "analyzing result..."
            )
            next(anim)  # start spinner
            try:
                try:
                    result = self.client.send_message(current_input, role=current_role)
                except TypeError:
                    result = self.client.send_message(current_input)
            finally:
                try:
                    anim.close()
                except Exception:
                    pass

            # Le spinner s'arrête automatiquement ici
            if not result['success']:
                self.console.print(f"[error]Erreur: {result.get('error', 'inconnu')}[/error]")
                break

            raw_response = result.get('response', '')
            parsed = self._parse_response(raw_response)
            if self.debug:
                self.console.print(f"[debug]Reponse recue ({len(raw_response)} chars), action={parsed['action'] is not None}[/debug]")

            # --- Duplicate response detection ---
            response_hash = hash(raw_response.strip())
            if response_hash == last_response_hash and iteration > 1:
                if parsed['text'] and not parsed['text'].startswith("FEEDBACK:"):
                    self.composer.display_ai_message(parsed['text'])
                break
            last_response_hash = response_hash

            # --- Display AI text ---
            display_text = parsed['text']
            if display_text and not display_text.startswith("FEEDBACK:"):
                self.composer.display_ai_message(display_text)

            # --- No action = end of cycle ---
            if not parsed['action']:
                break

            # --- Boucle outil supprimée ---
            if not parsed.get('action'):
                break

            act_type = parsed['action']['type']
            act_content = parsed['action']['content']
            last_tool_name = act_type

            # --- DEMANDE D'AUTORISATION AVANT EXECUTION ---
            if not self._ask_for_authorization(act_type, act_content):
                # Utilisateur a refusé
                self.console.print(f"[red] Exécution de l'outil '{act_type}' refusée.[/red]")
                # Envoyer un feedback de refus à l'IA
                current_input = f"FEEDBACK:\nTool: {act_type}\nSucces: false\nOutput:\n[EXECUTION REFUSEE PAR L'UTILISATEUR]"
                current_role = "tool_result"
                continue

            # --- Tool execution header ---
            self.composer.display_tool_start(act_type, act_content if isinstance(act_content, dict) else {})

            final_res = {}
            tool_call_count = 0
            accumulated_output = []  # Accumuler les lignes pour le feedback IA
            needs_input_handled = False
            
            # --- Execute tool ---
            for update in self.executor.execute_tool(act_type, act_content):
                # Vérifier si interruption demandée pendant l'exécution
                if self._interrupted:
                    self._interrupted = False
                    self.console.print("[yellow] Exécution de l'outil interrompue.[/yellow]")
                    final_res = {"success": False, "stdout": "", "error": "Interrompu par l'utilisateur"}
                    break
                    
                # Pour bash, gérer le besoin d'entrée utilisateur
                if act_type == "bash" and update.get('needs_input'):
                    # Stocker le contexte pour plus tard
                    input_context = update.get('input_context', '')
                    
                    # Afficher un message clair pour l'utilisateur
                    self.console.print()
                    if input_context and input_context != '[Commande attend une entrée...]':
                        self.console.print(f"[yellow]  La commande attend une entrée :[/yellow]")
                        # Afficher le contexte (dernières lignes) pour aider l'utilisateur
                        context_lines = input_context.strip().split('\n')
                        for context_line in context_lines[-3:]:  # Afficher les 3 dernières lignes max
                            if context_line.strip():
                                self.console.print(f"  [dim]{context_line}[/dim]")
                    else:
                        self.console.print("[yellow]  La commande attend une entrée utilisateur[/yellow]")
                    
                    try:
                        user_input = self.composer.prompt_input("[yellow]>>>[/yellow] ")
                        if user_input:
                            # Envoyer l'entrée au processus
                            if hasattr(self.executor, '_waiting_for_input') and self.executor._waiting_for_input:
                                try:
                                    import os
                                    if hasattr(self.executor, '_waiting_for_input_fd'):
                                        os.write(self.executor._waiting_for_input_fd, (user_input + "\n").encode('utf-8'))
                                    else:
                                        # Fallback au stdin standard
                                        self.executor._waiting_for_input.stdin.write(user_input + "\n")
                                        self.executor._waiting_for_input.stdin.flush()
                                    # Accumuler l'entrée pour le feedback
                                    accumulated_output.append(f"> {user_input}\n")
                                except Exception as e:
                                    accumulated_output.append(f"[ERROR] {e}\n")
                    except EOFError:
                        accumulated_output.append("[CANCELLED]\n")
                    
                    needs_input_handled = True
                    continue
                
                # Pour bash, accumuler la sortie dans accumulated_output
                if act_type == "bash" and 'stdout' in update:
                    accumulated_output.append(update['stdout'])
                
                # Stocker le résultat final
                if 'success' in update or (act_type != "bash" and update):
                    final_res = update
                    # Ajouter les lignes accumulées à stdout
                    if accumulated_output:
                        existing_stdout = final_res.get('stdout', '')
                        final_res['stdout'] = ''.join(accumulated_output) + (existing_stdout if existing_stdout else '')
                    # S'assurer que le feedback contient toujours la sortie complète
                    if 'stdout' not in final_res:
                        final_res['stdout'] = ''.join(accumulated_output) if accumulated_output else ''
                
                tool_call_count += 1
                
                # Pour les outils non-bash, on peut s'arrêter après le premier résultat
                # Pour bash, on continue jusqu'à la fin de l'itération
                if act_type != "bash" and final_res:
                    break

            # --- Result display ---
            if final_res:
                # Afficher directement le résultat pour tous les outils, y compris bash
                self.composer.display_tool_result(final_res, tool_name=act_type)
            else:
                self.console.print(Text("   Done", style="green"))

            current_input = self._format_feedback(parsed['action'], final_res)
            current_role = "tool_result"
            continue

        if iteration >= max_tool_iterations:
            self.console.print(f"[error]Limite de {max_tool_iterations} iterations d'outils atteinte. Arret du cycle.[/error]")

        elapsed = time.time() - start_time
        self.composer.display_task_summary(elapsed, tool_count=iteration - 1)

    def run(self):
        self.session_start = time.time()
        self.console.clear()

        self._load_config()

        try:
            self.client = create_provider(self.config)
        except Exception as e:
            self.console.print(f"[error]Erreur provider: {e}[/error]")
            self.console.print("[yellow]Passe au provider bridge par defaut (temporaire)...[/yellow]")
            # Fallback en memoire uniquement — ne pas ecraser la config sauvegardee
            fallback_config = {
                "provider": {"type": "bridge"},
                "bridge": {"host": "192.168.1.67", "port": 8080},
                "security": self.config.get("security", {"workspace": "./workspace"}),
            }
            self.client = create_provider(fallback_config)

        self.executor = create_executor_from_config(self.config, bridge=self.client)
        # Synchroniser le parseur avec les outils de l'executeur
        if hasattr(self.executor, "registry") and self.executor.registry:
            extra_tools = set(self.executor.registry._tools.keys())
            self.parser = ActionParser(extra_valid_tools=extra_tools)
        
        # Passer l'exécuteur au scheduler A2A pour les subagents
        from src.core.agent_manager import get_scheduler
        scheduler = get_scheduler()
        scheduler.set_executor(self.executor)
        
        # Recharger les agents avec l'exécuteur maintenant disponible
        # Les agents chargés depuis agents.json avant que l'exécuteur ne soit créé n'avaient pas d'exécuteur
        from src.core.default_commands import reload_agents_with_executor
        reload_agents_with_executor(self.executor)
        
        src.core.default_commands.set_active_app(self)

        self.console.clear()

        # Provider info for welcome
        provider_type = self.config['provider']['type']
        if provider_type in ("bridge", "nemapi_bridge"):
            host_info = f"{self.client.host}:{self.client.port}"
        else:
            host_info = self.client.model or provider_type

        # Modern welcome screen
        self.composer.display_welcome(provider=provider_type, target=host_info)

        # Ne pas tester la connexion au demarrage — le faire au premier message
        self._conn_ok = None

        try:
            while True:
                try:
                    user_input = self.composer.prompt_input()
                except KeyboardInterrupt:
                    self._handle_interrupt()
                    continue

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    parts = user_input[1:].split()
                    if not parts:
                        self._show_commands()
                        continue

                    cmd_name = parts[0]
                    cmd_args = parts[1:]
                    cmd = registry.get_command(cmd_name)
                    if cmd:
                        res = cmd.handler(cmd_args)
                        if isinstance(res, str) and res.startswith("PROMPT_INTERNAL:"):
                            self._process_cycle(res.replace("PROMPT_INTERNAL:", "").strip())
                else:
                    self._process_cycle(user_input)

        except KeyboardInterrupt:
            elapsed = time.time() - self.session_start
            mins, secs = divmod(int(elapsed), 60)
            self.console.print(f"\n[system]Session terminee — Duree totale : {mins:02d}:{secs:02d}[/system]")
            self.console.print("[system]Au revoir ![/system]")


if __name__ == "__main__":
    debug_mode = "--debug" in sys.argv
    app = NemesisApp(debug=debug_mode)
    app.run()