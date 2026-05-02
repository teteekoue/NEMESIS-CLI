#!/bin/bash

Script d'installation de NEMESIS CLI

Cree l'environnement virtuel et installe les dependances

echo "=== Installation de NEMESIS CLI ==="

Verifier Python

if ! command -v python3 &> /dev/null; then
echo "ERREUR: python3 non trouve. Installe-le d'abord."
exit 1
fi

Creer le venv

echo "Creation de l'environnement virtuel..."
python3 -m venv venv

Activer et installer les dependances

echo "Installation des dependances Python..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

Verifier LibreOffice

if command -v soffice &> /dev/null; then
echo "LibreOffice detecte - conversion PDF active."
else
echo "AVERTISSEMENT: LibreOffice non trouve. Conversion HTML->PDF indisponible."
echo "  Installe-le avec: sudo apt install libreoffice"
fi

echo ""
echo "=== Installation terminee ==="
echo "Pour lancer NEMESIS CLI: ./nemesis-cli2"
echo "Mode debug: ./venv/bin/python agent.py --debug"
