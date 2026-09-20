# NEMESIS-CLI

**Agent IA Autonome de Codage et d'Administration Système**

Développé par **TEJF - L'Aigle de la Justice**

---

## Table des Matières

1. [Vue d'Ensemble](#-vue-densemble)
2. [Fonctionnalités Clés](#-fonctionnalités-clés)
3. [Architecture](#-architecture)
4. [Prérequis](#-prérequis)
5. [Installation](#-installation)
6. [Configuration](#-configuration)
7. [Utilisation](#-utilisation)
8. [Système d'Autorisation](#-système-dautorisation)
9. [Outils Disponibles](#-outils-disponibles)
10. [Sécurité](#-sécurité)
11. [Commandes Slash](#-commandes-slash)
12. [Exemples d'Utilisation](#-exemples-dutilisation)
13. [Développement](#-développement)
14. [Dépannage](#-dépannage)
15. [Licence](#-licence)

---

## Vue d'Ensemble

**NEMESIS CLI** est un agent IA autonome de nouvelle génération conçu pour automatiser des tâches complexes sur les systèmes Linux. Il combine une intelligence artificielle avancée avec des capacités d'exécution système contrôlée, offrant une expérience utilisateur fluide et sécurisée.

### Capacités Principales

- Exécution de commandes système contrôlée et sécurisée
- Manipulation intelligente de fichiers (lecture, écriture, recherche/remplacement)
- Gestion de processus et tâches en arrière-plan
- Support du **Model Context Protocol (MCP)**
- Interface terminal moderne avec **Rich** et **prompt_toolkit**
- Interface coding-agent alternative et compacte (`cli.py`)
- Conservation du contexte côté serveur NEMAPI
- Gestion interactive des commandes nécessitant des entrées utilisateur

---

## Fonctionnalités Clés

### Système d'Autorisation Intelligent

NEMESIS implémente un système de confirmation avant chaque exécution d'outil :

- **`y`** : Autoriser une seule fois
- **`n`** : Refuser l'exécution
- **`a`** : Autoriser pour toute la session

Ce système garantit que l'utilisateur a un contrôle total sur les actions effectuées par l'IA.

### Support du Collage de Texte

L'interface permet désormais de coller du texte directement dans la barre de saisie :
- **Ctrl+V** : Coller depuis le presse-papiers
- Support natif via `InMemoryClipboard`
- Intégration transparente avec prompt_toolkit

### Streaming Temps Réel

Les commandes Bash sont exécutées avec :
- Affichage instantané des sorties
- Détection automatique des prompts interactifs (sudo, read, etc.)
- Affichage des 10 dernières lignes de contexte pour aider l'utilisateur
- Conversion automatique de `sudo` en `sudo -S` pour la lecture depuis stdin

### Parseur Multi-Niveaux

NEMESIS supporte plusieurs formats de réponse :
- JSON strict (format principal)
- JSON strict et JSON relaxé
- Appels groupés et appels tronqués
- XML/Qwen tolérant
- Nettoyage du protocole avant affichage

### Appels d'outils par lot

NEMESIS accepte un appel JSON unique ou un tableau JSON d'appels. Les
opérations indépendantes de lecture/recherche peuvent ainsi être exécutées
dans le même tour, tandis que les écritures dépendantes restent ordonnées.
Le registre dynamique est la source canonique des noms, schémas et niveaux de
risque exposés au CLI, à Telegram et aux sous-agents.

---

## Architecture

```
nemesis-cli/
├── agent.py                 # Point d'entrée principal
├── cli.py                   # Lanceur de l'interface coding-agent alternative
├── action_parser.py         # Parseur multi-niveaux des réponses IA
├── tools.py                 # Exécuteur d'outils principal
├── tools_schema.py          # Schéma centralisé des outils disponibles
├── bridge_client.py         # Client pour la communication avec l'IA
├── uploader.py              # Gestion des uploads de fichiers
├── config.yaml             # Configuration locale (non commité)
├── mcp_config.yaml          # Configuration MCP (non commité)
├── prompt_system.txt        # Prompt système pour l'IA
├── install.sh              # Script d'installation
├── requirements.txt         # Dépendances Python
├── .gitignore              # Fichiers à exclure du versionnage
├── src/
│   ├── core/
│   │   ├── commands.py      # Système de commandes slash
│   │   ├── default_commands.py
│   │   ├── mcp_client.py     # Client MCP
│   │   ├── mcp_manager.py    # Gestionnaire MCP
│   │   ├── tool_registry.py # Registre des outils
│   │   └── ...
│   └── ui/
│       ├── composer.py      # Orchestration I/O
│       ├── chat_ui.py        # Interface de chat
│       ├── header.py        # En-têtes et bannières
│       └── theme.py         # Thème Catppuccin
├── providers/
│   ├── base.py             # Provider de base
│   └── nemapi_v3.py        # Provider NEMAPI (nom public : NEMAPI)
├── tests/                  # Tests unitaires
└── tools_library/          # Bibliothèque de skills extensibles
```

---

## Prérequis

### Système
- **OS** : Linux (testé sur Ubuntu, Debian, Fedora)
- **Python** : 3.10 ou supérieur
- **Mémoire** : 4 Go minimum recommandé
- **Espace disque** : 2 Go minimum

### Dépendances Python
Toutes les dépendances sont listées dans `requirements.txt` :
```bash
rich>=13.0.0
prompt_toolkit>=3.0.0
pyyaml>=6.0.0
requests>=2.31.0
h11>=0.14.0
httpcore>=1.0.0
click>=8.0.0
```

### Outils Système Recommandés
- `tree` : Pour l'exploration de fichiers
- `git` : Pour le versionnage
- `curl` / `wget` : Pour les téléchargements

---

## Installation

### Méthode 1 : Installation sur Android / Termux (32 bits)

L'installation via Pip standard échouera sur les systèmes Termux ARMv7 car certaines dépendances natives ne sont pas pré-compilées.
Nous avons préparé un pack tout-en-un pour Termux.

👉 **Veuillez consulter le [Guide d'installation pour Termux (ARMv7)](TERMUX_INSTALL.md)** pour une installation simple et automatisée.

### Méthode 2 : Installation Standard (Linux/Mac/PC)


```bash
# 1. Cloner le dépôt
git clone https://github.com/TEJF/nemesis-cli.git
cd nemesis-cli

# 2. Créer l'environnement virtuel
python3 -m venv venv

# 3. Activer l'environnement
source venv/bin/activate

# 4. Installer les dépendances
pip install -r requirements.txt

# 5. Lancer NEMESIS
./venv/bin/python3 agent.py
```

### Interface coding-agent alternative

`cli.py` utilise exactement le même moteur, les mêmes outils et les mêmes
commandes que `agent.py`, mais avec une présentation plus adaptée au travail
de développement : conversation en flux, appels d'outils séparés des
résultats, sorties de commandes visibles et confirmations compactes.

```bash
./venv/bin/python3 cli.py
# ou avec les diagnostics du moteur
./venv/bin/python3 cli.py --debug
```

Cette interface est volontairement parallèle afin de pouvoir être évaluée
sans modifier l'interface historique lancée par `agent.py`.

L’interface expérimentale reprend les conventions d’affichage de Mistral Vibe
(composer persistant, transcript compact, cartes d’outils, todo et fermeture
à double `Ctrl+C`). Les primitives adaptées sont isolées dans
`src/ui/vibe_style.py` et accompagnées de leur notice Apache-2.0.

### Aperçu local avec le moteur NEMAPI fictif

Pour tester l'interface sans serveur NEMAPI, lancez :

```bash
python cli.py --mock
```

Le moteur fictif répond avec des appels JSON et exécute les vrais handlers de
l'agent. Dans la session, répondez `n` à la question du prompt système, puis
utilisez l'une de ces demandes exactes :

| Demande à saisir | Ce qui est affiché |
|---|---|
| `lis un fichier` | Appel `read_file` et aperçu du résultat |
| `lance une commande bash` | Appel Bash, sortie et statut de réussite |
| `fais une modification` | Demande d'autorisation puis appel `write` |
| `montre une erreur` | Sortie stderr et statut d'échec |
| `affiche un plan` | Carte de plan avec états pending/in_progress/completed |
| `teste tous les outils` | Deux appels Bash groupés et leurs résultats |

Pour les scénarios Bash, écrivez `y` quand l'interface demande
`Allow ... [y] once [a] always [n] deny`. Pour le scénario d'écriture,
`y` autorise également la création de `mock-ui-demo.txt` dans le workspace
configuré. Ce fichier peut être supprimé après le test.

### Méthode 2 : Installation Rapide

```bash
# Exécuter le script d'installation
chmod +x install.sh
./install.sh
```

Le script d'installation :
- Crée l'environnement virtuel
- Installe les dépendances
- Configure les fichiers de base

---

## Configuration

### Fichier `config.yaml`

Le fichier de configuration principal contrôle le comportement de NEMESIS :

```yaml
provider:
  type: nemapi
  model: qwen-chat

nemapi:
  host: 127.0.0.1
  port: 8090

# Configuration de sécurité
security:
  workspace: ./workspace
  allowed_commands:
    - ls
    - cd
    - cat
    - grep
    - find
    - echo
    - pwd

# Configuration MCP (optionnelle)
mcp:
  enabled: true
  servers:
    - calculator
    - filesystem
```

NEMAPI expose la liste réelle de ses modèles via `GET /v1/models`. Utilisez
`/config` pour modifier l'URL et le port du serveur, puis `/models` pour
sélectionner un modèle officiel. Si la liste est indisponible, `/models`
permet de saisir directement l'identifiant du modèle. La configuration peut
laisser `model` vide pour utiliser le premier modèle retourné. NEMESIS envoie
uniquement le message courant : l'historique et le contexte du prompt système
sont conservés par NEMAPI.

Au démarrage, NEMESIS demande si le prompt système doit être renvoyé. Répondez
`n` ou appuyez sur Entrée (valeur par défaut) pour poursuivre une session
NEMAPI existante en envoyant uniquement le message utilisateur. Répondez `o`
pour envoyer le prompt système une seule fois avant le premier message.

### Fichier `mcp_config.yaml`

Configuration spécifique pour le Model Context Protocol :

```yaml
# Liste des serveurs MCP activés
servers:
  - name: calculator
    command: python3 mcp_calculator.py
    enabled: true
    
  - name: filesystem
    command: mcp-server-filesystem
    args: [--path, ./workspace]
    enabled: true
```

---

## Utilisation

### Démarrage

```bash
# Lancer NEMESIS
./venv/bin/python3 agent.py

# Mode debug (pour le développement)
./venv/bin/python3 agent.py --debug
```

### Interface Utilisateur

NEMESIS propose une interface terminal moderne avec :
- **Affichage coloré** grâce à Rich
- **Saisie intelligente** avec prompt_toolkit
- **Complétion automatique** pour les commandes slash
- **Historique des commandes**
- **Support du collage** (Ctrl+V)

### Flux de Travail Typique

1. **Lancer NEMESIS** : `./venv/bin/python3 agent.py`
2. **Poser une question** : Par exemple, "Liste les fichiers Python dans /home/user"
3. **L'IA propose une action** : Elle affiche le JSON de l'outil à exécuter
4. **Autorisation** : NEMESIS demande `Autoriser ? (y=oui une fois / n=non / a=toujours autoriser)`
5. **Exécution** : Si autorisé, l'outil est exécuté et le résultat est affiché
6. **Feedback** : Le résultat est envoyé à l'IA pour la suite

---

## Système d'Autorisation

### Fonctionnement

Avant chaque exécution d'outil, NEMESIS demande une confirmation explicite :

```
⚠️ L'IA veut exécuter un outil :
  Outil: bash
  command: ls -la /home/user

Autoriser ? (y=oui une fois / n=non / a=toujours autoriser)
```

### Options

| Option | Description | Persistance |
|--------|-------------|-------------|
| `y` | Autoriser cette exécution uniquement | Non |
| `n` | Refuser l'exécution | Non |
| `a` | Autoriser pour toute la session | Oui |

### Avertissements Spéciaux

Pour les commandes potentiellement interactives (contenant `sudo`, `read`, `-p`), NEMESIS affiche un avertissement supplémentaire :

```
⚠️ Cette commande peut demander des entrées supplémentaires (mot de passe, etc.)
```

---

## Outils Disponibles

NEMESIS supporte actuellement **20 outils** différents, organisés en catégories :

### Outils de Fichiers

| Outil | Description | Paramètres |
|-------|-------------|------------|
| `read_file` | Lit un ou plusieurs fichiers | `files: list[str]` |
| `write_file` | Crée ou écrase un fichier | `path: str`, `content: str` |
| `append_file` | Ajoute du contenu à un fichier | `path: str`, `content: str` |
| `replace_file` | Recherche et remplace dans un fichier | `path: str`, `blocks: list` |

### Outils Bash

| Outil | Description | Paramètres |
|-------|-------------|------------|
| `bash` | Exécute une commande shell | `command: str`, `mode: str` |

**Modes disponibles** :
- `synchrone` (défaut) : Exécution bloquante avec streaming
- `asynchrone` : Exécution en arrière-plan

### Outils de Recherche

| Outil | Description | Paramètres |
|-------|-------------|------------|
| `grep` | Recherche un motif dans des fichiers | `pattern: str`, `path: str` |
| `list_dir` | Liste le contenu d'un dossier | `path: str` |

### Outils Système

| Outil | Description | Paramètres |
|-------|-------------|------------|
| `validate_code` | Valide la syntaxe d'un fichier | `path: str` |
| `stop_all` | Arrête tous les processus en arrière-plan | - |
| `check_process` | Vérifie l'état d'un processus | `pid: int` |
| `kill_process` | Tue un processus spécifique | `pid: int` |
| `cleanup_logs` | Nettoie les logs des processus terminés | - |

### Outils MCP (Model Context Protocol)

| Outil | Description | Paramètres |
|-------|-------------|------------|
| `mcp_list` | Liste les serveurs MCP installés | - |
| `mcp_tools_list` | Liste les outils d'un serveur MCP | `server: str` |
| `mcp_call` | Appelle un outil MCP | `server: str`, `tool: str`, `arguments: dict` |

### Outils Divers

| Outil | Description | Paramètres |
|-------|-------------|------------|
| `web_search` | Effectue une recherche web | `query: str` |
| `upload` | Upload un fichier | `file_path: str` |
| `update_tracker` | Met à jour le tracker de tâches | `project: str`, `task: str`, `status: str` |

---

## Sécurité

### Principes de Sécurité

NEMESIS implémente plusieurs couches de sécurité :

1. **Workspace Isolé** : Toutes les opérations sont confinées dans `./workspace` par défaut
2. **Système d'Autorisation** : Confirmation explicite avant chaque exécution
3. **Validation de Code** : Vérification automatique de la syntaxe Python/Bash
4. **Conversion Sudo** : `sudo` est automatiquement converti en `sudo -S` pour la lecture depuis stdin
5. **Limite de Sortie** : Les sorties sont tronquées à 10 000 000 caractères pour éviter les floods

### Actions Autorisées Sans Confirmation

- Lecture de fichiers (`read_file`, `grep`, `list_dir`)
- Écriture de fichiers dans le workspace
- Exécution de commandes en lecture seule (`ls`, `cat`, `grep`, `find`, etc.)
- Exécution de tests (`pytest`, `unittest`, etc.)
- Validation de code (`validate_code`)
- Recherche web (`web_search`)

### Actions Nécessitant Confirmation

- Suppression de fichiers ou dossiers (`rm`, `rmdir`, `rm -rf`)
- Modification de fichiers système (`/etc/`, `/usr/`, `/var/`, etc.)
- Exécution de commandes destructrices (`dd`, `mkfs`, `fdisk`, etc.)
- Installation de paquets système (`apt install`, `pip install --system`, etc.)
- Modification de permissions (`chmod`, `chown` sur des fichiers système)
- Redémarrage de services (`systemctl restart`, `service restart`)

### Actions Interdites

- Exécution de commandes en tant que root sans sudo
- Modification de `/boot/`, `/lib/`, `/lib64/`
- Exécution de commandes pouvant bricker le système
- Téléchargement et exécution de code non vérifié
- Suppression récursive sans confirmation (`rm -rf /`, etc.)
- Modification de `/proc/`, `/sys/`, `/dev/`
- Exécution de scripts inconnus

---

## Commandes Slash

NEMESIS propose des commandes spéciales préfixées par `/` :

| Commande | Description |
|----------|-------------|
| `/help` | Affiche la liste des commandes disponibles |
| `/status` | Affiche la connexion, le modèle, le endpoint et le workspace |
| `/todo` | Affiche le plan de travail courant |
| `/models` | Liste et sélectionne un modèle NEMAPI depuis `/v1/models` |
| `/model` | Alias de `/models` |
| `/tools` | Liste les outils disponibles |
| `/config` | Configure l'URL et le port du serveur NEMAPI |
| `/stats` | Affiche les statistiques de session |
| `/history` | Consulte ou gère l'historique |
| `/agents` | Gère les sous-agents (délégation) |
| `/skills` | Gère les compétences additionnelles |
| `/stats` | Affiche les métriques de la session |
| `/clear` | Réinitialise l'affichage du terminal |
| `/exit` | Quitte NEMESIS |

### Utilisation des Commandes Slash

```
# Afficher l'aide
/help

# Sélectionner un modèle NEMAPI depuis le serveur
/models

# Lister les outils
/tools

# Afficher les statistiques
/stats
```

---

## Exemples d'Utilisation

### Exemple 1 : Explorer un Projet

**Utilisateur** : "Explore le projet dans /home/user/myproject"

**IA** :
```json
{
  "tool": "bash",
  "parameters": {
    "command": "find /home/user/myproject -type f -name '*.py' | head -20"
  }
}
```

**NEMESIS** :
```
⚠️ L'IA veut exécuter un outil :
  Outil: bash
  command: find /home/user/myproject -type f -name '*.py' | head -20

Autoriser ? (y=oui une fois / n=non / a=toujours autoriser)
```

**Utilisateur** : `y`

**Résultat** : Liste des fichiers Python affichée en temps réel

---

### Exemple 2 : Modifier un Fichier

**Utilisateur** : "Dans config.py, change DEBUG de False à True"

**IA** :
```json
{
  "tool": "read_file",
  "parameters": {
    "files": ["config.py"]
  }
}
```

**NEMESIS** : Affiche le contenu de config.py

**IA** :
```json
{
  "tool": "replace_file",
  "parameters": {
    "path": "config.py",
    "blocks": [
      {
        "search": "DEBUG = False",
        "replace": "DEBUG = True"
      }
    ]
  }
}
```

**NEMESIS** : Demande confirmation, puis applique la modification

---

### Exemple 3 : Commande Interactive (sudo)

**Utilisateur** : "Mets à jour le système"

**IA** :
```json
{
  "tool": "bash",
  "parameters": {
    "command": "sudo -S apt update && sudo -S apt upgrade -y"
  }
}
```

**NEMESIS** :
```
⚠️ L'IA veut exécuter un outil :
  Outil: bash
  command: sudo -S apt update && sudo -S apt upgrade -y
  ⚠️ Cette commande peut demander des entrées supplémentaires (mot de passe, etc.)

Autoriser ? (y=oui une fois / n=non / a=toujours autoriser)
```

**Utilisateur** : `y`

**NEMESIS** :
```
[sudo] password for nemesis: 
⚠️ La commande attend une entrée :
  [sudo] password for nemesis: 
>>>
```

**Utilisateur** : (entre le mot de passe)

**Résultat** : La commande continue et met à jour le système

---

### Exemple 4 : Recherche Web

**Utilisateur** : "Recherche les meilleures pratiques Python asyncio 2024"

**IA** :
```json
{
  "tool": "web_search",
  "parameters": {
    "query": "Python asyncio best practices 2024"
  }
}
```

**NEMESIS** : Affiche les résultats de recherche

---

## Développement

### Ajouter un Nouvel Outil

1. **Définir le schéma** dans `tools_schema.py` :

```python
{
    "name": "mon_outil",
    "description": "Description de mon outil",
    "parameters": {
        "param1": "str - description du paramètre 1",
        "param2": "int - description du paramètre 2"
    },
    "handler_method": "execute_mon_outil"
}
```

2. **Implémenter le handler** dans `tools.py` :

```python
def execute_mon_outil(self, param1: str, param2: int):
    # Logique de l'outil
    result = {"success": True, "stdout": f"Résultat: {param1} - {param2}"}
    yield result
```

3. **Mettre à jour le parseur** dans `action_parser.py` si nécessaire

### Ajouter une Commande Slash

Dans `src/core/default_commands.py` :

```python
from src.core.commands import registry

@registry.register("ma_commande", "Description de ma commande")
def ma_commande_handler(args):
    # Logique de la commande
    return "Résultat de la commande"
```

### Structure d'un Skill MCP

Les skills MCP doivent être placés dans `tools_library/` avec :

1. Un fichier `SKILL.md` :
```yaml
---
name: MonSkill
description: Une description utile
version: 1.0.0
---
```

2. Un serveur MCP implémentant le protocole

---

## Dépannage

### Problèmes Courants

| Problème | Solution |
|----------|----------|
| `ModuleNotFoundError: yaml` | `pip install pyyaml` |
| `No module named 'rich'` | `pip install rich prompt_toolkit` |
| Erreur de connexion au provider | Vérifier `config.yaml` et le serveur IA |
| Action refusée | La commande n'est pas dans la liste blanche |
| Le collage ne fonctionne pas | Vérifier que `InMemoryClipboard` est supporté |

### Journalisation

NEMESIS génère des logs dans :
- `./workspace/` : Fichiers de sortie des outils
- Console : Messages de debug avec `--debug`

### Mode Debug

```bash
./venv/bin/python3 agent.py --debug
```

Affiche des informations détaillées sur :
- Les itérations d'outils
- Les réponses LLM
- Les appels d'outils
- Les erreurs

---

## Licence

**NEMESIS CLI** est un projet open-source développé par **TEJF - L'Aigle de la Justice**.

```
Copyright (c) 2024-2026 TEJF

Permission est accordée, gratuitement, à toute personne obtenant une copie
de ce logiciel et des fichiers de documentation associés (le "Logiciel"),
de traiter le Logiciel sans restriction, y compris sans limitation les droits
de l'utiliser, copier, modifier, fusionner, publier, distribuer, sous-licencier,
et/ou vendre des copies du Logiciel, et de permettre aux personnes auxquelles
le Logiciel est fourni de le faire, sous réserve que les conditions suivantes
soient remplies :

L'avis de copyright ci-dessus et cet avis de permission doivent être inclus
dans toutes les copies ou parties substantielles du Logiciel.

LE LOGICIEL EST FOURNI "EN L'ÉTAT", SANS GARANTIE D'AUCUNE SORTE, EXPLICITE
OU IMPLICITE, Y COMPRIS, SANS LIMITATION, LES GARANTIES DE QUALITÉ MARCHANDE,
D'ADÉQUATION À UN USAGE PARTICULIER ET DE NON-VIOLATION. EN AUCUN CAS LES
AUTEURS OU TITULAIRES DU COPYRIGHT NE SERONT TENUS RESPONSABLES DE TOUTE
RÉCLAMATION, DOMMAGES OU AUTRE RESPONSABILITÉ, QUE CE SOIT DANS UNE ACTION
DE CONTRAT, DE DÉLIT OU AUTRE, DÉCOULANT DE, OU EN RELATION AVEC LE LOGICIEL
OU L'UTILISATION OU AUTRES OPÉRATIONS AVEC LE LOGICIEL.
```

---

## Support

Pour toute question ou problème :
- Ouvrir une issue sur GitHub
- Contacter : TEJF - L'Aigle de la Justice

---

## Bot Telegram

NEMESIS propose également un bot Telegram qui permet d'utiliser toutes les fonctionnalités de l'agent directement depuis Telegram.

### Configuration du Bot Telegram

1. **Créer un bot Telegram** :
   - Ouvrez Telegram et recherchez @BotFather
   - Envoyez `/newbot` et suivez les instructions
   - Récupérez le token du bot

2. **Configurer le bot NEMESIS** :
   - Créez un fichier `telegram_config.yaml` :
     ```yaml
     token: "VOTRE_TOKEN_TELEGRAM"
     workspace: "./workspace"
     ```
   - Ou définissez la variable d'environnement :
     ```bash
     export TELEGRAM_BOT_TOKEN="votre_token"
     ```

3. **Démarrer le bot** :
   ```bash
   chmod +x run_telegram_bot.sh
   ./run_telegram_bot.sh
   ```

### Commandes du Bot Telegram

| Commande | Description |
|----------|-------------|
| `/start` | Démarrer le bot |
| `/help` | Affiche l'aide |
| `/tools` | Liste tous les outils disponibles |
| `/new` | Nouvelle conversation |
| `/clear` | Effacer l'historique |

### Commandes Rapides

Vous pouvez utiliser des commandes rapides directement dans le chat :

- `web_search:requête` - Effectuer une recherche web
- `web_fetch:url` ou `web_fetch:url|format` - Récupérer une page web
- `bash:commande` - Exécuter une commande bash
- `read:fichier` - Lire un fichier

### Exemple d'Utilisation

```
Utilisateur: web_search:Python asyncio best practices
Bot: [Retourne les résultats de recherche]

Utilisateur: bash:ls -la
Bot: [Retourne la liste des fichiers]

Utilisateur: read:config.yaml
Bot: [Retourne le contenu du fichier]
```

### JSON Tool Calls

Vous pouvez également envoyer des appels d'outils au format JSON :

```json
{
  "tool": "list_dir",
  "parameters": {
    "path": "."
  }
}
```

Le bot exécutera l'outil et retournera le résultat.

---

**Prêt à coder avec NEMESIS !** 🚀

*Documentation mise à jour le 5 août 2026*
