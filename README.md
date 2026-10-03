# NEMESIS-CLI

**Un agent IA autonome qui pilote votre système Linux : il lit, écrit, exécute, cherche et automatise — sous votre contrôle total.**

Python  
Plateforme  
Outils  
Licence

Développé par **Ekoue TETE** (TEJF)

---

## 💡 Le projet en bref

NEMESIS est un **agent IA de codage et d'administration système** qui fonctionne dans le terminal. Vous décrivez une tâche en langage naturel ; l'IA choisit l'outil adapté, demande votre autorisation, exécute, puis poursuit à partir du résultat.

- **Autonome mais sous contrôle** : chaque action sensible passe par une confirmation explicite (`y` / `n` / `a`)
- **Multi-modèles** : compatible DeepSeek, Qwen, Claude et Gemini via la passerelle [NemApi](https://github.com/teteekoue/NemApi) (protocole OpenAI-compatible)
- **20+ outils** : fichiers, bash, recherche, processus, upload, recherche web
- **Extensible** : support du **Model Context Protocol (MCP)**, skills, sous-agents
- **Partout** : Linux (Ubuntu, Debian, Fedora) et même **Android via Termux**
- **Python 3.9+** : compatibilité testée et distribuée à partir de Python 3.9
- **Telegram** : pilotage complet de l'agent depuis un bot

---

## Table des Matières

1. [Vue d'Ensemble](#vue-densemble)
2. [Fonctionnalités Clés](#fonctionnalités-clés)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Utilisation](#utilisation)
6. [Système d'Autorisation](#système-dautorisation)
7. [Outils Disponibles](#outils-disponibles)
8. [Sécurité](#sécurité)
9. [Commandes Slash](#commandes-slash)
10. [Exemples d'Utilisation](#exemples-dutilisation)
11. [Bot Telegram](#bot-telegram)
12. [Développement](#développement)
13. [Dépannage](#dépannage)
14. [Licence](#licence)
15. [Réalisation &amp; Contact](#réalisation--contact)

---

## Vue d'Ensemble

**NEMESIS CLI** est un agent IA autonome de nouvelle génération conçu pour automatiser des tâches complexes sur les systèmes Linux. Il combine une intelligence artificielle avancée avec des capacités d'exécution système contrôlée, offrant une expérience utilisateur fluide et sécurisée.

### Capacités Principales

- Exécution de commandes système contrôlée et sécurisée
- Manipulation intelligente de fichiers (lecture, écriture, recherche/remplacement)
- Gestion de processus et tâches en arrière-plan
- Support du **Model Context Protocol (MCP)**
- Interface terminal moderne avec **Rich** et **prompt\_toolkit**
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

L'interface permet de coller du texte directement dans la barre de saisie :

- **Ctrl+V** : Coller depuis le presse-papiers
- Support natif via `InMemoryClipboard`
- Intégration transparente avec prompt\_toolkit

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

### Appels d'Outils par Lot

NEMESIS accepte un appel JSON unique ou un tableau JSON d'appels. Les opérations indépendantes de lecture/recherche peuvent ainsi être exécutées dans le même tour, tandis que les écritures dépendantes restent ordonnées. Le registre dynamique est la source canonique des noms, schémas et niveaux de risque exposés au CLI, à Telegram et aux sous-agents.

---

## Architecture

```text
nemesis-cli/
├── agent.py                 # Point d'entrée principal
├── cli.py                   # Lanceur de l'interface coding-agent alternative
├── action_parser.py         # Parseur multi-niveaux des réponses IA
├── tools.py                 # Exécuteur d'outils principal
├── tools_schema.py          # Schéma centralisé des outils disponibles
├── bridge_client.py         # Client pour la communication avec l'IA
├── uploader.py              # Gestion des uploads de fichiers
├── config.yaml              # Configuration locale (non commité)
├── mcp_config.yaml          # Configuration MCP (non commité)
├── prompt_system.txt        # Prompt système pour l'IA
├── install.sh               # Script d'installation
├── requirements.txt         # Dépendances Python
├── .gitignore               # Fichiers à exclure du versionnage
├── src/
│   ├── core/
│   │   ├── commands.py      # Système de commandes slash
│   │   ├── default_commands.py
│   │   ├── mcp_client.py     # Client MCP
│   │   ├── mcp_manager.py    # Gestionnaire MCP
│   │   ├── tool_registry.py  # Registre des outils
│   │   └── ...
│   └── ui/
│       ├── composer.py      # Orchestration I/O
│       ├── chat_ui.py       # Interface de chat
│       ├── header.py        # En-têtes et bannières
│       └── theme.py         # Thème Catppuccin
├── providers/
│   ├── base.py              # Provider de base
│   └── nemapi_v3.py         # Provider NEMAPI (nom public : NEMAPI)
├── tests/                   # Tests unitaires
└── tools_library/           # Bibliothèque de skills extensibles
```

---

## Installation

### Prérequis

- **OS** : Linux (testé sur Ubuntu, Debian, Fedora) ou Android/Termux
- **Python** : 3.10 ou supérieur
- **Mémoire** : 4 Go minimum recommandés
- **Espace disque** : 2 Go minimum

### Méthode 1 : Android / Termux (32 bits)

L'installation via Pip standard échoue sur les systèmes Termux ARMv7 car certaines dépendances natives ne sont pas pré-compilées. Un pack tout-en-un est préparé pour Termux.

👉 **Consultez le [Guide d'installation pour Termux (ARMv7)](TERMUX_INSTALL.md)** pour une installation simple et automatisée.

### Méthode 2 : Installation Standard (Linux/Mac/PC)

```bash
# 1. Cloner le dépôt
git clone https://github.com/teteekoue/NEMESIS-CLI.git
cd NEMESIS-CLI

# 2. Créer l'environnement virtuel
python3 -m venv venv

# 3. Activer l'environnement
source venv/bin/activate

# 4. Installer les dépendances
pip install -r requirements.txt

# 5. Lancer NEMESIS
./venv/bin/python3 agent.py
```

### Méthode 3 : Installation Rapide

```bash
chmod +x install.sh
./install.sh
```

Le script d'installation :

- Crée l'environnement virtuel
- Installe les dépendances
- Configure les fichiers de base

### Interface Coding-Agent Alternative

`nemesis-cli` utilise exactement le même moteur, les mêmes outils et les mêmes commandes que `nemesis`. Il fournit un point d'entrée stable, des options explicites pour le workspace et la configuration, et conserve le contexte conversationnel côté NemApi.

```bash
# Lanceur professionnel installé avec le paquet
./venv/bin/nemesis-cli

# Diagnostics et workspace explicite
./venv/bin/nemesis-cli --debug --workspace ~/projets/mon-app
```

### Diagnostic local

NEMESIS reste connecté à NemApi et conserve le contexte côté serveur. Lancez `/doctor` dans une session pour vérifier la configuration locale, les skills et la connectivité NemApi sans modifier le contexte courant.

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

NEMAPI expose la liste réelle de ses modèles via `GET /v1/models`. Utilisez `/config` pour modifier l'URL et le port du serveur, puis `/models` pour sélectionner un modèle officiel. Si la liste est indisponible, `/models` permet de saisir directement l'identifiant du modèle. La configuration peut laisser `model` vide pour utiliser le premier modèle retourné. NEMESIS envoie uniquement le message courant : l'historique et le contexte du prompt système sont conservés par NEMAPI.

Au démarrage, NEMESIS demande si le prompt système doit être renvoyé. Répondez `n` ou appuyez sur Entrée (valeur par défaut) pour poursuivre une session NEMAPI existante en envoyant uniquement le message utilisateur. Répondez `o` pour envoyer le prompt système une seule fois avant le premier message.

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
- **Saisie intelligente** avec prompt\_toolkit
- **Complétion automatique** pour les commandes slash
- **Historique des commandes**
- **Support du collage** (Ctrl+V)

### Flux de Travail Typique

1. **Lancer NEMESIS** : `./venv/bin/python3 agent.py`
2. **Poser une question** : par exemple, « Liste les fichiers Python dans /home/user »
3. **L'IA propose une action** : elle affiche le JSON de l'outil à exécuter
4. **Autorisation** : NEMESIS demande `Autoriser ? (y=oui une fois / n=non / a=toujours autoriser)`
5. **Exécution** : si autorisé, l'outil est exécuté et le résultat est affiché
6. **Feedback** : le résultat est envoyé à l'IA pour la suite

---

## Système d'Autorisation

### Fonctionnement

Avant chaque exécution d'outil, NEMESIS demande une confirmation explicite :

```text
⚠️ L'IA veut exécuter un outil :
  Outil: bash
  command: ls -la /home/user

Autoriser ? (y=oui une fois / n=non / a=toujours autoriser)
```

### Options


| Option | Description                          | Persistance |
| ------ | ------------------------------------ | ----------- |
| `y`    | Autoriser cette exécution uniquement | Non         |
| `n`    | Refuser l'exécution                  | Non         |
| `a`    | Autoriser pour toute la session      | Oui         |


### Avertissements Spéciaux

Pour les commandes potentiellement interactives (contenant `sudo`, `read`, `-p`), NEMESIS affiche un avertissement supplémentaire :

```text
⚠️ Cette commande peut demander des entrées supplémentaires (mot de passe, etc.)
```

---

## Outils Disponibles

NEMESIS supporte actuellement **20 outils** différents, organisés en catégories :

### Outils de Fichiers


| Outil          | Description                           | Paramètres                  |
| -------------- | ------------------------------------- | --------------------------- |
| `read_file`    | Lit un ou plusieurs fichiers          | `files: list[str]`          |
| `write_file`   | Crée ou écrase un fichier             | `path: str`, `content: str` |
| `append_file`  | Ajoute du contenu à un fichier        | `path: str`, `content: str` |
| `replace_file` | Recherche et remplace dans un fichier | `path: str`, `blocks: list` |


### Outils Bash


| Outil  | Description                | Paramètres                  |
| ------ | -------------------------- | --------------------------- |
| `bash` | Exécute une commande shell | `command: str`, `mode: str` |


**Modes disponibles** :

- `synchrone` (défaut) : exécution bloquante avec streaming
- `asynchrone` : exécution en arrière-plan

### Outils de Recherche


| Outil      | Description                          | Paramètres                  |
| ---------- | ------------------------------------ | --------------------------- |
| `grep`     | Recherche un motif dans des fichiers | `pattern: str`, `path: str` |
| `list_dir` | Liste le contenu d'un dossier        | `path: str`                 |


### Outils Système


| Outil           | Description                               | Paramètres  |
| --------------- | ----------------------------------------- | ----------- |
| `validate_code` | Valide la syntaxe d'un fichier            | `path: str` |
| `stop_all`      | Arrête tous les processus en arrière-plan | -           |
| `check_process` | Vérifie l'état d'un processus             | `pid: int`  |
| `kill_process`  | Tue un processus spécifique               | `pid: int`  |
| `cleanup_logs`  | Nettoie les logs des processus terminés   | -           |


### Outils MCP (Model Context Protocol)


| Outil            | Description                       | Paramètres                                    |
| ---------------- | --------------------------------- | --------------------------------------------- |
| `mcp_list`       | Liste les serveurs MCP installés  | -                                             |
| `mcp_tools_list` | Liste les outils d'un serveur MCP | `server: str`                                 |
| `mcp_call`       | Appelle un outil MCP              | `server: str`, `tool: str`, `arguments: dict` |


### Outils Divers


| Outil            | Description                     | Paramètres                                 |
| ---------------- | ------------------------------- | ------------------------------------------ |
| `web_search`     | Effectue une recherche web      | `query: str`                               |
| `upload`         | Upload un fichier               | `file_path: str`                           |
| `update_tracker` | Met à jour le tracker de tâches | `project: str`, `task: str`, `status: str` |


---

## Sécurité

### Principes de Sécurité

NEMESIS implémente plusieurs couches de sécurité :

1. **Workspace isolé** : toutes les opérations sont confinées dans `./workspace` par défaut
2. **Système d'autorisation** : confirmation explicite avant chaque exécution
3. **Validation de code** : vérification automatique de la syntaxe Python/Bash
4. **Conversion sudo** : `sudo` est automatiquement converti en `sudo -S` pour la lecture depuis stdin
5. **Limite de sortie** : les sorties sont tronquées à 10 000 000 caractères pour éviter les floods

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


| Commande   | Description                                                  |
| ---------- | ------------------------------------------------------------ |
| `/help`    | Affiche la liste des commandes disponibles                   |
| `/status`  | Affiche la connexion, le modèle, le endpoint et le workspace |
| `/todo`    | Affiche le plan de travail courant                           |
| `/models`  | Liste et sélectionne un modèle NEMAPI depuis `/v1/models`    |
| `/model`   | Alias de `/models`                                           |
| `/tools`   | Liste les outils disponibles                                 |
| `/config`  | Configure l'URL et le port du serveur NEMAPI                 |
| `/stats`   | Affiche les statistiques de session                          |
| `/history` | Consulte ou gère l'historique                                |
| `/reset`   | Réinitialise explicitement le contexte conservé par NemApi   |
| `/doctor`  | Vérifie la configuration locale et la connexion NemApi       |
| `/workspace` | Affiche le workspace actif                                  |
| `/agents`  | Gère les sous-agents (délégation)                            |
| `/skills`  | Gère les compétences additionnelles                          |
| `/clear`   | Réinitialise l'affichage du terminal                         |
| `/exit`    | Quitte NEMESIS                                               |


### Utilisation des Commandes Slash

```text
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

**Utilisateur** : « Explore le projet dans /home/user/myproject »

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

```text
⚠️ L'IA veut exécuter un outil :
  Outil: bash
  command: find /home/user/myproject -type f -name '*.py' | head -20

Autoriser ? (y=oui une fois / n=non / a=toujours autoriser)
```

**Utilisateur** : `y`

**Résultat** : liste des fichiers Python affichée en temps réel.

### Exemple 2 : Modifier un Fichier

**Utilisateur** : « Dans config.py, change DEBUG de False à True »

**IA** :

```json
{
  "tool": "read_file",
  "parameters": {
    "files": ["config.py"]
  }
}
```

**NEMESIS** : affiche le contenu de config.py

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

**NEMESIS** : demande confirmation, puis applique la modification.

### Exemple 3 : Commande Interactive (sudo)

**Utilisateur** : « Mets à jour le système »

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

```text
⚠️ L'IA veut exécuter un outil :
  Outil: bash
  command: sudo -S apt update && sudo -S apt upgrade -y
  ⚠️ Cette commande peut demander des entrées supplémentaires (mot de passe, etc.)

Autoriser ? (y=oui une fois / n=non / a=toujours autoriser)
```

**Utilisateur** : `y`, puis saisie du mot de passe quand le prompt apparaît.

**Résultat** : la commande continue et met à jour le système.

### Exemple 4 : Recherche Web

**Utilisateur** : « Recherche les meilleures pratiques Python asyncio »

**IA** :

```json
{
  "tool": "web_search",
  "parameters": {
    "query": "Python asyncio best practices"
  }
}
```

**NEMESIS** : affiche les résultats de recherche.

---

## Bot Telegram

NEMESIS propose également un bot Telegram qui permet d'utiliser toutes les fonctionnalités de l'agent directement depuis Telegram.

### Configuration du Bot

1. **Créer un bot Telegram** :
  - Ouvrez Telegram et recherchez @BotFather
  - Envoyez `/newbot` et suivez les instructions
  - Récupérez le token du bot
2. **Configurer le bot NEMESIS** — créez un fichier `telegram_config.yaml` :
  ```yaml
   token: "VOTRE_TOKEN_TELEGRAM"
   workspace: "./workspace"
  ```

   Ou définissez la variable d'environnement :
3. **Démarrer le bot** :
  ```bash
   chmod +x run_telegram_bot.sh
   ./run_telegram_bot.sh
  ```

### Commandes du Bot


| Commande | Description                       |
| -------- | --------------------------------- |
| `/start` | Démarrer le bot                   |
| `/help`  | Affiche l'aide                    |
| `/tools` | Liste tous les outils disponibles |
| `/new`   | Nouvelle conversation             |
| `/clear` | Effacer l'historique              |


### Commandes Rapides

- `web_search:requête` — effectuer une recherche web
- `web_fetch:url` ou `web_fetch:url|format` — récupérer une page web
- `bash:commande` — exécuter une commande bash
- `read:fichier` — lire un fichier

### Appels d'Outils au Format JSON

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


| Problème                        | Solution                                      |
| ------------------------------- | --------------------------------------------- |
| `ModuleNotFoundError: yaml`     | `pip install pyyaml`                          |
| `No module named 'rich'`        | `pip install rich prompt_toolkit`             |
| Erreur de connexion au provider | Vérifier `config.yaml` et le serveur IA       |
| Action refusée                  | La commande n'est pas dans la liste blanche   |
| Le collage ne fonctionne pas    | Vérifier que `InMemoryClipboard` est supporté |


### Journalisation

NEMESIS génère des logs dans :

- `./workspace/` : fichiers de sortie des outils
- Console : messages de debug avec `--debug`

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

## Réalisation &amp; Contact

Développé par **Ekoue TETE** — développeur web &amp; data scientist (Lomé, Togo), alias **TEJF - L'Aigle de la Justice**.

- 💼 GitHub : [github.com/teteekoue](https://github.com/teteekoue)
- 📱 WhatsApp : **+228 98 08 44 42** (réponse rapide)
- 🐛 Signaler un problème : ouvrez une [issue GitHub](https://github.com/teteekoue/NEMESIS-CLI/issues)

---

**Prêt à coder avec NEMESIS !** 🚀
