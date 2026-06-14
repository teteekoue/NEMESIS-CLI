#!/bin/bash

# Script d'installation de NEMESIS CLI
# Assure la configuration de l'environnement virtuel et des dépendances.

set -e  # Arrêter le script si une commande échoue

echo "========================================"
echo "=== Installation de NEMESIS CLI v2 ==="
echo "========================================"

# 1. Vérification de Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERREUR] python3 n'est pas installé."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[INFO] Python détecté : $PYTHON_VERSION"

# 2. Création de l'environnement virtuel
if [ -d "venv" ]; then
    echo "[INFO] Dossier venv existant. Suppression..."
    rm -rf venv
fi

echo "[INFO] Création de l'environnement virtuel..."
python3 -m venv venv

# 3. Activation de l'environnement pour le script
source venv/bin/activate

# 4. Mise à jour des outils de packaging
echo "[INFO] Mise à jour des outils de packaging (pip, setuptools, wheel)..."
pip install --upgrade pip setuptools wheel --quiet

# 5. Installation des dépendances
if [ -f "requirements.txt" ]; then
    echo "[INFO] Installation des dépendances depuis requirements.txt..."
    pip install -r requirements.txt --quiet
else
    echo "[ERREUR] Le fichier requirements.txt est introuvable."
    exit 1
fi

# 6. Vérification des outils système requis (optionnel)
if ! command -v tree &> /dev/null; then
    echo "[AVERTISSEMENT] L'outil 'tree' n'est pas installé."
    echo "              Certaines fonctionnalités (list_dir) seront limitées."
    echo "              Installation conseillée : sudo apt install tree"
fi

echo ""
echo "========================================"
echo "=== Installation terminée avec succès ==="
echo "========================================"
echo "Pour activer l'environnement : source venv/bin/activate"
echo "Pour lancer NEMESIS : ./venv/bin/python agent_modular.py"
echo "========================================"
