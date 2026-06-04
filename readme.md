# 🚀 NEMESIS CLI v2.0.0 (Modulaire)

**NEMESIS CLI** est un agent IA autonome de nouvelle génération pour Linux, conçu pour automatiser des tâches complexes en orchestrant des outils système locaux et des capacités de raisonnement LLM avancées.

---

## 📋 Table des Matières

1. [Vue d'ensemble](#-vue-densemble)
2. [Architecture](#-architecture)
3. [Prérequis](#-prérequis)
4. [Installation](#-installation)
5. [Configuration](#-configuration)
6. [Utilisation](#-utilisation)
7. [Sécurité et Bac à sable](#-sécurité-et-bac-à-sable)
8. [Développement et Extensibilité](#-développement-et-extensibilité)
9. [Dépannage](#-dépannage)

---

## 🌟 Vue d'ensemble

NEMESIS CLI n'est pas qu'un simple chatbot. C'est un **agent opérationnel** capable de :
*   Exécuter des commandes système de manière contrôlée.
*   Manipuler des fichiers avec intelligence (lecture, écriture, recherche/remplacement complexe).
*   Déléguer des tâches à d'autres agents spécialisés.
*   S'étendre via des *Skills* dynamiques.
*   Dialoguer avec des modèles LLM modernes (via Groq/Llama-3).

---

## 🏗️ Architecture

Le projet a été entièrement refactorisé en une architecture modulaire :

*   `src/core/` : Cœur métier (gestionnaire d'agents, registre de commandes, client MCP).
*   `src/ui/` : Interface utilisateur basée sur `rich` et `prompt_toolkit`.
*   `tools_library/` : Bibliothèque de *Skills* extensibles.
*   `workspace/` : Environnement de travail sécurisé (bac à sable).

```mermaid
graph TD
    A[Utilisateur] --> B[Interface TUI]
    B --> C[Agent Manager]
    C --> D[Groq LLM]
    C --> E[Action Executor]
    E --> F[Workspace (Sandbox)]
    E --> G[Skills Library]
```

---

## 🛠️ Prérequis

- **OS** : Linux
- **Python** : 3.10+
- **Outils système** : `tree` (pour l'exploration de fichiers), `LibreOffice` (pour les conversions PDF).

---

## ⚙️ Installation

### Option 1 : Installation du binaire (Recommandé)
Vous pouvez installer le paquet directement via l'URL de la dernière release :

```bash
curl -LO https://github.com/teteekoue/NEMESIS-CLI/releases/latest/download/nemesis-cli_2.0.0_i386.deb && sudo apt install ./nemesis-cli_2.0.0_i386.deb
```

### Option 2 : Installation depuis les sources
```bash
# 1. Cloner le dépôt
git clone https://github.com/teteekoue/NEMESIS-CLI
cd NEMESIS-CLI

# 2. Lancer le script d'installation
chmod +x install.sh
./install.sh

# 3. Lancer l'agent
./nemesis-cli
```

---

## ⚙️ Configuration (`config.yaml`)

Le fichier `config.yaml` contrôle le comportement de l'agent :
*   **bridge** : Connexion à l'interface d'IA externe.
*   **security** : Définition du `workspace` et liste des commandes autorisées.

---

## 💡 Utilisation

### Commandes Slash (Intégrées)
Lors de l'utilisation de l'interface, tapez `/` pour accéder aux commandes :
*   `/help` : Liste les commandes.
*   `/agents` : Gérer les sous-agents (délégation).
*   `/skills` : Gérer les compétences additionnelles.
*   `/stats` : Voir les métriques de la session.

### Protocole IA
L'agent utilise des balises pour agir :
- `<ACTION type="bash">...</ACTION>`
- `<ACTION type="write">fichier|contenu</ACTION>`
- `<ACTION type="read">fichier</ACTION>`

---

## 🔒 Sécurité et Bac à sable

*   **Workspace isolé** : L'IA est confinée dans `./workspace`.
*   **Liste blanche** : Seules les commandes autorisées sont exécutées.
*   **Protection de syntaxe** : Le système `replace` utilise des mesures de similarité (Levenshtein) pour éviter les erreurs de modification.
*   **Validation** : Chaque écriture de code Python/Bash est automatiquement vérifiée.

---

## 🛠️ Développement et Extensibilité

### Ajouter une commande
Enregistrez-la dans `src/core/default_commands.py` :
```python
@registry.register("nom", "Description")
def ma_fonction():
    # Logique
```

### Ajouter un Skill
Placez votre dossier de skill dans `tools_library/` avec un fichier `SKILL.md` contenant :
```yaml
---
name: MonSkill
description: Une description utile
version: 1.0.0
---
```

---

## 🐛 Dépannage

- **Erreur de connexion** : Vérifiez votre configuration `config.yaml`.
- **Action refusée** : La commande n'est peut-être pas dans la liste blanche (vérifiez `tools.py`).
- **Logs** : Consultez les fichiers générés dans `./workspace` ou via `/status`.

---

*Documentation mise à jour le 27 mai 2026*
