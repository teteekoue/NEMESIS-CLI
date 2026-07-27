# NEMESIS-CLI v4.0

Agent de codage IA ultra-moderne inspiré de Claude Code, avec interface CLI fluide et appels d'outils en JSON natif.

![Version](https://img.shields.io/badge/version-4.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux%20(amd64|i386)-orange)

## 🦅 Fonctionnalités

### Tool Calling JSON Natif
- **Format OpenAI function calling** — Plus de XML, uniquement du JSON structuré
- **Support multi-providers** — API natives avec function calling (Groq, NVIDIA, OpenRouter, etc.)
- **API Bridge personnalisé** — Extraction automatique des tool calls depuis les réponses

### 7+ Providers IA Supportés
| Provider | Type | Function Calling |
|----------|------|------------------|
| Groq | Natif | ✅ |
| NVIDIA NIM | Natif | ✅ |
| OpenRouter | Natif | ✅ |
| Fireworks AI | Natif | ✅ |
| Cohere | Natif | ✅ |
| API Bridge | Custom (reverse engineering) | ✅ (extraction JSON) |
| Custom OpenAI | Endpoint personnalisé | ✅ |

### Interface Moderne Style Claude Code
- **Commandes slash complètes** — `/help`, `/clear`, `/plan`, `/dual`, `/mcp`, `/model`, etc.
- **Logo ASCII Aigle** — Identité visuelle NEMESIS
- **Thème Dracula** — Couleurs modernes et lisibles
- **TUI Textual** — Interface terminal réactive et fluide

### Modes Intelligents
- **Mode Plan** — Génération de plan structuré avant exécution
- **Mode Dual-Modèle** — Deux modèles collaboratifs (Générateur + Réviseur)
- **Sous-agents** — Agents dédiés avec APIs indépendantes pour éviter les rate limits

### Intégrations Avancées
- **MCP (Model Context Protocol)** — Connexion à des serveurs MCP externes
- **6 outils intégrés** — `bash`, `read_file`, `write_file`, `edit_file`, `list_dir`, `search_files`
- **Boucle agentic** — Exécution itérative jusqu'à résolution complète

---

## 📦 Installation

### Option 1 : Package .deb (Recommandé)

#### Pour systèmes 64 bits (amd64)
```bash
# Télécharger le paquet
wget https://github.com/teteekoue/nemesis-cli/releases/latest/download/nemesis-cli_4.0.0_amd64.deb

# Installer
sudo dpkg -i nemesis-cli_4.0.0_amd64.deb

# Configuration initiale
sudo nemesis --setup

# Lancer
nemesis
```

#### Pour systèmes 32 bits (i386)
```bash
# Télécharger le paquet
wget https://github.com/teteekoue/nemesis-cli/releases/latest/download/nemesis-cli_4.0.0_i386.deb

# Installer
sudo dpkg -i nemesis-cli_4.0.0_i386.deb

# Configuration initiale
sudo nemesis --setup

# Lancer
nemesis
```

### Option 2 : Depuis les sources

```bash
# Cloner le dépôt
git clone https://github.com/teteekoue/nemesis-cli.git
cd nemesis-cli

# Installer les dépendances
pip install -r requirements.txt

# Configuration initiale
python3 nemesis.py --setup

# Lancement
python3 nemesis.py
```

---

## 🔧 Commandes Slash

| Commande | Description |
|----------|-------------|
| `/help`, `/h`, `/?` | Afficher l'aide complète |
| `/clear`, `/c` | Effacer l'historique de conversation |
| `/exit`, `/quit`, `/q` | Quitter l'application |
| `/model [provider/model]` | Afficher ou changer le modèle |
| `/provider [name]` | Lister ou changer de provider |
| `/plan [on|off]` | Activer/désactiver le mode planification |
| `/dual [setup|on|off]` | Mode dual-modèle (2 APIs) |
| `/mcp [list|add|remove]` | Gestion des serveurs MCP |
| `/config [set key value]` | Configuration avancée |
| `/cost` | Afficher la consommation de tokens |
| `/status` | Statut complet de la session |
| `/compact` | Compacter l'historique |
| `/undo` | Annuler le dernier échange |
| `/auto` | Mode auto-allow (exécution automatique) |
| `/agent` | Gestion des sous-agents |

---

## 🏗️ Build du Package .deb

### Build pour amd64 (64 bits)
```bash
chmod +x build_deb.sh
./build_deb.sh
```

### Build pour toutes architectures (amd64 + i386)
```bash
./build_deb.sh --all
```

Les paquets seront générés dans le dossier `dist/` :
- `nemesis-cli_4.0.0_amd64.deb` — Pour systèmes 64 bits
- `nemesis-cli_4.0.0_i386.deb` — Pour systèmes 32 bits

### Prérequis de compilation
- Python 3.8+
- PyInstaller
- dpkg-deb (pour créer les paquets .deb)
- libc6 >= 2.31
- libssl3
- ca-certificates

---

## 📁 Structure du Projet

```
nemesis.py              # Point d'entrée principal
build_deb.sh            # Script de build .deb
requirements.txt        # Dépendances Python
src/
  config.py             # Configuration (dataclass, JSON)
  prompts.py            # Chargeur de prompts système
  providers/            # Providers IA (factory pattern)
    base.py             # Classe abstraite + ProviderResponse
    groq_provider.py    # Provider Groq
    nvidia_nim.py       # Provider NVIDIA NIM
    openrouter.py       # Provider OpenRouter
    fireworks.py        # Provider Fireworks AI
    cohere_provider.py  # Provider Cohere
    api_bridge.py       # Bridge custom (polling HTTP)
    custom_openai.py    # Provider OpenAI custom
  agent/                # Noyau agent
    core.py             # Boucle agentic principale
    sub_agent.py        # Gestionnaire sous-agents (threads)
    modes.py            # Mode Plan + Mode Dual-Modèle
  tools/                # Outils function calling
    definitions.py      # Schémas JSON (OpenAI format)
    executor.py         # Exécuteur d'outils
  mcp/                  # Model Context Protocol
    client.py           # Client stdio JSON-RPC
    manager.py          # Gestionnaire multi-serveurs
  ui/                   # Interface utilisateur
    theme.py            # Thème Dracula (rich)
    logo.py             # Logo ASCII Aigle
    renderer.py         # Rendu des sorties (rich)
    input_handler.py    # Input avec prompt_toolkit
  commands/             # Système de commandes slash
    registry.py         # Registre décorateur
    builtins.py         # Commandes intégrées
  tui/                  # Interface Textual (TUI)
    app.py              # Application TUI principale
    css.py              # Styles CSS
    theme.py            # Thème de couleurs
prompts/                # Prompts système
  system.txt            # Prompt système principal
  plan.txt              # Prompt mode Plan
  sub_agent.txt         # Prompt sous-agents
```

---

## ⚙️ Configuration

La configuration est stockée dans `~/.nemesis/config.json`.

### Fichier de configuration exemple
```json
{
  "active_provider": "groq",
  "active_model": "llama-3.3-70b-versatile",
  "workspace": "/home/user/projects",
  "providers": {
    "groq": {
      "api_key": "gsk_xxx",
      "model": "llama-3.3-70b-versatile",
      "max_tokens": 8192,
      "temperature": 0.7
    },
    "api_bridge": {
      "base_url": "http://192.168.1.67:8080"
    }
  },
  "dual_model": {
    "model_a_provider": "groq",
    "model_a_api_key": "gsk_xxx",
    "model_a_model": "llama-3.3-70b-versatile",
    "model_b_provider": "groq",
    "model_b_api_key": "gsk_xxx",
    "model_b_model": "llama-3.1-70b-versatile"
  }
}
```

---

## 🛠️ Désinstallation

### Si installé via .deb
```bash
sudo apt remove nemesis-cli
# ou
sudo dpkg -r nemesis-cli
```

### Suppression manuelle des fichiers de configuration
```bash
rm -rf ~/.nemesis
```

---

## 🎯 Modes Spéciaux

### Mode Plan
Activez le mode planification pour que NEMESIS génère un plan détaillé avant d'exécuter toute action :
```
/plan on
```

### Mode Dual-Modèle
Configurez deux modèles pour qu'ils collaborent sur une tâche :
```
/dual setup
```
Puis activez-le :
```
/dual on
```

Le modèle A propose des solutions, le modèle B les révise et les approuve.

---

## 📝 Licence

MIT License — Voir le fichier LICENSE pour plus de détails.

---

## 🦅 Logo

```
                    ___
               ____/   \____
              /             \
             |  (o)     (o)  |
             |       <       |   N E M E S I S
             |    \_____/    |      C L I  v4.0
             |  /         \  |
              \ \  _____  / /
               \_\|_____||/_/
                  |_____||
                  |_____||
                  |_____||
                  |_____||
                  |_____||
```
