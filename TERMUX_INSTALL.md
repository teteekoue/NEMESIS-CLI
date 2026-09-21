# Installation de NEMESIS CLI sur Termux (Android 32-bit)

Ce guide explique comment installer NEMESIS CLI sur un environnement Termux 32 bits.

## Pourquoi une installation spécifique ?

NEMESIS CLI dépend de plusieurs bibliothèques Python (comme `pydantic-core`, `lxml`, `pyyaml`, `markupsafe`) qui utilisent du code natif (C ou Rust). 
Sur un système 64 bits classique, un simple `pip install nemesis-cli` télécharge automatiquement des binaires pré-compilés de ces bibliothèques depuis internet. 
Cependant, pour les architectures **32 bits (ARMv7 ou Intel i686/i386)** (courantes sur les anciens téléphones Android ou les émulateurs PC), ces binaires n'existent souvent pas en ligne. Par conséquent, `pip` tenterait de recompiler ces dépendances directement sur votre appareil, ce qui échoue presque systématiquement.

Pour résoudre ce problème, nous fournissons deux archives "tout-en-un" (une pour ARM, l'autre pour Intel) contenant :
1. Le package de NEMESIS CLI (`.whl`).
2. **Tous les packages de ses dépendances** précompilés pour la bonne architecture.
3. Un script automatisé (`install_termux.sh`) pour une installation propre et hors-ligne.

---

## 1. Connaître son architecture

Dans Termux, tapez cette commande pour connaître l'architecture de votre appareil :
```bash
uname -m
```
- Si cela affiche `armv7l` ou `armv8l` (en mode 32-bit) : vous avez besoin de la version **ARMv7**.
- Si cela affiche `i686` ou `i386` (souvent le cas des émulateurs sur PC) : vous avez besoin de la version **Intel i386**.

---

## 2. Télécharger l'archive correspondante

Rendez-vous dans les [Releases du dépôt Github](https://github.com/teteekoue/NEMESIS-CLI/releases) et récupérez la bonne version.

**Pour ARMv7 :**
```bash
wget https://github.com/teteekoue/NEMESIS-CLI/releases/download/termux-armv7-v1.0/nemesis-termux-32bit-armv7.tar.gz
tar -xzf nemesis-termux-32bit-armv7.tar.gz
cd 32bit_armv7
```

**Pour Intel i386 (i686) :**
```bash
wget https://github.com/teteekoue/NEMESIS-CLI/releases/download/termux-i386-v1.0/nemesis-termux-32bit-i386.tar.gz
tar -xzf nemesis-termux-32bit-i386.tar.gz
cd 32bit_i386
```

---

## 3. Lancer l'installation

Une fois dans le dossier extrait, exécutez le script d'installation :

```bash
bash install_termux.sh
```

**Que fait ce script ?**
- Il s'assure que Termux est à jour (`pkg update`).
- Il installe Python et `libyaml` si ce n'est pas déjà fait.
- Il exécute `pip install` sur le projet **en utilisant uniquement les binaires locaux** situés dans le dossier `wheels/`.

---

## 4. Utilisation

Une fois l'installation terminée avec succès, vous pouvez lancer le bot n'importe où dans Termux en tapant :

```bash
nemesis
```
ou
```bash
nemesis-cli
```

Vous devrez probablement configurer vos clés d'API (comme décrit dans la documentation principale) pour que le bot puisse fonctionner correctement.
