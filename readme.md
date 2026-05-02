# 📚 Documentation Complète - NEMESIS CLI & API Bridge

## 🌟 Vue d'ensemble du projet

Le projet **NEMESIS CLI** est un agent autonome en ligne de commande qui utilise **API Bridge** comme passerelle pour communiquer avec des intelligences artificielles mobiles gratuites (DeepSeek, ChatGPT, Claude, etc.). Il transforme un simple chatbot en un véritable agent capable d'exécuter des actions sur votre système (commandes bash, lecture/écriture de fichiers) de manière totalement autonome.

### Architecture globale

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   NEMESIS CLI   │────▶│   API Bridge     │────▶│   Application   │
│   (PC Linux)    │◀────│   (Android)      │◀────│   IA Mobile     │
└────────┬────────┘     └──────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│   Système de    │
│   fichiers PC   │
│   Commandes Bash│
└─────────────────┘
```

---

## 📦 Partie 1 : API Bridge (Android)

### 🎯 Objectif

**API Bridge** est une application Android qui expose n'importe quelle application d'IA mobile via une API HTTP locale. Elle utilise les services d'accessibilité pour simuler des interactions humaines.

### 🔧 Fonctionnement technique

| Composant | Rôle |
|-----------|------|
| `AccessibilityService` | Simule les clics sur l'écran |
| `NanoHTTPD` | Serveur HTTP embarqué sur le port 8080 |
| `ClipboardManager` | Lit/écrit dans le presse-papiers |
| `Overlay Service` | Bouton flottant de contrôle |

### 📡 Endpoint API

```
GET http://[IP_DU_TELEPHONE]:8080/ask?q=[QUESTION_ENCODEE]
```

**Exemple :**
```bash
curl "http://192.168.1.67:8080/ask?q=Quelle%20est%20la%20capitale%20de%20la%20France%3F"
```

**Réponse :**
```
Paris est la capitale de la France.
```

### 🔄 Séquence d'une requête

1. Réception de la requête HTTP
2. Clic sur la zone de saisie (calibrée)
3. Collage du texte dans le champ
4. Clic sur le bouton d'envoi
5. Attente de la génération de la réponse
6. Clic sur le bouton "Copier" de la réponse
7. Lecture du presse-papiers
8. Retour de la réponse via HTTP

### 📱 Calibration

La calibration définit les coordonnées d'écran pour :
- **Champ de saisie** : là où le texte est écrit
- **Bouton Envoyer** : pour soumettre la question
- **Bouton Copier** : sur le message de réponse de l'IA

### ⚠️ Limitations

- Téléphone doit rester **allumé et déverrouillé**
- L'application d'IA doit être **au premier plan**
- **Latence** : 5-30 secondes selon la longueur de la réponse
- **Une seule requête à la fois** (pas de parallélisme)

---

## 💻 Partie 2 : NEMESIS CLI (PC)

### 🎯 Objectif

**NEMESIS CLI** est un agent autonome qui orchestre des tâches complexes en dialoguant avec l'IA via API Bridge et en exécutant des actions sur le système local.

### 📁 Structure des fichiers

```
nemesis-cli/
├── agent.py              # Point d'entrée principal
├── bridge_client.py      # Client HTTP pour API Bridge
├── tools.py              # Exécuteur d'actions sécurisé
├── config.yaml           # Configuration
├── requirements.txt      # Dépendances Python
├── workspace/            # Bac à sable pour l'IA
└── history/              # Historique des conversations
```

### 🔧 Dépendances

```
requests>=2.28.0    # Requêtes HTTP
pyyaml>=6.0         # Parsing YAML
rich>=13.0.0        # Interface TUI
```

### ⚙️ Configuration (`config.yaml`)

```yaml
bridge:
  host: "192.168.1.67"    # IP du téléphone
  port: 8080              # Port de l'API Bridge
  timeout: 60             # Timeout en secondes

security:
  workspace: "./workspace"           # Dossier autorisé
  allowed_commands:                  # Commandes bash autorisées
    - ls, cat, grep, find, head, tail, wc, mkdir, cp, mv, echo, date, pwd
  forbidden_patterns:                # Patterns interdits
    - rm, >, >>, |, ;, &&, ||, $(
  ask_confirmation: "dangerous"      # always, dangerous, never
  max_file_size: 1048576             # 1 MB
  command_timeout: 30

agent:
  max_iterations: 15      # Évite les boucles infinies
  verbose: true           # Mode verbeux
  save_history: true      # Sauvegarde l'historique
  show_todo: true         # Affiche la todo-list
```

### 🚀 Lancement

```bash
# Installation
pip install -r requirements.txt

# Lancement
python agent.py
```

### 🎮 Interface interactive

```
╔══════════════════════════════════════════════════════════════╗
║   ███╗   ██╗███████╗███╗   ███╗███████╗███████╗██╗███████╗  ║
║   ████╗  ██║██╔════╝████╗ ████║██╔════╝██╔════╝██║██╔════╝  ║
║   ██╔██╗ ██║█████╗  ██╔████╔██║█████╗  ███████╗██║███████╗  ║
║   ██║╚██╗██║██╔══╝  ██║╚██╔╝██║██╔══╝  ╚════██║██║╚════██║  ║
║   ██║ ╚████║███████╗██║ ╚═╝ ██║███████╗███████║██║███████║  ║
║   ╚═╝  ╚═══╝╚══════╝╚═╝     ╚═╝╚══════╝╚══════╝╚═╝╚══════╝  ║
║                     C O M M A N D   L I N E                  ║
╚══════════════════════════════════════════════════════════════╝

✅ NEMESIS CLI est prêt !
──────────────────────────────────────────────────

💬 Vous: Trouve tous les fichiers .txt modifiés cette semaine
```

### 🤖 Protocole de communication avec l'IA

L'agent envoie à chaque message un **prompt système** qui définit le format d'échange :

```
Tu es un agent autonome NEMESIS capable d'exécuter des tâches complexes.

PROTOCOLE DE COMMUNICATION :

1. Pour chaque mission, établis un plan :
   <TODO>
   1. Première étape
   2. Deuxième étape
   </TODO>

2. Pour agir, utilise UNE balise par réponse :
   <ACTION type="bash">commande</ACTION>
   <ACTION type="read">fichier</ACTION>
   <ACTION type="write">fichier|contenu</ACTION>

3. Mets à jour ta <TODO> avec :
   [✓] réussi, [✗] échoué, [→] en cours

4. Quand tout est [✓], donne ta réponse finale sans balise.
```

### 🔄 Boucle d'exécution

```
┌─────────────────────────────────────────────────────────────┐
│                     BOUCLE D'EXÉCUTION                      │
├─────────────────────────────────────────────────────────────┤
│  1. Envoi du message utilisateur + prompt système           │
│                        ↓                                    │
│  2. Réception de la réponse de l'IA                         │
│                        ↓                                    │
│  3. Parsing (extraction <TODO> et <ACTION>)                 │
│                        ↓                                    │
│  4. Affichage formaté de la réponse                         │
│                        ↓                                    │
│  5. Si <ACTION> présente :                                  │
│     → Validation de sécurité                                │
│     → Exécution via tools.py                                │
│     → Formatage du feedback                                 │
│     → Retour à l'étape 1 avec le feedback                   │
│                        ↓                                    │
│  6. Sinon : Fin de la tâche                                 │
└─────────────────────────────────────────────────────────────┘
```

### 🛠️ Module `tools.py` - Exécuteur d'actions

| Action | Description | Format |
|--------|-------------|--------|
| `bash` | Exécute une commande shell | `<ACTION type="bash">ls -la</ACTION>` |
| `read` | Lit un fichier | `<ACTION type="read">config.json</ACTION>` |
| `write` | Écrit un fichier | `<ACTION type="write">fichier.txt\|contenu</ACTION>` |

**Sécurités intégrées :**
- Workspace isolé (`./workspace`)
- Liste blanche de commandes
- Patterns interdits (`rm`, `>`, `|`, `;`, `&&`, etc.)
- Timeout d'exécution
- Taille maximale des fichiers

### 📊 Exemple de conversation

**Utilisateur :**
```
Trouve tous les fichiers .txt dans le workspace
```

**IA (réponse 1) :**
```
<TODO>
1. Lister les fichiers .txt
2. Présenter les résultats
</TODO>

<ACTION type="bash">find . -name "*.txt"</ACTION>
```

**Système (feedback) :**
```
<action type="bash">find . -name "*.txt"</action>
<output>notes.txt
rapport.txt</output>
<error></error>
<success>true</success>
```

**IA (réponse 2) :**
```
<TODO>
[✓] 1. Lister les fichiers .txt
[✓] 2. Présenter les résultats
</TODO>

J'ai trouvé 2 fichiers .txt dans le workspace :
- notes.txt
- rapport.txt
```

---

## 🔒 Sécurité

### Niveaux de protection

| Niveau | Description |
|--------|-------------|
| **Workspace isolé** | L'IA ne peut pas accéder aux dossiers système |
| **Liste blanche** | Seules les commandes autorisées sont exécutables |
| **Patterns interdits** | Bloque les redirections, pipes, et commandes dangereuses |
| **Confirmation** | Demande validation avant les actions risquées |
| **Timeout** | Limite le temps d'exécution des commandes |
| **Taille limite** | Empêche la lecture de fichiers trop volumineux |

### Modes de confirmation

| Mode | Comportement |
|------|--------------|
| `always` | Confirme chaque action |
| `dangerous` | Confirme seulement les actions risquées |
| `never` | Aucune confirmation (déconseillé) |

---

## 🚀 Cas d'utilisation

### 1. Analyse de logs
```
💬 Vous: Analyse les logs d'erreur dans le dossier logs/
```
L'IA va lister, filtrer, compter et générer un rapport.

### 2. Organisation de fichiers
```
💬 Vous: Classe les images par date dans des dossiers mois/année
```
L'IA va créer l'arborescence et déplacer les fichiers.

### 3. Génération de documentation
```
💬 Vous: Génère un README.md listant tous les scripts Python
```
L'IA va scanner, analyser et rédiger la documentation.

---

## 🐛 Dépannage

### Problèmes courants

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| "Connection refused" | Téléphone non connecté | Vérifier l'IP et le WiFi |
| Réponse "OK" uniquement | Prompt système non envoyé | Vérifier `_process_message()` |
| Timeout | IA trop lente | Augmenter `timeout` dans config |
| "Commande non autorisée" | Commande hors liste blanche | Ajouter à `allowed_commands` |
| Écran noir sur téléphone | Verrouillage automatique | Désactiver la mise en veille |

### Logs et historique

Les conversations sont sauvegardées dans `./history/` :
```
history/
├── 20260122_143052.json
├── 20260122_150315.json
└── ...
```

---

## 📈 Performances

| Métrique | Valeur typique |
|----------|----------------|
| Latence par requête | 5-30 secondes |
| Itérations par tâche | 3-10 |
| Tâche simple | 30-60 secondes |
| Tâche complexe | 2-5 minutes |

---

## 🔮 Évolutions possibles

- [ ] Support de plusieurs sessions parallèles
- [ ] Interface Web complémentaire
- [ ] Plugins pour actions personnalisées
- [ ] Mode "headless" pour scripts
- [ ] Support d'autres applications IA
- [ ] Export des résultats en PDF/HTML

---

## 📝 Licence et crédits

Ce projet est destiné à un usage **personnel et éducatif**. Respectez les conditions d'utilisation des applications d'IA que vous interfacez.

**Auteur :** NEMESIS
**Version :** 1.0.0

---

*Documentation générée le 22 janvier 2026*