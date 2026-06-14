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

```bash
# 1. Cloner le dépôt
git clone [URL_DU_PROJET]
cd nemesis-cli