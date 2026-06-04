import os
import sys
from pathlib import Path

def get_resource_path(relative_path: str) -> Path:
    """
    Résout le chemin d'une ressource interne (prompt, source, etc.).
    Compatible avec PyInstaller (sys._MEIPASS).
    """
    try:
        # PyInstaller crée un dossier temporaire et stocke le chemin dans _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # En mode développement, on utilise le chemin absolu du projet
        base_path = Path(os.path.abspath("."))

    return (base_path / relative_path).resolve()

def ensure_workspace_structure(workspace_path: str):
    """
    Crée l'arborescence minimale requise pour le fonctionnement de l'agent.
    """
    ws = Path(workspace_path).resolve()
    subdirs = [
        "tasks/inbox",
        "tasks/outbox",
        "logs"
    ]
    
    for sd in subdirs:
        target = ws / sd
        target.mkdir(parents=True, exist_ok=True)
    
    return True
