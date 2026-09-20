# Installation de NEMESIS CLI sur Termux (Android 32-bit / ARMv7)

Ce guide explique comment installer NEMESIS CLI sur un environnement Termux 32 bits.

## Pourquoi une installation spécifique ?

NEMESIS CLI dépend de plusieurs bibliothèques Python (comme `pydantic-core`, `lxml`, `pyyaml`, `markupsafe`) qui utilisent du code natif (C ou Rust). 
Sur un système 64 bits classique, un simple `pip install nemesis-cli` télécharge automatiquement des binaires pré-compilés de ces bibliothèques depuis internet. 
Cependant, pour l'architecture **ARMv7 32 bits** (courante sur les anciens téléphones Android ou certaines installations Termux), ces binaires n'existent souvent pas en ligne. Par conséquent, `pip` tenterait de recompiler ces dépendances directement sur votre téléphone, ce qui échoue presque systématiquement à cause du manque d'outils de compilation complets, de RAM, ou d'incompatibilités avec l'environnement Android.

Pour résoudre ce problème, nous fournissons une archive "tout-en-un" contenant :
1. Le package de NEMESIS CLI (`.whl`).
2. **Tous les packages de ses dépendances** compilés nativement pour l'architecture ARMv7 32 bits.
3. Un script automatisé qui force `pip` à utiliser ces fichiers locaux au lieu de chercher sur internet.

---

## Étapes d'installation

### 1. Télécharger l'archive

Téléchargez le fichier `nemesis-termux-32bit-armv7.tar.gz` disponible dans les [Releases du dépôt Github](https://github.com/teteekoue/NEMESIS-CLI/releases).
Vous pouvez utiliser `wget` ou `curl` depuis Termux :

```bash
wget https://github.com/teteekoue/NEMESIS-CLI/releases/latest/download/nemesis-termux-32bit-armv7.tar.gz
```
*(Remplacez l'URL par le lien exact de la release si nécessaire)*

### 2. Extraire l'archive

Une fois le fichier téléchargé, extrayez-le à l'aide de la commande `tar` :

```bash
tar -xzf nemesis-termux-32bit-armv7.tar.gz
```

Cela créera un dossier nommé `32bit_armv7`.

### 3. Lancer l'installation

Allez dans le dossier extrait et exécutez le script d'installation :

```bash
cd 32bit_armv7
bash install_termux.sh
```

**Que fait ce script ?**
- Il s'assure que Termux est à jour (`pkg update`).
- Il installe Python, Pip et `libyaml` si ce n'est pas déjà fait.
- Il met à jour `pip`.
- Il exécute `pip install` sur le projet **en utilisant uniquement les binaires locaux** situés dans le dossier `wheels/`.

### 4. Utilisation

Une fois l'installation terminée avec succès, vous pouvez lancer le bot n'importe où dans Termux en tapant :

```bash
nemesis
```
ou
```bash
nemesis-cli
```

Vous devrez probablement configurer vos clés d'API (comme décrit dans la documentation principale) pour que le bot puisse fonctionner correctement.
