# NEMESIS - Documentation du Projet

## Vue d'ensemble

NEMESIS est un agent de codage autonome en CLI, spécialisé dans l'ingénierie logicielle et l'administration système sur Linux. Il utilise une architecture modulaire avec des providers LLM, des outils système et un système de subagents via le protocole A2A.

## Architecture

### Composants principaux

- **`agent.py`** : Point d'entrée principal, classe `NemesisApp`
- **`providers/`** : Providers LLM (bridge, nemapi-v3, openai-compatible, etc.)
- **`src/core/`** : Logique métier (outils, commandes, A2A, MCP)
- **`src/ui/`** : Interface utilisateur avec Rich
- **`tools/`** : Outils système et exécuteur

### Providers

| Provider | Description |
|----------|-------------|
| `bridge` | API Bridge Android (polling) |
| `nemapi-v3` | API NEMAPI v3 (Firefox extension) |
| `openai-compatible` | Providers compatibles OpenAI (Groq, Nvidia, etc.) |
| `ollama` | Ollama local |

### Subagents (A2A)

Le système de subagents utilise le protocole A2A (Agent-to-Agent) pour la délégation de tâches.

**Fichiers clés :**
- `src/core/agent_manager.py` : Gestion des subagents
- `src/core/a2a_protocol.py` : Protocole A2A
- `agents.json` : Configuration des subagents

**Subagent actuel :**
- Nom : Agent1
- Provider : custom (NEMAPI v3)
- Modèle : gemini-chat
- Statut : fonctionnel pour la génération de texte, mais problème d'exécution d'outils

## Problèmes connus

### 1. Erreur `'str' object has no attribute 'choices'`

**Description :** Le provider NEMAPI v3 renvoie des réponses en streaming (SSE) même avec `stream: false`. Le code attend un objet avec `choices`.

**Statut :** Partiellement résolu - gestion du streaming ajoutée dans `nemapi_v3.py`

**Fichiers touchés :**
- `providers/nemapi_v3.py` : Traitement SSE
- `src/core/agent_manager.py` : Vérification de type

### 2. Prompt système envoyé automatiquement

**Description :** Le prompt système était envoyé automatiquement sans demande d'autorisation.

**Statut :** Résolu - demande d'autorisation ajoutée dans `agent.py`

### 3. Subagent ne peut pas exécuter d'outils

**Description :** Le subagent Agent1 génère des appels d'outil (`write_file`) mais ne peut pas les exécuter. Le fichier n'est jamais créé.

**Statut :** Non résolu

**Cause probable :**
- L'appel d'outil est renvoyé comme réponse directe et non exécuté
- Le mécanisme de feedback n'est pas bouclé correctement
- L'exécuteur n'est pas correctement intégré dans le flux du subagent

**Fichiers concernés :**
- `src/core/agent_manager.py` : `A2AAgentClient.send_message()`, `_execute_task_loop()`
- `src/core/tool_bridge.py` : `execute_tool()`
- `agent.py` : Injection de l'exécuteur

### 4. Réponses en streaming non assemblées

**Description :** Le provider NEMAPI v3 renvoie des chunks SSE qui ne sont pas toujours correctement assemblés.

**Statut :** Résolu - extraction du contenu des chunks SSE

**Fichiers touchés :**
- `providers/nemapi_v3.py` : `send_message()` avec traitement SSE

## Modifications récentes

### 22 août 2026

1. **`providers/nemapi_v3.py`**
   - Ajout du traitement SSE pour les réponses streaming
   - Détection JSON vs streaming

2. **`src/core/agent_manager.py`**
   - Ajout de `executor` et `_tools_cache` dans `A2AAgentClient`
   - Ajout de `set_executor()` et `set_tools()`
   - Modification de `send_message()` pour les appels d'outil
   - Ajout de `_execute_task_loop()`
   - Ajout de `set_executor()` dans `A2ATaskScheduler`

3. **`agent.py`**
   - Injection de l'exécuteur dans le scheduler A2A
   - Demande d'autorisation pour le prompt système

4. **`src/core/default_commands.py`**
   - Ajout des commandes `/agents` et `/delegate`

## Configuration

### config.yaml

```yaml
bridge:
  host: 192.168.1.66
  port: 8080

provider:
  type: nemapi-v3
  model: deepseek-chat

nemapi_v3:
  host: 127.0.0.1
  port: 8080

security:
  workspace: ./workspace
```

### agents.json

```
{
  "Agent1": {
    "api_key": "rien",
    "provider": "custom",
    "model": "gemini-chat",
    "base_url": "http://127.0.0.1:8080/v1"
  }
}
```

## Commandes disponibles

| Commande | Description |
|----------|-------------|
| `/help` | Affiche les commandes disponibles |
| `/clear` | Efface l'écran |
| `/config` | Affiche la configuration |
| `/stats` | Statistiques de session |
| `/agents` | Gestion des subagents |
| `/delegate <agent> <instruction>` | Délègue une tâche |
| `/tools` | Liste des outils disponibles |
| `/show` | Affiche les sorties cachées |

## Prochaines étapes

1. **Résoudre l'exécution des outils pour les subagents**
   - Implémenter un mécanisme de feedback correct
   - Boucler l'appel d'outil → résultat → continuation

2. **Améliorer la robustesse du provider NEMAPI v3**
   - Gérer tous les formats de réponse possibles
   - Meilleure gestion des erreurs

3. **Documentation**
   - Ajouter des exemples d'utilisation
   - Documenter le protocole A2A

## Notes de développement

- Le projet utilise Python 3.12+
- L'interface utilisateur utilise la bibliothèque `rich`
- Le protocole A2A est basé sur JSON
- Les subagents sont configurés via `agents.json`

---

*Document mis à jour le 22 août 2026*
