#!/bin/bash
set -e
echo "=== Installation de NEMESIS CLI (dev local) ==="

if ! command -v python3 &>/dev/null; then
    echo "ERREUR: python3 n'est pas installé."
    exit 1
fi

if ! command -v tree &>/dev/null; then
    echo "AVERTISSEMENT: 'tree' non installé (utile pour list_dir). sudo apt install tree"
fi

echo "Création de l'environnement virtuel..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo ""
echo "=== Installation terminée ==="
echo "Lancer:  ./venv/bin/python3 agent.py"
echo "Config:  ~/.config/nemesis-cli/  (créée au premier lancement)"
echo "Workspace par défaut: ~/nemesis-workspace"
