"""Définitions des outils en JSON Schema (format OpenAI function calling)."""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Exécuter une commande bash dans le terminal. Retourne stdout et stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "La commande bash a exécuter"},
                    "timeout": {"type": "integer", "description": "Timeout en secondes (défaut 300)", "default": 300},
                    "working_dir": {"type": "string", "description": "Répertoire de travail (optionnel)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lire le contenu d'un fichier texte.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin du fichier"},
                    "offset": {"type": "integer", "description": "Ligne de départ (1-based)", "default": 1},
                    "limit": {"type": "integer", "description": "Nombre max de lignes", "default": 200}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Écrire du contenu dans un fichier (crée ou écrase).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin du fichier"},
                    "content": {"type": "string", "description": "Contenu à écrire"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Remplacer un texte par un autre dans un fichier existant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin du fichier"},
                    "old_text": {"type": "string", "description": "Texte exact à remplacer"},
                    "new_text": {"type": "string", "description": "Texte de remplacement"}
                },
                "required": ["path", "old_text", "new_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Lister les fichiers et dossiers d'un répertoire.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin du répertoire"},
                    "recursive": {"type": "boolean", "description": "Liste récursive", "default": False}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Rechercher un motif dans les fichiers d'un répertoire.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Motif de recherche (regex)"},
                    "path": {"type": "string", "description": "Répertoire de recherche"},
                    "file_pattern": {"type": "string", "description": "Filtre de fichiers (glob, ex: *.py)"}
                },
                "required": ["pattern", "path"]
            }
        }
    },
]

def get_tool_definitions():
    return TOOL_DEFINITIONS
