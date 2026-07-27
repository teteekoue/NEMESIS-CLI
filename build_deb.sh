#!/bin/bash
set -e
VERSION="4.0.0"
DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD="$DIR/build_deb"
DIST="$DIR/dist"

function build_for() {
    local ARCH_LABEL=$1 DEB_ARCH=$2
    echo ""
    echo "================================================"
    echo "  Build ${ARCH_LABEL} -> nemesis-cli_${VERSION}_${DEB_ARCH}.deb"
    echo "================================================"

    local BD="$BUILD/${DEB_ARCH}"
    local PKG="$BD/pkg/nemesis-cli_${VERSION}_${DEB_ARCH}"
    rm -rf "$BD"
    mkdir -p "$BD/dist" "$BD/work" "$PKG/DEBIAN" "$PKG/usr/bin"

    # --- PyInstaller onefile: tout empaquetté dans un seul binaire ---
    cd "$DIR"
    pyinstaller --clean --onefile \
        --distpath "$BD/dist" \
        --workpath "$BD/work" \
        --name nemesis \
        --hidden-import=httpx \
        --hidden-import=httpx._transports.default \
        --hidden-import=httpcore \
        --hidden-import=h11 \
        --hidden-import=anyio \
        --hidden-import=rich \
        --hidden-import=rich.console \
        --hidden-import=rich.markdown \
        --hidden-import=rich.panel \
        --hidden-import=prompt_toolkit \
        --hidden-import=pydantic \
        --hidden-import=yaml \
        --hidden-import=textual \
        --hidden-import=textual.app \
        --hidden-import=textual.widgets \
        --hidden-import=src.config \
        --hidden-import=src.providers \
        --hidden-import=src.tools \
        --hidden-import=src.agent \
        --hidden-import=src.mcp \
        --hidden-import=src.ui \
        --hidden-import=src.commands \
        --hidden-import=src.tui \
        --add-data "prompts:prompts" \
        --add-data "src:src" \
        nemesis.py 2>&1 | tail -10

    # Copier le binaire onefile directement dans /usr/bin
    if [ ! -f "$BD/dist/nemesis" ]; then
        echo "ERREUR: binaire non trouvé: $BD/dist/nemesis"
        return 1
    fi
    cp "$BD/dist/nemesis" "$PKG/usr/bin/nemesis"
    chmod +x "$PKG/usr/bin/nemesis"

    # --- Control file ---
    local SIZE
    SIZE=$(du -sk "$PKG" | cut -f1)
    cat > "$PKG/DEBIAN/control" << CTRLEOF
Package: nemesis-cli
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${DEB_ARCH}
Installed-Size: ${SIZE}
Depends: libc6 (>= 2.31), libssl3, ca-certificates
Maintainer: teteekoue <teteekoue@users.noreply.github.com>
Description: NEMESIS-CLI v4.0 - Agent de codage IA autonome
 NEMESIS est un agent de codage autonome multi-fournisseurs
 (Groq, NVIDIA NIM, OpenRouter, Fireworks, Cohere, API Bridge,
 Custom OpenAI) avec integration MCP, mode plan, mode dual-modele,
 sous-agents, et interface CLI moderne theme Dracula.
CTRLEOF
    chmod 644 "$PKG/DEBIAN/control"

    # --- Post-install ---
    cat > "$PKG/DEBIAN/postinst" << POSTEOF
#!/bin/bash
mkdir -p /root/.nemesis 2>/dev/null || true
mkdir -p "\$HOME/.nemesis" 2>/dev/null || true
POSTEOF
    chmod 755 "$PKG/DEBIAN/postinst"

    # --- Pre-remove ---
    cat > "$PKG/DEBIAN/prerm" << PREMEOF
#!/bin/bash
rm -rf /root/.nemesis 2>/dev/null || true
rm -rf "\$HOME/.nemesis" 2>/dev/null || true
PREMEOF
    chmod 755 "$PKG/DEBIAN/prerm"

    # --- Build deb ---
    dpkg-deb --build "$PKG" "$DIST/nemesis-cli_${VERSION}_${DEB_ARCH}.deb" 2>/dev/null \
        && echo "--- ${ARCH_LABEL} OK -> dist/nemesis-cli_${VERSION}_${DEB_ARCH}.deb ---" \
        || echo "dpkg-deb non disponible"
}

echo "=== NEMESIS-CLI v${VERSION} Build ==="
rm -rf "$BUILD" "$DIST"
mkdir -p "$DIST"

# Par défaut: amd64 seulement (i386 nécessite un env 32-bit)
# Usage: ./build_deb.sh          -> amd64
#        ./build_deb.sh --all   -> amd64 + i386
build_for "AMD64" "amd64"

if [ "${1}" = "--all" ]; then
    build_for "i386" "i386"
fi

echo ""
echo "=== Build terminé ==="
ls -lh "$DIST"/*.deb 2>/dev/null || echo "Aucun .deb"
