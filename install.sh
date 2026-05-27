#!/bin/bash

# Script d'installation de NEMESIS CLI
# Crée l'environnement virtuel et installe les dépendances nécessaires.

echo "=== Installation de NEMESIS CLI ==="

# Vérifier Python
if ! command -v python3 &> /dev/null; then
    echo "ERREUR: python3 n'est pas installé."
    exit 1
fi

# Vérifier tree (requis pour list_dir dans tools.py)
if ! command -v tree &> /dev/null; then
    echo "AVERTISSEMENT: 'tree' n'est pas installé. Veuillez l'installer pour la commande list_dir."
    echo "  sudo apt install tree"
fi

# Créer le venv
echo "Création de l'environnement virtuel..."
python3 -m venv venv

# Activer et installer les dépendances
echo "Installation des dépendances Python..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo ""
echo "=== Installation terminée ==="
echo "Pour lancer NEMESIS CLI: ./nemesis-cli2"
echo "Ou lancez directement : ./venv/bin/python agent_modular.py"
