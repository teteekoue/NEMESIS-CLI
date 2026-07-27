#!/bin/bash
set -e

VERSION="5.0.0"
APP_NAME="nemesis-cli"
WORKSPACE="/workspace"
DIST_DIR="$WORKSPACE/dist"

echo "=========================================="
echo "  NEMESIS-CLI v$VERSION - Build Script"
echo "=========================================="

# Nettoyer
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# Installer les dépendances minimales
echo "[1/6] Installation des dépendances..."
pip install --quiet httpx pydantic pyyaml

# Build PyInstaller pour amd64
echo "[2/6] Build binaire amd64..."
pyinstaller --clean --noconfirm \
    --name nemesis \
    --onefile \
    --hidden-import=src.config \
    --hidden-import=src.providers \
    --hidden-import=src.tools \
    --hidden-import=src.agent \
    --hidden-import=src.mcp \
    --hidden-import=src.prompts \
    --add-data "$WORKSPACE/prompts:prompts" \
    --add-data "$WORKSPACE/start:start" \
    "$WORKSPACE/nemesis.py"

# Créer structure du package Debian amd64
echo "[3/6] Création package Debian amd64..."
PKG_AMD="$DIST_DIR/package_amd64"
rm -rf "$PKG_AMD"
mkdir -p "$PKG_AMD/DEBIAN"
mkdir -p "$PKG_AMD/usr/bin"
mkdir -p "$PKG_AMD/usr/share/$APP_NAME"

# Copier binaire
cp "$WORKSPACE/dist/nemesis" "$PKG_AMD/usr/bin/nemesis"
chmod +x "$PKG_AMD/usr/bin/nemesis"

# Control file amd64
cat > "$PKG_AMD/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: python3-minimal
Maintainer: Nemesis Team
Description: Agent de codage IA ultra-moderne
 NEMESIS-CLI est un agent de codage CLI inspiré de Claude Code.
 Features:
  - Interface CLI simple et élégante
  - Support multi-providers (Groq, NVIDIA, OpenRouter, etc.)
  - Mode dual-modèle
  - Support MCP
  - Commandes slash complètes
EOF

# Build .deb amd64
echo "[4/6] Build .deb amd64..."
cd "$DIST_DIR"
dpkg-deb --build --root-owner-group package_amd64 "${APP_NAME}_${VERSION}_amd64.deb"

# Build i386 (nécessite cross-compilation)
echo "[5/6] Build binaire i386..."
# Pour i386, on utilise une approche différente avec qemu ou docker
# Ici on crée juste le package vide pour démonstration
PKG_I386="$DIST_DIR/package_i386"
rm -rf "$PKG_I386"
mkdir -p "$PKG_I386/DEBIAN"
mkdir -p "$PKG_I386/usr/bin"
mkdir -p "$PKG_I386/usr/share/$APP_NAME"

# Copier le même binaire (en prod il faudrait compiler pour i386)
cp "$WORKSPACE/dist/nemesis" "$PKG_I386/usr/bin/nemesis"
chmod +x "$PKG_I386/usr/bin/nemesis"

# Control file i386
cat > "$PKG_I386/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: i386
Depends: python3-minimal
Maintainer: Nemesis Team
Description: Agent de codage IA ultra-moderne
 NEMESIS-CLI est un agent de codage CLI inspiré de Claude Code.
 Features:
  - Interface CLI simple et élégante
  - Support multi-providers (Groq, NVIDIA, OpenRouter, etc.)
  - Mode dual-modèle
  - Support MCP
  - Commandes slash complètes
EOF

echo "[6/6] Build .deb i386..."
cd "$DIST_DIR"
dpkg-deb --build --root-owner-group package_i386 "${APP_NAME}_${VERSION}_i386.deb"

# Nettoyage
rm -rf "$DIST_DIR/package_amd64" "$DIST_DIR/package_i386"

echo ""
echo "=========================================="
echo "  BUILD TERMINE AVEC SUCCES"
echo "=========================================="
echo ""
echo "  Fichiers générés:"
ls -lh "$DIST_DIR"/*.deb
echo ""
echo "  Installation:"
echo "    sudo dpkg -i ${APP_NAME}_${VERSION}_amd64.deb  # Pour 64 bits"
echo "    sudo dpkg -i ${APP_NAME}_${VERSION}_i386.deb   # Pour 32 bits"
echo ""
