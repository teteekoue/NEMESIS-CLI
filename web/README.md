# NEMESIS Web

Interface web de NEMESIS, construite **sur le moteur CLI existant** (`agent.py`,
`action_parser.py`, `tools.py`, `src/core/*`). Aucune logique agent n'est
dupliquée : la boucle `_process_cycle`, le système d'autorisation `y / n / a`,
le parseur multi-niveaux, l'exécuteur d'outils, les commandes slash, MCP,
skills et sous-agents A2A sont ceux de la CLI.

Inspirée des harness web modernes (DeepSeek Harness) : timeline de
conversation avec appels d'outils repliables, onglet *Trajectoire*, panneau
latéral (Todo / Workspace / Sorties / Stats), sélecteur de mode d'accès et de
modèle dans le composer, barre de statistiques.

## Lancer

```bash
pip install -r requirements.txt        # ajoute fastapi + uvicorn
./nemesis-web                          # http://0.0.0.0:3080
# ou
python -m web.server --host 127.0.0.1 --port 3080
```

Variables : `NEMESIS_WEB_HOST`, `NEMESIS_WEB_PORT`, plus celles de la CLI
(`NEMESIS_CONFIG_DIR`, `NEMESIS_WORKSPACE`). La configuration lue/écrite est
**la même que la CLI** (`~/.config/nemesis-cli/config.yaml`).

### Sans serveur NEMAPI (démo)

```bash
python -m web.mock_nemapi --port 8090   # faux NEMAPI scripté (pas une IA)
./nemesis-web
```

Le mock rejoue quelques scénarios (« écris un script hello.py », « explore le
workspace », « supprime … » pour tester un refus) et permet de valider toute
l'interface : autorisations, todo, sorties bash, stats.

## Architecture

```
web/
├── engine.py      # Adaptateurs : EventConsole (Rich → HTML), WebComposer (E/S → événements)
├── sessions.py    # Session = 1 NemesisApp + 1 thread de travail + journal d'événements
├── server.py      # FastAPI : REST + WebSocket + fichiers statiques
├── mock_nemapi.py # Serveur NEMAPI de démonstration
└── static/        # index.html, app.css, app.js (vanilla, aucune étape de build)
```

### Comment le moteur CLI est réutilisé

`NemesisApp` attend deux surfaces d'E/S : `self.console` (Rich) et
`self.composer` (affichage + `prompt_input`). L'interface web injecte :

- **`EventConsole`** : une `rich.Console` en mode `record` ; chaque `print`
  est exporté en HTML (styles inline) et émis comme événement `system`. Les
  tableaux des commandes `/status`, `/help`, `/stats`, `/tools`… s'affichent
  donc à l'identique dans le navigateur. `console.input()` lève une erreur
  explicite (les commandes interactives — `/config`, `/mcp`, `/agents`… — ont
  leur équivalent dans le panneau ⚙ Paramètres).
- **`WebComposer`** : mêmes méthodes que `src.ui.composer.Composer`
  (`display_ai_message`, `display_tool_start`, `display_tool_result`,
  `display_thinking`, `display_auth`, `prompt_input`, …) mais émet des
  événements JSON. `prompt_input()` **bloque le thread de travail** jusqu'à
  la réponse de l'utilisateur (carte d'autorisation ou saisie), exactement
  comme la CLI bloque sur le terminal.

Le mode d'accès enveloppe `_ask_for_authorization` :

| Mode | Comportement |
|------|--------------|
| `ask` (défaut) | Comportement CLI : confirmation `y / n / a` pour les outils non-lecture. |
| `full` | Tout est autorisé sans confirmation. |
| `readonly` | Seuls les outils `risk == "read"` s'exécutent ; les autres sont refusés et le refus est renvoyé au modèle. |

### Événements

| type | contenu |
|------|---------|
| `ready` | provider, model, target, workspace |
| `user` / `assistant` | `text` (+ `command: true` pour une commande slash) |
| `thinking` | `active`, `message` |
| `tool_start` / `tool_result` | `call_id`, `tool`, `params`, `risk` / `success`, `output`, `edits`, `exit_code`, `output_id` |
| `auth_request` / `input_request` / `input_resolved` | `request_id`, … |
| `system` | `html` (rendu Rich) ou `text` + `level` |
| `error`, `summary`, `todo`, `meta`, `busy`, `clear` | |

Chaque événement porte un `seq` ; le WebSocket accepte `?since=<seq>` et
rejoue les événements manquants (reconnexion transparente). Les sessions sont
persistées dans `~/.config/nemesis-cli/web_sessions/` et consultables en
lecture seule après redémarrage.

## API

- `GET /api/state` — config, commandes slash, modes d'accès
- `GET|PUT /api/config`, `POST /api/config/test`, `GET /api/models`
- `GET /api/tools`, `GET /api/system-prompt`
- `GET|POST /api/sessions`, `GET|DELETE /api/sessions/{id}`
- `POST /api/sessions/{id}/message | respond | interrupt | access | model`
- `GET /api/sessions/{id}/outputs[/{output_id}]`, `/history`
- `WS /ws/sessions/{id}?since=N` — messages `message`, `respond`, `interrupt`, `access`, `ping`
- `GET /api/workspace/tree?path=`, `GET /api/workspace/file?path=`, `GET /api/todo`, `GET /api/git`
- `GET|POST /api/mcp`, `DELETE /api/mcp/{name}`, `POST /api/mcp/{name}/test`
- `GET /api/skills`, `GET /api/agents`
- Documentation interactive : `/api/docs`

## Raccourcis

- `Entrée` envoyer · `Shift+Entrée` nouvelle ligne · `Échap` interrompre
- `/` ouvre l'autocomplétion des commandes (↑ ↓ Tab)
- Pendant une autorisation, taper `y`, `n` ou `a` dans la zone de saisie répond directement

## Sécurité

L'interface expose l'exécution de commandes sur la machine hôte : ne l'exposez
pas sur un réseau non maîtrisé sans reverse-proxy authentifié. Par défaut
`./nemesis-web` écoute sur `0.0.0.0` (pratique pour un preview) ; utilisez
`--host 127.0.0.1` en local.
