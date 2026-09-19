# NEMESIS - Documentation du Projet

## Vue d'ensemble

NEMESIS est un agent de codage autonome en CLI, spécialisé dans l'ingénierie logicielle et l'administration système sur Linux. Il utilise une architecture modulaire avec des providers LLM, des outils système et un système de subagents via le protocole A2A.

## Architecture

### Composants principaux

- **`agent.py`** : Point d'entrée principal, classe `NemesisApp`
- **`providers/`** : Provider NEMAPI unique, avec contexte conservé côté serveur
- **`src/core/`** : Logique métier (outils, commandes, A2A, MCP)
- **`src/ui/`** : Interface utilisateur avec Rich
- **`tools/`** : Outils système et exécuteur

### Provider

| Provider | Description |
|----------|-------------|
| `nemapi` | Provider unique NEMAPI, contexte serveur et modèles via `/v1/models` |

### Subagents (A2A)

Le système de subagents utilise le protocole A2A (Agent-to-Agent) pour la délégation de tâches.

**Fichiers clés :**
- `src/core/agent_manager.py` : Gestion des subagents
- `src/core/a2a_protocol.py` : Protocole A2A
- `agents.json` : Configuration des subagents

**Subagent actuel :**
- Nom : Agent1
- Provider : nemapi
- Modèle : sélectionné depuis `/v1/models`
- Statut : outils exécutés par le bridge partagé

## État technique

- Les réponses JSON et SSE de NEMAPI sont normalisées par le provider.
- Le prompt système est envoyé une seule fois au début de la session.
- Les appels d'outils sont exécutés par le bridge partagé, pour l'agent
  principal comme pour les sous-agents.
- Le contexte conversationnel reste côté serveur NEMAPI ; aucun historique
  complet n'est reconstruit côté client.

## Configuration

### config.yaml

```yaml
provider:
  type: nemapi
  model: qwen-chat

nemapi:
  host: 127.0.0.1
  port: 8090

security:
  workspace: ./workspace
```

### agents.json

Les sous-agents utilisent la même instance NEMAPI et le même contexte serveur
que l'agent principal. Aucun token de fournisseur n'est requis par NEMESIS.

## Commandes disponibles

| Commande | Description |
|----------|-------------|
| `/help` | Affiche les commandes disponibles |
| `/clear` | Efface l'écran |
| `/config` | Configure l'URL et le port du serveur NEMAPI |
| `/models` | Liste et sélectionne un modèle officiel, ou saisie manuelle |
| `/stats` | Statistiques de session |
| `/agents` | Gestion des subagents |
| `/delegate <agent> <instruction>` | Délègue une tâche |
| `/tools` | Liste des outils disponibles |
| `/show` | Affiche les sorties cachées |

## État actuel

- NEMAPI est le seul provider public.
- Les modèles sont récupérés dynamiquement depuis `/v1/models`.
- NEMAPI conserve le contexte ; le client n'envoie pas tout l'historique à
  chaque tour.
- Le parseur accepte les appels JSON, XML/Qwen, groupés et tronqués.

## Notes de développement

- Le projet utilise Python 3.12+
- L'interface utilisateur utilise la bibliothèque `rich`
- Le protocole A2A est basé sur JSON
- Les subagents sont configurés via `agents.json`

---

*Document mis à jour le 18 septembre 2026*
