import os
import sys
import asyncio
import subprocess
import yaml
import io
import logging
import re
import time
from typing import Dict, Any, List, Optional

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler, 
    filters,
    CallbackQueryHandler
)

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Import des composants de Nemesis
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from bridge_client import BridgeClient
    from tools import ActionExecutor
except ImportError as e:
    print(f"Erreur d'importation : {e}")
    sys.exit(1)

class TelegramNemesisBot:
    def __init__(self, config_path="config.yaml"):
        self.config = self._load_config(config_path)
        self.token = self.config.get('telegram', {}).get('bot_token')
        self.allowed_id = self.config.get('telegram', {}).get('allowed_user_id')
        
        if not self.token or self.token == "VOTRE_TOKEN_ICI":
            print("Erreur : Le token Telegram n'est pas configuré dans config.yaml")
            sys.exit(1)

        # Mode interactif pour la connexion au bridge
        print("\n--- Configuration du Bridge Nemesis ---")
        default_host = self.config.get('bridge', {}).get('host', 'localhost')
        default_port = self.config.get('bridge', {}).get('port', 8080)
        
        host = input(f"Entrez l'IP du bridge [{default_host}]: ").strip() or default_host
        port_input = input(f"Entrez le port du bridge [{default_port}]: ").strip()
        port = int(port_input) if port_input else default_port
        
        init_prompt = input("Voulez-vous initialiser le prompt système ? (o/N): ").lower().strip() == 'o'
        
        print(f"\nConnexion au bridge sur {host}:{port}...")
        try:
            self.bridge = BridgeClient(host, port)
            self.executor = ActionExecutor()
            print("Connexion au bridge établie.")
        except Exception as e:
            print(f"Erreur de connexion au bridge : {e}")
            sys.exit(1)
        
        if init_prompt:
            self._initialize_system_prompt()

        # État pour gérer les actions en attente de confirmation
        self.pending_actions = {} 

    def _load_config(self, path):
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Erreur lors du chargement de la config : {e}")
            return {}

    def _initialize_system_prompt(self):
        print("Initialisation du prompt système...")
        try:
            prompt_file = "prompt_system.txt"
            if os.path.exists(prompt_file):
                with open(prompt_file, "r") as f:
                    system_prompt = f.read()
                print("Envoi du prompt au bridge...")
                result = self.bridge.send_message(f"SYSTEM_PROMPT: {system_prompt}")
                if result.get('success'):
                    print("Prompt système initialisé avec succès.")
                else:
                    print(f"Erreur lors de l'initialisation du prompt : {result.get('error')}")
            else:
                print(f"Avertissement : Fichier {prompt_file} introuvable.")
        except Exception as e:
            print(f"Erreur lors de l'initialisation du prompt : {e}")

    def is_authorized(self, user_id):
        if not self.allowed_id or self.allowed_id == 0:
            return True
        return user_id == self.allowed_id

    def _parse_response(self, resp: str) -> Dict:
        parsed = {'text': resp, 'action': None}
        if resp.startswith("FEEDBACK:"):
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
        return parsed

    def _format_feedback(self, action: Dict, res: Dict) -> str:
        output = res.get('stdout', res.get('content', ''))
        if len(output) > 3500:
            output = output[:3500] + "\n\n[AVERTISSEMENT : Output tronqué pour Telegram]"
        return f"FEEDBACK:\nAction: {action['type']}\nSuccès: {res.get('success', False)}\nOutput:\n{output}"

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not self.is_authorized(user.id):
            await update.message.reply_text("Accès non autorisé.")
            return
        
        await update.message.reply_text(
            f"Bienvenue {user.first_name} sur Nemesis Remote !\n\n"
            "Commandes disponibles :\n"
            "/ask <message> - Lancer la boucle de réflexion/action\n"
            "/bash <commande> - Exécuter une commande système directe\n"
            "/status - État du système\n"
            "/help - Aide"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.start(update, context)

    async def ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update.effective_user.id):
            return

        user_input = " ".join(context.args)
        if not user_input:
            await update.message.reply_text("Usage: /ask <votre message>")
            return

        await self._process_nemesis_loop(update, context, user_input)

    async def _process_nemesis_loop(self, update: Update, context: ContextTypes.DEFAULT_TYPE, current_input: str):
        chat_id = update.effective_chat.id
        thinking_msg = await update.effective_message.reply_text("🤔 *Nemesis réfléchit...*", parse_mode='Markdown')

        try:
            result = self.bridge.send_message(current_input)
            try: await thinking_msg.delete()
            except: pass
            
            if not result.get('success'):
                await update.effective_message.reply_text(f"❌ **Erreur Bridge** : {result.get('error')}")
                return

            response_text = result.get('response', '')
            parsed = self._parse_response(response_text)
            
            if parsed['text']:
                try:
                    await update.effective_message.reply_text(parsed['text'], parse_mode='Markdown')
                except:
                    await update.effective_message.reply_text(parsed['text'])

            if parsed['action']:
                act_type = parsed['action']['type']
                act_content = parsed['action']['content']
                
                keyboard = [[InlineKeyboardButton("✅ Autoriser", callback_data="action_allow"),
                             InlineKeyboardButton("❌ Refuser", callback_data="action_deny")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                preview = act_content[:400] + ("..." if len(act_content) > 400 else "")
                
                action_msg = (f"🛠 **DEMANDE D'ACTION**\nType: `{act_type.upper()}`\n\n"
                            f"Contenu:\n```\n{preview}\n```\n"
                            f"Autorisez-vous l'exécution ?")
                
                self.pending_actions[chat_id] = {'action': parsed['action'], 'original_input': current_input}
                await update.effective_message.reply_text(action_msg, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            await update.effective_message.reply_text(f"⚠️ Erreur : {e}")

    async def on_button_click(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        chat_id = query.message.chat_id
        if not self.is_authorized(query.from_user.id):
            await query.answer("Accès non autorisé.", show_alert=True)
            return

        await query.answer()
        if chat_id not in self.pending_actions:
            await query.edit_message_text("❌ Action expirée.")
            return

        state = self.pending_actions.pop(chat_id)
        action = state['action']

        if query.data == "action_allow":
            status_msg = await query.edit_message_text(f"⏳ Exécution de `{action['type'].upper()}`...")
            
            final_res = {}
            try:
                # Exécution synchrone simple (mais dans un thread pour ne pas figer le bot)
                def run_executor():
                    res = {}
                    for info in self.executor.execute_action(action['type'], action['content']):
                        res = info
                    return res
                
                final_res = await asyncio.to_thread(run_executor)
                
                status = "✅" if final_res.get('success') else "❌"
                await status_msg.edit_text(f"{status} `{action['type'].upper()}` terminé.")
                
                feedback = self._format_feedback(action, final_res)
                await self._process_nemesis_loop(update, context, feedback)
                
            except Exception as e:
                await query.message.reply_text(f"⚠️ Erreur d'exécution : {e}")
        else:
            await query.edit_message_text(f"🚫 Action `{action['type'].upper()}` refusée.")

    async def bash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update.effective_user.id): return
        command = " ".join(context.args)
        if not command:
            await update.message.reply_text("Usage: /bash <commande>")
            return
        
        await update.message.reply_text(f"🐚 Exécution : `{command}`...")
        
        try:
            def run_bash():
                res = {}
                for info in self.executor.execute_action("bash", f"synchrone | {command}"):
                    res = info
                return res

            result = await asyncio.to_thread(run_bash)
            response = ""
            if result.get('stdout'):
                response += f"**SORTIE:**\n```\n{result['stdout']}\n```"
            
            if not response:
                response = "✅ Commande exécutée."
                
            await update.message.reply_text(response[:4000], parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"Erreur : {e}")

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_authorized(update.effective_user.id): return
        await update.message.reply_text("Nemesis Remote is ONLINE 🟢")

    def run(self):
        from telegram.request import HTTPXRequest
        request = HTTPXRequest(connect_timeout=3600.0, read_timeout=3600.0, write_timeout=3600.0, pool_timeout=3600.0)
        app = ApplicationBuilder().token(self.token).request(request).build()
        
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("bash", self.bash))
        app.add_handler(CommandHandler("ask", self.ask))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CallbackQueryHandler(self.on_button_click))
        
        print("\nBot Telegram stable démarré...")
        retry_delay = 5
        while True:
            try:
                app.run_polling(drop_pending_updates=True)
                break
            except Exception as e:
                print(f"\n❌ Erreur réseau : {e}. Reconnexion dans {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300)

if __name__ == "__main__":
    bot = TelegramNemesisBot()
    bot.run()
