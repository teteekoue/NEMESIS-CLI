# NEMESIS-CLI v3.0

Agent de codage IA autonome, moderne et multi-fournisseurs.

## Fonctionnalités

- **Tool Calling JSON natif** — Format OpenAI function calling (pas de XML)
- **7 providers IA** — Groq, NVIDIA NIM, OpenRouter, Fireworks, Cohere, API Bridge, Custom OpenAI
- **Boucle agentic** — L'agent appelle des outils itérativement jusqu'à résolution
- **CLI moderne** — prompt_toolkit, complétion slash commands, thème Dracula (rich)
- **MCP (Model Context Protocol)** — Intégration de serveurs MCP via stdio JSON-RPC
- **Mode Plan** — Génération de plan JSON structuré avant exécution
- **Mode Dual-Modèle** — Générateur + Réviseur avec approbation itérative
- **Sous-agents** — Spawn d'agents dédiés dans des threads séparés avec APIs indépendantes
- **6 outils intégrés** — bash, read_file, write_file, edit_file, list_dir, search_files

## Installation

```bash
# Dépendances
pip install -r requirements.txt

# Configuration initiale
python3 nemesis.py --setup

# Lancement
python3 nemesis.py
# ou
./start
```

## Build .deb

```bash
chmod +x build_deb.sh
./build_deb.sh
```

## Commandes slash

| Commande | Description |
|----------|-------------|
| `/help` | Afficher l'aide |
| `/model` | Afficher/changer le modèle |
| `/provider` | Changer de provider |
| `/plan` | Activer/désactiver le mode plan |
| `/dual` | Mode dual-modèle |
| `/mcp` | Gestion MCP (list/add/remove) |
| `/agent` | Gestion sous-agents |
| `/compact` | Compacter l'historique |
| `/cost` | Afficher l'usage tokens |
| `/status` | Statut complet |
| `/config` | Configuration |
| `/auto` | Mode auto-allow |
| `/undo` | Annuler dernier échange |
| `/clear` | Effacer l'historique |
| `/exit` | Quitter |

## Structure

```
nemesis.py           # Point d'entrée principal
src/
  config.py          # Configuration (dataclass, JSON)
  prompts.py         # Chargeur de prompts
  providers/         # Providers IA (factory pattern)
    base.py          # Classe abstraite + ProviderResponse
    groq_provider.py
    nvidia_nim.py
    openrouter.py
    fireworks.py
    cohere_provider.py
    api_bridge.py    # Polling GET /ask → GET /result
    custom_openai.py
  agent/            # Noyau agent
    core.py          # Boucle agentic principale
    sub_agent.py     # Gestionnaire sous-agents (threads)
    modes.py         # Mode Plan + Mode Dual-Modèle
  tools/            # Outils function calling
    definitions.py   # Schémas JSON (OpenAI format)
    executor.py      # Exécuteur d'outils
  mcp/              # Model Context Protocol
    client.py        # Client stdio JSON-RPC
    manager.py       # Gestionnaire multi-serveurs
  ui/               # Interface utilisateur
    theme.py         # Thème Dracula (rich)
    logo.py          # Logo ASCII
    renderer.py      # Rendu des sorties (rich)
    input_handler.py # Input avec prompt_toolkit
  commands/         # Système de commandes slash
    registry.py      # Registre décorateur
    builtins.py      # Commandes intégrées
prompts/            # Prompts système
  system.txt
  plan.txt
  sub_agent.txt
```

## Configuration

La configuration est stockée dans `~/.nemesis/config.json`.

## Licence

MIT
