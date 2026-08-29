#!/usr/bin/env python3
"""Bot Telegram pour NEMESIS CLI v3.0 - Agent IA moderne avec gestion complete des providers et conversations.

Structure de configuration (identique au CLI NEMESIS) :
- provider.type: type de provider (bridge, nemapi_bridge, fireworks, groq, etc.)
- provider.api_key: cle API pour les providers tiers
- provider.model: modele selectionne
- provider.endpoint: endpoint pour whisperer
- bridge: {host, port} pour BridgeProvider
- nemapi_bridge: {host, port} pour NemapiBridgeProvider
- security.workspace: repertoire de travail

Les configurations du bot sont stockees dans telegram_bot_configs/{chat_id}.yaml
Separation totale des configurations CLI et bot.
"""

import os
import sys
import json
import logging
import asyncio
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Ajouter le repertoire parent au path pour les imports
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))

from telegram import Update, Message, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackContext,
    CallbackQueryHandler,
)

# Import des modules NEMESIS
from src.core.agent_tools import create_registry
from providers import create_provider, list_providers
from tools import ActionExecutor
from tools_schema import get_tool_handler_method, validate_tool_call
from action_parser import ActionParser

# Configuration du logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTES
# =============================================================================

PROVIDER_LABELS = {
    "bridge": "Bridge (Android/Local)",
    "nemapi_bridge": "NEMAPI Bridge (Firefox/OpenAI)",
    "groq": "Groq",
    "nvidia_nim": "Nvidia NIM",
    "nvidia": "Nvidia NIM",
    "fireworks": "Fireworks AI",
    "cohere": "Cohere",
    "xai": "xAI Grok",
    "openrouter": "OpenRouter",
    "ollama": "Ollama local",
    "whisperer": "Whisperer (llm-whisperer local)",
}

# Providers qui gerent leur contexte cote serveur
SERVER_MANAGED_PROVIDERS = ["bridge", "nemapi_bridge"]

# Etats de conversation
AWAITING_PROVIDER_CONFIG = 1
AWAITING_MODEL_SELECTION = 2
AWAITING_CONFIRMATION = 3
AWAITING_BRIDGE_HOST = 4
AWAITING_NEMAPI_HOST = 5
AWAITING_WHISPERER_CONFIG = 6

# Repertoire de stockage des configurations du bot
BOT_CONFIG_DIR = Path(__file__).parent / "telegram_bot_configs"


# =============================================================================
# GESTION DE LA CONFIGURATION PERSISTANTE
# =============================================================================

def ensure_config_dir():
    """Assure que le repertoire de configuration existe."""
    BOT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_chat_config_path(chat_id: int) -> Path:
    """Retourne le chemin du fichier de configuration pour un chat."""
    return BOT_CONFIG_DIR / f"{chat_id}.yaml"


def load_chat_config(chat_id: int) -> Dict[str, Any]:
    """Charge la configuration pour un chat depuis le disque."""
    ensure_config_dir()
    config_path = get_chat_config_path(chat_id)
    
    # Configuration par defaut (identique au CLI)
    default_config = {
        "provider": {"type": "bridge"},
        "bridge": {"host": "192.168.1.67", "port": 8080},
        "nemapi_bridge": {"host": "127.0.0.1", "port": 8080},
        "security": {"workspace": "./workspace"},
    }
    
    if not config_path.exists():
        return default_config
    
    try:
        import yaml
        with open(config_path, 'r') as f:
            loaded = yaml.safe_load(f)
            if not loaded:
                return default_config
            # Fusionner avec la config par defaut pour les champs manquants
            for key, value in default_config.items():
                if key not in loaded:
                    loaded[key] = value
                elif isinstance(value, dict) and key in default_config:
                    for subkey, subvalue in default_config[key].items():
                        if subkey not in loaded.get(key, {}):
                            loaded.setdefault(key, {})[subkey] = subvalue
            return loaded
    except Exception as e:
        logger.error(f"Erreur chargement config pour chat {chat_id}: {e}")
        return default_config


def save_chat_config(chat_id: int, config: Dict[str, Any]) -> bool:
    """Sauvegarde la configuration pour un chat sur le disque."""
    ensure_config_dir()
    config_path = get_chat_config_path(chat_id)
    
    try:
        import yaml
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde config pour chat {chat_id}: {e}")
        return False


# =============================================================================
# CLASSE PRINCIPALE DU BOT
# =============================================================================

class NemesisTelegramBot:
    """Bot Telegram qui integre l'agent NEMESIS v3.0."""

    def __init__(self, token: str, workspace: str = "./workspace"):
        """Initialise le bot Telegram NEMESIS."""
        self.token = token
        self.workspace = workspace
        self.bot: Optional[Bot] = None
        self.app: Optional[Application] = None
        self.registry = None
        self.executor = ActionExecutor(workspace=self.workspace)
        self.parser = ActionParser()
        
        # Etats de conversation par chat
        self.chat_states: Dict[int, int] = {}
        
        # Donnees temporaires
        self.pending_config: Dict[int, Dict[str, Any]] = {}
        self.pending_actions: Dict[int, Dict[str, Any]] = {}
        
        # Suivi du prompt système envoyé par chat
        self.prompt_system_sent: Dict[int, bool] = {}
        
        # Initialiser NEMESIS
        self._init_nemesis()
        
        # S'assurer que le repertoire de config existe
        ensure_config_dir()

    def _init_nemesis(self):
        """Initialise les composants NEMESIS."""
        self.registry = create_registry(self.workspace)
        logger.info("NEMESIS agent initialized with %d tools", len(self.registry._tools))

    def _get_chat_config(self, chat_id: int) -> Dict[str, Any]:
        """Charge la configuration pour un chat."""
        return load_chat_config(chat_id)

    def _save_chat_config(self, chat_id: int, config: Dict[str, Any]) -> bool:
        """Sauvegarde la configuration pour un chat."""
        return save_chat_config(chat_id, config)

    def _get_provider(self, chat_id: int) -> Any:
        """Cree et retourne le provider pour un chat."""
        config = self._get_chat_config(chat_id)
        try:
            return create_provider(config)
        except Exception as e:
            logger.error(f"Erreur creation provider pour chat {chat_id}: {e}")
            return None

    def _needs_provider_config(self, chat_id: int) -> bool:
        """Verifie si le provider a besoin d'etre configure."""
        config = self._get_chat_config(chat_id)
        provider_type = config.get("provider", {}).get("type", "bridge")
        
        if provider_type in ["bridge", "nemapi_bridge"]:
            return False
        if provider_type == "whisperer":
            return not config.get("provider", {}).get("endpoint")
        
        # Pour Fireworks, Groq, OpenRouter, etc. - verifier api_key
        api_key = config.get("provider", {}).get("api_key", "")
        return not api_key

    def _get_default_model_for_provider(self, provider_type: str) -> str:
        """Retourne le modele par defaut pour un provider donne."""
        from providers.openai_compatible import (
            GroqProvider,
            NvidiaNimProvider,
            XaiProvider,
            OpenRouterProvider,
            OllamaProvider,
            FireworksProvider,
            CohereProvider,
        )
        
        provider_defaults = {
            "groq": GroqProvider.DEFAULT_MODEL,
            "nvidia_nim": NvidiaNimProvider.DEFAULT_MODEL,
            "nvidia": NvidiaNimProvider.DEFAULT_MODEL,
            "xai": XaiProvider.DEFAULT_MODEL,
            "openrouter": OpenRouterProvider.DEFAULT_MODEL,
            "ollama": OllamaProvider.DEFAULT_MODEL,
            "fireworks": FireworksProvider.DEFAULT_MODEL,
            "cohere": CohereProvider.DEFAULT_MODEL,
        }
        return provider_defaults.get(provider_type, "")
    
    def _needs_model_selection(self, chat_id: int) -> bool:
        """Verifie si le modele doit etre selectionne."""
        config = self._get_chat_config(chat_id)
        provider_type = config.get("provider", {}).get("type", "bridge")
        
        if provider_type in ["bridge", "nemapi_bridge"]:
            return False
        
        model = config.get("provider", {}).get("model", "")
        
        # Pour les providers tiers (Fireworks, Groq, etc.), on DOIT toujours selectionner un modele
        # Pas de modele par defaut automatique - l'utilisateur doit choisir
        if provider_type in ["fireworks", "groq", "openrouter", "xai", "cohere", "ollama", "nvidia", "nvidia_nim"]:
            return not model
        
        return not model


    # =============================================================================
    # COMMANDES SLASH
    # =============================================================================

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /start."""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        welcome_message = (
            "<b>🚀 Bienvenue sur NEMESIS Telegram Bot v3.0</b>\n\n"
            f"Bonjour {user.first_name}!\n\n"
            "Je suis NEMESIS, votre agent IA autonome de codage et d'administration systeme.\n\n"
            "<b>📋 Configuration requise avant de commencer :</b>\n"
            "1. Configurez votre provider LLM avec /provider\n"
            "2. Selectionnez un modele avec /model (si necessaire)\n"
            "3. Demarrez une nouvelle conversation avec /new\n\n"
            "<b>💡 Commandes principales :</b>\n"
            "/start - Demarrer le bot\n"
            "/help - Aide\n"
            "/provider - Configurer le provider LLM\n"
            "/model - Changer le modele\n"
            "/new - Nouvelle conversation\n"
            "/clear - Effacer la conversation\n"
            "/tools - Liste des outils disponibles\n"
            "/config - Afficher la configuration actuelle\n"
            "/history - Gerer l'historique\n\n"
            "<b>🔧 Outils integrés :</b>\n"
            "read_file, write_file, bash, grep, list_dir, web_search, web_fetch\n"
            "mcp_list, mcp_tools_list, mcp_call, et bien plus!\n\n"
            "<b>ℹ️ Note :</b> Les providers Bridge et NEMAPI Bridge gerent leur contexte cote serveur.\n"
            "Pour les autres providers (Fireworks, Groq, etc.), utilisez /new pour une nouvelle conversation."
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_message,
        )
        
        if not self._needs_provider_config(chat_id):
            await context.bot.send_message(
                chat_id=chat_id,
                text="<b>✅ Votre provider est deja configure.</b> Utilisez /new pour commencer une conversation.",
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /help."""
        chat_id = update.effective_chat.id
        
        help_text = (
            "<b>📖 Aide NEMESIS Telegram Bot v3.0</b>\n\n"
            "<b>🎯 Configuration :</b>\n"
            "/provider - Configurer le provider LLM\n"
            "/model - Changer le modele\n"
            "/config - Afficher la configuration\n\n"
            "<b>💬 Conversation :</b>\n"
            "/new - Nouvelle conversation\n"
            "/clear - Effacer conversation\n"
            "/history - Gerer historique\n\n"
            "<b>📊 Informations :</b>\n"
            "/start - Menu de demarrage\n"
            "/help - Aide\n"
            "/tools - Liste des outils\n"
            "/about - A propos\n\n"
            "<b>⚙️ Outils :</b>\n"
            "Envoyez: /read: fichier\n"
            "       /bash: commande\n"
            "       /grep: pattern\n"
            "       /search: requete\n"
            "       /fetch: url\n\n"
            "<b>🔒 Securite :</b>\n"
            "Les actions sensibles demandent confirmation."
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=help_text,
        )

    async def provider_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /provider."""
        chat_id = update.effective_chat.id
        
        available_providers = list_providers()
        
        keyboard = []
        for provider_type in available_providers:
            label = PROVIDER_LABELS.get(provider_type, provider_type)
            keyboard.append([InlineKeyboardButton(label, callback_data=f"provider_{provider_type}")])
        
        keyboard.append([InlineKeyboardButton("Annuler", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="<b>🔧 Selectionnez un provider LLM :</b>\n\n"
                 "Bridge et NEMAPI Bridge gerent leur contexte serveur.\n"
                 "Pour les autres, utilisez /new pour une nouvelle conversation.",
            reply_markup=reply_markup,
        )
        
        self.chat_states[chat_id] = AWAITING_PROVIDER_CONFIG

    async def model_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /model."""
        chat_id = update.effective_chat.id
        
        config = self._get_chat_config(chat_id)
        provider_type = config.get("provider", {}).get("type", "bridge")
        
        if provider_type in ["bridge", "nemapi_bridge"]:
            await context.bot.send_message(
                chat_id=chat_id,
                text="ℹ️ Bridge et NEMAPI Bridge utilisent les modeles configures cote serveur.",
            )
            return
        
        # Vérifier qu'un provider est configuré avec une clé API
        api_key = config.get("provider", {}).get("api_key", "")
        if not api_key and provider_type not in ["whisperer"]:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Configurez d'abord votre clé API avec /provider",
            )
            return
        
        # Vérifier le modele actuel
        current_model = config.get("provider", {}).get("model", "")
        
        provider = self._get_provider(chat_id)
        if not provider:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Erreur: Impossible de creer le provider. Verifiez votre configuration.",
            )
            return
        
        try:
            models = provider.list_models()
        except Exception as e:
            logger.error(f"Erreur list_models pour {provider_type}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Impossible de lister les modeles. Verifiez votre clé API avec /config\n\n"
                     f"Erreur: {str(e)[:200]}",
            )
            return
        
        # Filtrer les doublons
        seen_models = set()
        unique_models = []
        for model in models:
            model_id = model.get("id", "")
            if model_id and model_id not in seen_models:
                seen_models.add(model_id)
                unique_models.append(model)
        
        # Limiter à 15 modèles
        models_to_show = unique_models[:15]
        
        if not models_to_show:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Aucun modele disponible. Verifiez votre clé API.",
            )
            return
        
        keyboard = []
        for model in models_to_show:
            model_id = model.get("id", "")
            owned_by = model.get("owned_by", "")
            display_name = model_id
            if owned_by and owned_by != "unknown":
                display_name = f"{model_id} ({owned_by})"
            if model_id:
                keyboard.append([InlineKeyboardButton(display_name, callback_data=f"model_{model_id}")])
        
        keyboard.append([InlineKeyboardButton("Annuler", callback_data="cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Afficher le modele actuel si deja selectionne
        if current_model:
            text = f"<b>🎯 Modele actuel: {current_model}</b>\n\nSelectionnez un autre modele pour {provider_type} :"
        else:
            text = f"<b>🎯 Selectionnez un modele pour {provider_type} :</b>"
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
        )
        
        self.chat_states[chat_id] = AWAITING_MODEL_SELECTION

    async def new_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /new."""
        chat_id = update.effective_chat.id
        
        if self._needs_provider_config(chat_id):
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Configurez d'abord un provider avec /provider",
            )
            return
        
        if self._needs_model_selection(chat_id):
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Selectionnez d'abord un modele avec /model",
            )
            return
        
        provider_type = self._get_chat_config(chat_id).get("provider", {}).get("type", "bridge")
        
        if provider_type not in SERVER_MANAGED_PROVIDERS:
            provider = self._get_provider(chat_id)
            if provider:
                provider.reset_conversation()
        
        # Réinitialiser le flag de prompt système pour une nouvelle conversation
        self.prompt_system_sent[chat_id] = False
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="<b>🆕 Nouvelle conversation demarree!</b>\n\n"
                 "Votre conversation est prete. Envoyez un message pour commencer.",
        )

    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /clear."""
        chat_id = update.effective_chat.id
        
        provider = self._get_provider(chat_id)
        if provider:
            provider.reset_conversation()
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="<b>🧹 Conversation effacee!</b>\n\n"
                 "La conversation a ete reinitialisee.",
        )

    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /config."""
        chat_id = update.effective_chat.id
        
        config = self._get_chat_config(chat_id)
        provider_type = config.get("provider", {}).get("type", "bridge")
        
        config_text = (
            "<b>📋 Configuration actuelle</b>\n\n"
            f"Provider: {PROVIDER_LABELS.get(provider_type, provider_type)}\n"
        )
        
        if provider_type not in ["bridge", "nemapi_bridge"]:
            provider_config = config.get("provider", {})
            model = provider_config.get("model", "Non selectionne")
            config_text += f"Modele: {model}\n"
            api_key = provider_config.get("api_key", "")
            if api_key:
                config_text += f"Cle API: {'*' * len(api_key)}\n"
            if provider_type == "whisperer":
                endpoint = provider_config.get("endpoint", "")
                if endpoint:
                    config_text += f"Endpoint: {endpoint}\n"
        
        if provider_type == "bridge":
            bridge_config = config.get("bridge", {})
            config_text += f"Host: {bridge_config.get('host', 'N/A')}\n"
            config_text += f"Port: {bridge_config.get('port', 'N/A')}\n"
        
        if provider_type == "nemapi_bridge":
            nb_config = config.get("nemapi_bridge", {})
            config_text += f"Host: {nb_config.get('host', 'N/A')}\n"
            config_text += f"Port: {nb_config.get('port', 'N/A')}\n"
        
        config_text += f"\nWorkspace: {config.get('security', {}).get('workspace', self.workspace)}"
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=config_text,
        )

    async def tools_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /tools."""
        chat_id = update.effective_chat.id
        
        if not self.registry:
            self._init_nemesis()
        
        tools_list = list(self.registry._tools.keys())
        lines = ["🔧 *Outils NEMESIS disponibles:*", ""]
        
        for i, tool in enumerate(tools_list, 1):
            tool_def = self.registry._tools[tool].definition
            description = (tool_def.description or "").split("\n")[0][:100]
            lines.append(f"{i}. `{tool}` - {description}")
        
        lines.append("")
        lines.append("💡 Utilisation:")
        lines.append("Envoyez: /read: fichier.txt")
        lines.append("Ou: {\"tool\": \"read_file\", \"parameters\": {\"path\": \"fichier.txt\"}}")
        
        for i in range(0, len(lines), 40):
            await context.bot.send_message(
                chat_id=chat_id,
                text='\n'.join(lines[i:i+40])
            )

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /about."""
        chat_id = update.effective_chat.id
        
        about_text = (
            "ℹ️ *A propos de NEMESIS Telegram Bot*\n\n"
            "NEMESIS CLI v3.0 - Agent IA autonome\n\n"
            "*Fonctionnalites :*\n"
            "- Execution de commandes systeme\n"
            "- Lecture/Ecriture de fichiers\n"
            "- Recherche web\n"
            "- Utilisation d'outils MCP\n"
            "- Support multi-providers\n"
            "- Gestion des conversations\n\n"
            "*Providers:*\n"
            ", ".join([f"{label}" for label in PROVIDER_LABELS.values()])
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=about_text,
        )

    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere la commande /history."""
        chat_id = update.effective_chat.id
        
        keyboard = [
            [InlineKeyboardButton("Effacer conversation", callback_data="history_clear")],
            [InlineKeyboardButton("Annuler", callback_data="cancel")],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="📜 *Gestion de l'historique* :\n\n"
                 "Choisissez une action.",
            reply_markup=reply_markup,
        )


    # =============================================================================
    # GESTION DES MESSAGES
    # =============================================================================

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere les messages texte."""
        chat_id = update.effective_chat.id
        message_text = update.message.text
        
        if not message_text:
            return
        
        config = self._get_chat_config(chat_id)
        
        # Gestion des etats de configuration
        if chat_id in self.chat_states:
            state = self.chat_states[chat_id]
            
            if state == AWAITING_BRIDGE_HOST:
                if ":" in message_text:
                    parts = message_text.split(":", 1)
                    host = parts[0].strip()
                    try:
                        port = int(parts[1].strip())
                        config["bridge"] = {"host": host, "port": port}
                        config["provider"]["type"] = "bridge"
                        self._save_chat_config(chat_id, config)
                        
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"✅ Bridge configure: {host}:{port}"
                        )
                        self.chat_states.pop(chat_id, None)
                        return
                    except ValueError:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="❌ Port invalide. Format: host:port (ex: 192.168.1.67:8080)"
                        )
                        return
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="❌ Format invalide. Utilisez: host:port"
                    )
                    return
            
            elif state == AWAITING_NEMAPI_HOST:
                if ":" in message_text:
                    parts = message_text.split(":", 1)
                    host = parts[0].strip()
                    try:
                        port = int(parts[1].strip())
                        config["nemapi_bridge"] = {"host": host, "port": port}
                        config["provider"]["type"] = "nemapi_bridge"
                        self._save_chat_config(chat_id, config)
                        
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"✅ NEMAPI Bridge configure: {host}:{port}"
                        )
                        self.chat_states.pop(chat_id, None)
                        return
                    except ValueError:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="❌ Port invalide. Format: host:port (ex: 127.0.0.1:8080)"
                        )
                        return
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="❌ Format invalide. Utilisez: host:port"
                    )
                    return
            
            elif state == AWAITING_WHISPERER_CONFIG:
                if "," in message_text:
                    parts = message_text.split(",", 1)
                    endpoint = parts[0].strip()
                    token = parts[1].strip()
                    config["provider"]["endpoint"] = endpoint
                    config["provider"]["api_key"] = token
                    config["provider"]["type"] = "whisperer"
                    self._save_chat_config(chat_id, config)
                    
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="✅ Whisperer configure"
                    )
                    self.chat_states.pop(chat_id, None)
                    return
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="❌ Format invalide. Utilisez: endpoint,token"
                    )
                    return
            
            elif state == AWAITING_PROVIDER_CONFIG:
                # Pour Fireworks, Groq, OpenRouter, etc. - on attend la cle API
                provider_type = config.get("provider", {}).get("type", "bridge")
                if provider_type not in ["bridge", "nemapi_bridge", "whisperer"]:
                    # Sauvegarder la cle API
                    config["provider"]["api_key"] = message_text.strip()
                    self._save_chat_config(chat_id, config)
                    
                    # TOUJOURS lister les modeles pour forcer la selection - pas de modele par defaut automatique
                    try:
                        provider = self._get_provider(chat_id)
                        if provider:
                            models = provider.list_models()
                            if models and len(models) > 0:
                                # Filtrer les doublons
                                seen = set()
                                unique = []
                                for m in models:
                                    mid = m.get("id", "")
                                    if mid and mid not in seen:
                                        seen.add(mid)
                                        unique.append(m)
                                
                                models_to_show = unique[:15]
                                
                                if models_to_show:
                                    keyboard = []
                                    for model in models_to_show:
                                        model_id = model.get("id", "")
                                        owned_by = model.get("owned_by", "")
                                        display_name = model_id
                                        if owned_by and owned_by != "unknown":
                                            display_name = f"{model_id} ({owned_by})"
                                        if model_id:
                                            keyboard.append([InlineKeyboardButton(display_name, callback_data=f"model_{model_id}")])
                                    
                                    keyboard.append([InlineKeyboardButton("Annuler", callback_data="cancel")])
                                    reply_markup = InlineKeyboardMarkup(keyboard)
                                    
                                    await context.bot.send_message(
                                        chat_id=chat_id,
                                        text=f"✅ Cle API registre pour {PROVIDER_LABELS.get(provider_type, provider_type)}\n\n"
                                             f"<b>🎯 Selectionnez un modele ({len(models)} disponibles) :</b>",
                                        reply_markup=reply_markup,
                                    )
                                    self.chat_states[chat_id] = AWAITING_MODEL_SELECTION
                                    return
                                else:
                                    await context.bot.send_message(
                                        chat_id=chat_id,
                                        text=f"❌ Aucuns modeles trouves. Verifiez votre cle API."
                                    )
                                    self.chat_states.pop(chat_id, None)
                                    return
                            else:
                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"❌ Impossible de recuperer les modeles. Verifiez votre cle API."
                                )
                                self.chat_states.pop(chat_id, None)
                                return
                        else:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=f"⚠️ Erreur de creation du provider. Verifiez votre cle API avec /config"
                            )
                            self.chat_states.pop(chat_id, None)
                            return
                    except Exception as e:
                        logger.error(f"Erreur list_models pour {provider_type}: {e}")
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"❌ Erreur lors de la recuperation des modeles. Verifiez votre cle API.\n"
                                 f"Erreur: {str(e)[:150]}"
                        )
                        self.chat_states.pop(chat_id, None)
                        return
        
        # Verifier si c'est une commande directe
        if message_text.startswith('/'):
            command = message_text[1:].split(' ')[0].split('@')[0]
            
            if command in ['start', 'help', 'provider', 'model', 'new', 'clear', 'config', 'tools', 'history', 'about']:
                return
            
            # Vérifier si c'est un outil direct
            tool_result = await self._handle_message_with_tools(message_text, chat_id, context)
            if tool_result:
                if self._is_sensitive_tool(message_text):
                    await self._ask_for_confirmation(update, context, message_text)
                else:
                    await context.bot.send_message(chat_id=chat_id, text=tool_result)
                return
        
        # Vérifier si le provider est configuré
        if self._needs_provider_config(chat_id):
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Provider non configure\n\n"
                     "Utilisez /provider pour configurer.",
            )
            return
        
        # Vérifier si le modele est selectionne
        if self._needs_model_selection(chat_id):
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Modele non selectionne\n\n"
                     "Utilisez /model pour selectionner un modele.",
            )
            return
        
        # Verifier si c'est un appel d'outil direct
        tool_result = await self._handle_message_with_tools(message_text, chat_id, context)
        if tool_result:
            if self._is_sensitive_tool(message_text):
                await self._ask_for_confirmation(update, context, message_text)
            else:
                await context.bot.send_message(chat_id=chat_id, text=tool_result)
            return
        
        # Traiter comme une requete pour l'IA
        await self._process_ai_request(update, context, message_text, chat_id)


    # =============================================================================
    # OUTILS
    # =============================================================================

    async def _handle_message_with_tools(self, message: str, chat_id: int, 
                                        context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
        """Traite un message qui peut contenir des appels d'outils."""
        message_stripped = message.strip()
        
        # Outils directs avec prefixe
        tool_prefixes = {
            'bash:': ('bash', lambda m: {'command': m[5:].strip()}),
            'read:': ('read_file', lambda m: {'path': m[5:].strip()}),
            'write:': ('write_file', lambda m: self._parse_write(m)),
            'grep:': ('grep', lambda m: {'pattern': m[5:].strip()}),
            'list:': ('list_dir', lambda m: {'path': m[5:].strip() or None}),
            'search:': ('web_search', lambda m: {'query': m[7:].strip()}),
            'fetch:': ('web_fetch', lambda m: self._parse_fetch(m)),
        }
        
        for prefix, (tool_name, parser) in tool_prefixes.items():
            if message_stripped.lower().startswith(prefix):
                params = parser(message_stripped)
                result = await self._execute_tool(tool_name, params, chat_id, context)
                return self._format_tool_result_for_display(result)
        
        # JSON tool call
        if message_stripped.startswith('{') and message_stripped.endswith('}'):
            try:
                tool_call = json.loads(message_stripped)
                if 'tool' in tool_call and 'parameters' in tool_call:
                    result = await self._execute_tool(
                        tool_call['tool'],
                        tool_call['parameters'],
                        chat_id,
                        context
                    )
                    return self._format_tool_result_for_display(result)
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _parse_write(self, message: str) -> Dict[str, Any]:
        """Parse un message write:"""
        parts = message[6:].strip().split('|', 1)
        if len(parts) >= 2:
            return {'file_path': parts[0].strip(), 'content': parts[1].strip()}
        return {'file_path': '', 'content': ''}
    
    def _parse_fetch(self, message: str) -> Dict[str, Any]:
        """Parse un message fetch:"""
        parts = message[6:].strip().split('|', 1)
        url = parts[0].strip()
        fmt = parts[1].strip() if len(parts) > 1 else 'markdown'
        return {'url': url, 'format': fmt}

    def _is_sensitive_tool(self, message: str) -> bool:
        """Verifie si le message contient un outil sensible."""
        sensitive_tools = ['write_file', 'write:', 'bash:', 'delete_file', 'edit']
        for tool in sensitive_tools:
            if message.startswith(tool) or tool in message.lower():
                return True
        return False

    async def _ask_for_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
        """Demande confirmation."""
        chat_id = update.effective_chat.id
        
        self.pending_config[chat_id] = {"message": message, "timestamp": time.time()}
        
        keyboard = [
            [InlineKeyboardButton("Confirmer", callback_data="confirm_yes")],
            [InlineKeyboardButton("Annuler", callback_data="confirm_no")],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ *Confirmation requise*\n\n"
                 f"Action sensible:\n\n```\n{message}\n```\n\n"
                 f"Executer?",
            reply_markup=reply_markup,
        )

    async def _execute_tool(self, tool_name: str, parameters: Dict[str, Any],
                          chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
        """Execute un outil et retourne un dict avec success/content/error."""
        try:
            if not self.registry:
                self._init_nemesis()

            if tool_name not in self.registry._tools:
                alt_names = {
                    'read': 'read_file',
                    'write': 'write_file',
                    'append': 'append_file',
                    'replace': 'edit',
                }
                tool_name = alt_names.get(tool_name, tool_name)

            if tool_name not in self.registry._tools:
                available_tools = list(self.registry._tools.keys())
                return {"success": False, "error": f"Outil inconnu: {tool_name}"}

            parameters = self._normalize_parameters(tool_name, parameters)
            tool_reg = self.registry._tools[tool_name]
            result = tool_reg.handler(**parameters)
            
            # Formater le résultat
            formatted = self._format_tool_result(result)
            
            # Déterminer le succès
            if isinstance(result, dict):
                success = result.get('success', True)
                error = result.get('error', None)
                content = result.get('content', result.get('output', formatted))
            else:
                success = True
                error = None
                content = formatted
            
            return {
                "success": success,
                "content": content,
                "error": error,
                "output": content  # Pour compatibilité
            }
            
        except Exception as e:
            logger.error(f"Erreur outil {tool_name}: {e}")
            return {"success": False, "error": str(e), "content": "", "output": ""}

    async def _process_ai_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  message: str, chat_id: int):
        """Traite une requete pour l'IA avec le workflow NEMESIS complet."""
        config = self._get_chat_config(chat_id)
        provider_type = config.get("provider", {}).get("type", "bridge")
        model = config.get("provider", {}).get("model", "")
        
        provider = self._get_provider(chat_id)
        if not provider:
            await context.bot.send_message(chat_id=chat_id, text="❌ Erreur: Provider non disponible")
            return
        
        # Envoyer le prompt système si ce n'est pas déjà fait
        # (sauf pour les providers qui gèrent leur contexte serveur)
        if (not self.prompt_system_sent.get(chat_id, False) and 
            provider_type not in SERVER_MANAGED_PROVIDERS):
            await self._send_system_prompt(chat_id)
        
        # Afficher le message "NEMESIS réfléchit..."
        try:
            thinking_msg = await context.bot.send_message(
                chat_id=chat_id,
                text="⏳ <i>NEMESIS réfléchit...</i>"
            )
        except Exception:
            thinking_msg = None
        
        try:
            # Initialiser la conversation
            current_input = message
            current_role = "user"
            iteration = 0
            max_iterations = 10  # Limite pour éviter les boucles infinies
            collected_outputs = []
            
            while iteration < max_iterations:
                iteration += 1
                
                # Envoyer le message à l'IA
                try:
                    result = provider.send_message(current_input, role=current_role)
                except TypeError:
                    result = provider.send_message(current_input)
                
                if not result or not isinstance(result, dict):
                    await self._cleanup_thinking_message(context, chat_id, thinking_msg)
                    await context.bot.send_message(chat_id=chat_id, text="❌ Erreur: Réponse invalide du provider")
                    return
                
                if not result.get("success"):
                    await self._cleanup_thinking_message(context, chat_id, thinking_msg)
                    error = result.get('error', 'Erreur inconnue')
                    await context.bot.send_message(chat_id=chat_id, text=f"❌ Erreur: {error}")
                    return
                
                # Parser la réponse
                raw_response = result.get('response', '')
                parsed = self.parser.parse(raw_response)
                
                # Extraire le texte à afficher
                display_text = parsed.get('text', '')
                action = parsed.get('action')
                
                # Stocker le texte pour la réponse finale
                if display_text and not display_text.startswith("FEEDBACK:"):
                    collected_outputs.append(display_text)
                
                # Si pas d'action, on arrête
                if not action:
                    break
                
                # Gérer l'action (appel d'outil)
                act_type = action.get('type', '')
                act_content = action.get('content', {})
                
                # Demander confirmation pour les outils sensibles
                if self._is_sensitive_tool(act_type):
                    # Stocker l'action en attente de confirmation
                    self.pending_actions[chat_id] = {
                        'action_type': act_type,
                        'action_content': act_content,
                        'original_input': current_input,
                        'role': current_role,
                        'iteration': iteration,
                        'collected_outputs': collected_outputs,
                        'thinking_msg': thinking_msg
                    }
                    
                    await self._cleanup_thinking_message(context, chat_id, thinking_msg)
                    
                    # Afficher le texte reçu avant de demander confirmation
                    if collected_outputs:
                        formatted_text = self._format_ai_response(collected_outputs, provider_type, model)
                        await context.bot.send_message(chat_id=chat_id, text=formatted_text)
                    
                    # Demander confirmation
                    keyboard = [
                        [InlineKeyboardButton("✅ Confirmer", callback_data=f"confirm_tool_{chat_id}")],
                        [InlineKeyboardButton("❌ Annuler", callback_data=f"cancel_tool_{chat_id}")],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    action_desc = act_type
                    if isinstance(act_content, dict):
                        action_desc = f"{act_type}: {act_content}"
                    elif isinstance(act_content, str):
                        action_desc = f"{act_type}: {act_content[:50]}"
                    
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ <b>Confirmation requise</b>\n\n"
                             f"L'IA veut exécuter: <code>{action_desc}</code>\n\n"
                             f"Accepter?",
                        reply_markup=reply_markup
                    )
                    return
                else:
                    # Exécuter directement l'outil (non sensible)
                    tool_result = await self._execute_tool(act_type, act_content, chat_id, context)
                    
                    # Construire le feedback pour l'IA
                    if isinstance(tool_result, dict):
                        if tool_result.get('success'):
                            feedback = f"FEEDBACK:\nTool: {act_type}\nSuccess: true\nOutput:\n{tool_result.get('content', tool_result.get('output', 'OK'))}"
                        else:
                            feedback = f"FEEDBACK:\nTool: {act_type}\nSuccess: false\nError:\n{tool_result.get('error', 'Erreur inconnue')}"
                    else:
                        feedback = f"FEEDBACK:\nTool: {act_type}\nSuccess: true\nOutput:\n{str(tool_result)}"
                    
                    # Envoyer le feedback à l'IA
                    current_input = feedback
                    current_role = "tool_result"
            
            # Supprimer le message "réfléchit"
            await self._cleanup_thinking_message(context, chat_id, thinking_msg)
            
            # Envoyer la réponse finale
            if collected_outputs:
                formatted_response = self._format_ai_response(collected_outputs, provider_type, model)
                await context.bot.send_message(chat_id=chat_id, text=formatted_response)
            else:
                await context.bot.send_message(chat_id=chat_id, text="ℹ️ Aucune réponse textuelle générée.")
            
        except Exception as e:
            await self._cleanup_thinking_message(context, chat_id, thinking_msg)
            logger.error(f"Erreur dans _process_ai_request: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Erreur: {str(e)[:1000]}")

    async def _cleanup_thinking_message(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, thinking_msg):
        """Supprime le message 'réfléchit' si possible."""
        if thinking_msg:
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=thinking_msg.message_id
                )
            except Exception:
                pass

    async def _send_system_prompt(self, chat_id: int) -> bool:
        """Envoye le prompt système à l'IA (pas à l'utilisateur!) pour ce chat."""
        prompt_path = Path(__file__).parent / "prompt_system_telegram.txt"
        if not prompt_path.exists():
            logger.warning("prompt_system_telegram.txt non trouvé")
            return False
        
        try:
            provider = self._get_provider(chat_id)
            if not provider:
                logger.error("Provider non disponible pour envoyer le prompt système")
                return False
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
            
            # Envoyer le prompt à l'IA via le provider, pas à l'utilisateur!
            # Certains providers (nemapi_bridge) supportent role=, d'autres non
            try:
                result = provider.send_message(prompt, role="user")
            except TypeError:
                # Provider ne supporte pas role=, envoyer sans
                result = provider.send_message(prompt)
            
            if result and result.get("success"):
                self.prompt_system_sent[chat_id] = True
                return True
            else:
                logger.error(f"Echec envoi prompt système: {result}")
                return False
        except Exception as e:
            logger.error(f"Erreur envoi prompt système: {e}")
            return False

    def _format_ai_response(self, outputs: List[str], provider_type: str, model: str) -> str:
        """Formate la réponse de l'IA comme dans le CLI NEMESIS."""
        combined_text = '\n\n'.join(outputs)
        
        if len(combined_text) > 3500:
            combined_text = combined_text[:3500] + "\n\n... (tronque)"
        
        if model:
            return f"🤖 <b>NEMESIS [{provider_type}] ({model}) :></b>\n\n{combined_text}"
        else:
            return f"🤖 <b>NEMESIS [{provider_type}] :></b>\n\n{combined_text}"

    def _format_tool_result_for_display(self, tool_result: Dict[str, Any]) -> str:
        """Formate un résultat d'outil (dict) en chaîne pour affichage."""
        if isinstance(tool_result, dict):
            if not tool_result.get('success', True):
                error = tool_result.get('error', 'Erreur inconnue')
                return f"❌ Erreur outil: {error}"
            content = tool_result.get('content', tool_result.get('output', 'OK'))
            if isinstance(content, str) and len(content) > 10000:  # 10 Ko - augmente de 3 Ko
                content = content[:10000] + "\n\n... (tronque)"
            return str(content)
        return str(tool_result)

    def _normalize_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Adapte les parametres."""
        parameters = dict(parameters)
        
        if tool_name == "read_file":
            if "files" in parameters and "paths" not in parameters and "path" not in parameters:
                parameters["paths"] = parameters.pop("files")
        elif tool_name == "bash":
            parameters.pop("mode", None)
        elif tool_name == "edit":
            if "path" in parameters and "file_path" not in parameters:
                parameters["file_path"] = parameters.pop("path")
            if "blocks" in parameters and isinstance(parameters["blocks"], list):
                blocks = parameters["blocks"]
                if len(blocks) == 1:
                    parameters["old_string"] = blocks[0].get("search", "")
                    parameters["new_string"] = blocks[0].get("replace", "")
                parameters.pop("blocks", None)
        
        return parameters

    def _format_tool_result(self, result) -> str:
        """Formate le resultat d'un outil."""
        if hasattr(result, '__iter__') and not isinstance(result, (str, dict)):
            output_parts = []
            for r in result:
                output_parts.append(self._format_tool_result(r))
            return '\n'.join(output_parts)
        
        if isinstance(result, dict):
            if result.get('success'):
                content = result.get('content', result.get('output', result.get('stdout', 'OK')))
                if isinstance(content, str) and len(content) > 10000:  # 10 Ko
                    content = content[:10000] + "\n\n... (tronque)"
                return content
            else:
                error = result.get('error', result.get('message', 'Erreur inconnue'))
                return f"❌ Erreur: {error}"
        
        if isinstance(result, str):
            if len(result) > 10000:  # 10 Ko
                return result[:10000] + "\n\n... (tronque)"
            return result
        
        return str(result)


    # =============================================================================
    # GESTION DES CALLBACKS
    # =============================================================================

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gere les callbacks des boutons inline."""
        query = update.callback_query
        await query.answer()
        
        chat_id = query.message.chat_id
        data = query.data
        config = self._get_chat_config(chat_id)
        
        if data == "cancel":
            await query.edit_message_text("❌ Operation annulee.")
            self.chat_states.pop(chat_id, None)
            self.pending_config.pop(chat_id, None)
        
        elif data.startswith("provider_"):
            provider_type = data[9:]
            config["provider"]["type"] = provider_type
            self._save_chat_config(chat_id, config)
            
            if provider_type == "bridge":
                await query.edit_message_text(
                    "🌉 Configuration Bridge\n\n"
                    "Envoyez: `host:port` (ex: 192.168.1.67:8080)"
                )
                self.chat_states[chat_id] = AWAITING_BRIDGE_HOST
            elif provider_type == "nemapi_bridge":
                await query.edit_message_text(
                    "🌉 Configuration NEMAPI Bridge\n\n"
                    "Envoyez: `host:port` (ex: 127.0.0.1:8080)"
                )
                self.chat_states[chat_id] = AWAITING_NEMAPI_HOST
            elif provider_type == "whisperer":
                await query.edit_message_text(
                    "🌉 Configuration Whisperer\n\n"
                    "Envoyez: `endpoint,token` (ex: http://localhost:9777/v1,sk-xxx)"
                )
                self.chat_states[chat_id] = AWAITING_WHISPERER_CONFIG
            else:
                # Fireworks, Groq, OpenRouter, etc.
                await query.edit_message_text(
                    f"🔑 Configuration de {PROVIDER_LABELS.get(provider_type, provider_type)}\n\n"
                    "Envoyez votre cle API.\n\n"
                    "💡 Vous devrez selectionner un modele dans la liste apres validation de la cle."
                )
                self.chat_states[chat_id] = AWAITING_PROVIDER_CONFIG
        
        elif data.startswith("model_"):
            model_id = data[6:]
            config["provider"]["model"] = model_id
            self._save_chat_config(chat_id, config)
            
            await query.edit_message_text(f"✅ Modele selectionne: {model_id}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="🆕 Utilisez /new pour demarrer une conversation.",
            )
            self.chat_states.pop(chat_id, None)
        
        elif data == "confirm_yes":
            if chat_id in self.pending_config:
                pending = self.pending_config[chat_id]
                message = pending.get("message", "")
                result = await self._handle_message_with_tools(message, chat_id, context)
                if result:
                    await context.bot.send_message(chat_id=chat_id, text=result)
                await query.edit_message_text("✅ Operation confirmee.")
                self.pending_config.pop(chat_id, None)
            else:
                await query.edit_message_text("❌ Aucune operation en attente.")
        
        elif data == "confirm_no":
            self.pending_config.pop(chat_id, None)
            await query.edit_message_text("❌ Operation annulee.")
        
        elif data.startswith("confirm_tool_"):
            # Gestion de la confirmation d'outil
            chat_id_from_data = int(data.replace("confirm_tool_", ""))
            if chat_id_from_data in self.pending_actions:
                pending = self.pending_actions[chat_id_from_data]
                
                # Exécuter l'outil
                act_type = pending['action_type']
                act_content = pending['action_content']
                tool_result = await self._execute_tool(act_type, act_content, chat_id_from_data, context)
                
                # Construire le feedback
                if isinstance(tool_result, dict):
                    if tool_result.get('success'):
                        feedback = f"FEEDBACK:\nTool: {act_type}\nSuccess: true\nOutput:\n{tool_result.get('content', tool_result.get('output', 'OK'))}"
                    else:
                        feedback = f"FEEDBACK:\nTool: {act_type}\nSuccess: false\nError:\n{tool_result.get('error', 'Erreur inconnue')}"
                else:
                    feedback = f"FEEDBACK:\nTool: {act_type}\nSuccess: true\nOutput:\n{str(tool_result)}"
                
                # Envoyer le feedback à l'IA et continuer la conversation
                provider = self._get_provider(chat_id_from_data)
                if provider:
                    result = provider.send_message(feedback, role="tool_result")
                    if result and result.get('success'):
                        raw_response = result.get('response', '')
                        parsed = self.parser.parse(raw_response)
                        display_text = parsed.get('text', '')
                        
                        if display_text and not display_text.startswith("FEEDBACK:"):
                            # Envoyer la réponse
                            config = self._get_chat_config(chat_id_from_data)
                            provider_type = config.get("provider", {}).get("type", "bridge")
                            model = config.get("provider", {}).get("model", "")
                            formatted_response = self._format_ai_response([display_text], provider_type, model)
                            await context.bot.send_message(chat_id=chat_id_from_data, text=formatted_response)
                
                await query.edit_message_text("✅ Outil exécuté et feedback envoyé à l'IA")
                self.pending_actions.pop(chat_id_from_data, None)
            else:
                await query.edit_message_text("❌ Aucune action en attente.")
        
        elif data.startswith("cancel_tool_"):
            # Annulation de l'outil
            chat_id_from_data = int(data.replace("cancel_tool_", ""))
            if chat_id_from_data in self.pending_actions:
                self.pending_actions.pop(chat_id_from_data, None)
                await query.edit_message_text("❌ Exécution de l'outil annulée.")
            else:
                await query.edit_message_text("❌ Aucune action en attente.")
        
        elif data == "history_clear":
            provider = self._get_provider(chat_id)
            if provider:
                provider.reset_conversation()
            await query.edit_message_text("🧹 Conversation effacee.")


    # =============================================================================
    # DEMARRAGE
    # =============================================================================

    def run(self):
        """Demarre le bot."""
        if not self.token:
            raise ValueError("Token Telegram manquant!")
        
        self.app = Application.builder().token(self.token).build()
        
        # Ajouter les handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("provider", self.provider_command))
        self.app.add_handler(CommandHandler("model", self.model_command))
        self.app.add_handler(CommandHandler("new", self.new_command))
        self.app.add_handler(CommandHandler("clear", self.clear_command))
        self.app.add_handler(CommandHandler("config", self.config_command))
        self.app.add_handler(CommandHandler("tools", self.tools_command))
        self.app.add_handler(CommandHandler("history", self.history_command))
        self.app.add_handler(CommandHandler("about", self.about_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))

        logger.info("Demarrage du bot Telegram NEMESIS v3.0...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    def stop(self):
        """Arrete le bot."""
        if self.app:
            self.app.stop()


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def load_bot_config(config_path: str = "telegram_config.yaml") -> Dict[str, Any]:
    """Charge la configuration du bot depuis un fichier YAML."""
    import yaml
    config_path = Path(config_path)
    if not config_path.exists():
        return {}
    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {}


def main():
    """Point d'entree principal."""
    config = load_bot_config()
    token = os.getenv('TELEGRAM_BOT_TOKEN') or config.get('token')
    workspace = config.get('workspace', './workspace')
    
    if not token:
        print("❌ Erreur: Token Telegram manquant!")
        print("   Definissez TELEGRAM_BOT_TOKEN ou creez telegram_config.yaml")
        sys.exit(1)
    
    bot = NemesisTelegramBot(token=token, workspace=workspace)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\nArret du bot...")
        bot.stop()
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
