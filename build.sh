#!/bin/bash

echo "=== Préparation du Build NEMESIS CLI ==="

# Activation de l'environnement virtuel
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERREUR : Environnement virtuel (venv) introuvable."
    exit 1
fi

# Installation de PyInstaller et dépendances nécessaires
pip install --upgrade pip
pip install pyinstaller -r requirements.txt

echo "=== Lancement de la Compilation (PyInstaller) ==="

# Compilation avec imports explicites pour résoudre les warnings
pyinstaller --onefile \
  --name nemesis-cli \
  --add-data "src:src" \
  --add-data "prompt_system.txt:." \
  --add-data "agent_subordinate_prompt.txt:." \
  --add-data "tools_library:tools_library" \
  --hidden-import prompt_toolkit \
  --hidden-import prompt_toolkit.filters \
  --hidden-import prompt_toolkit.key_binding \
  --collect-all rich \
  --collect-all prompt_toolkit \
  --collect-all ddgs \
  --collect-all yaml \
  agent_modular.py

echo ""
echo "=== Build Terminé ! ==="
echo "Votre binaire se trouve dans : ./dist/nemesis-cli"
