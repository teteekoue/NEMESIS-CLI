#!/bin/bash

echo "=== Préparation du Build NEMESIS CLI ==="

# Activation de l'environnement virtuel
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERREUR : Environnement virtuel (venv) introuvable."
    exit 1
fi

# Installation de PyInstaller si nécessaire
pip install pyinstaller

echo "=== Lancement de la Compilation (PyInstaller) ==="

# Compilation en un seul fichier
# --collect-all assure que les dépendances graphiques complexes sont incluses
pyinstaller --onefile \
  --name nemesis \
  --add-data "src:src" \
  --add-data "prompt_system.txt:." \
  --add-data "agent_subordinate_prompt.txt:." \
  --add-data "tools_library:tools_library" \
  --collect-all rich \
  --collect-all prompt_toolkit \
  --collect-all ddgs \
  --collect-all yaml \
  agent_modular.py

echo ""
echo "=== Build Terminé ! ==="
echo "Votre binaire se trouve dans : ./dist/nemesis"
echo "Vous pouvez maintenant le copier n'importe où sur Linux."
