#!/bin/bash
# Script de lancement du bot Telegram NEMESIS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activer le venv s'il existe
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Utiliser python3
PYTHON="python3"

echo "=========================================="
echo "  NEMESIS Telegram Bot"
echo "=========================================="
echo ""
echo "Utilisation: $PYTHON"
echo ""

# Vérifier si le token est défini
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  Token Telegram non trouvé dans les variables d'environnement"
    echo ""
    
    # Vérifier si le fichier de config existe
    if [ -f "telegram_config.yaml" ]; then
        echo "✅ Fichier telegram_config.yaml trouvé"
        echo "   Démarrage du bot..."
        $PYTHON telegram_bot.py
    else
        echo "❌ Ni TELEGRAM_BOT_TOKEN ni telegram_config.yaml trouvé!"
        echo ""
        echo "Pour démarrer le bot, vous avez besoin de:"
        echo "1. Créer un bot via @BotFather sur Telegram"
        echo "2. Récupérer le token du bot"
        echo "3. Soit définir la variable d'environnement:"
        echo "   export TELEGRAM_BOT_TOKEN='votre_token'"
        echo "   puis exécuter: $0"
        echo ""
        echo "4. Soit créer un fichier telegram_config.yaml avec:"
        echo "   token: votre_token"
        echo "   puis exécuter: $0"
        exit 1
    fi
else
    echo "✅ Token Telegram trouvé dans TELEGRAM_BOT_TOKEN"
    echo "   Démarrage du bot..."
    $PYTHON telegram_bot.py
fi
