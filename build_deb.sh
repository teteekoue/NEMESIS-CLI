#!/bin/bash
set -e
VERSION="3.0.0"
DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD="$DIR/build_deb"
DIST="$DIR/dist"

function build_for() {
    local ARCH_LABEL=$1 DEB_ARCH=$2 PYINST_ARCH=$3
    echo ""
    echo "================================================"
    echo "  Build ${ARCH_LABEL} -> nemesis-cli_${VERSION}_${DEB_ARCH}.deb"
    echo "================================================"

    local BD="$BUILD/${DEB_ARCH}"
    local PKG="$BD/pkg/nemesis-cli_${VERSION}_${DEB_ARCH}"
    rm -rf "$BD"
    mkdir -p "$PKG/DEBIAN" "$PKG/usr/bin"

    # --- PyInstaller onefile: tout empaquetté dans un seul binaire ---
    local SPEC_FILE="$BD/nemesis_onefile.spec"
    cat > "$SPEC_FILE" << PYEOF
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
PROJ = Path('${DIR}')

a = Analysis(
    ['nemesis.py'],
    pathex=[str(PROJ)],
    binaries=[],
    datas=[('prompts', 'prompts'), ('src', 'src')],
    hiddenimports=[
        'httpx','httpx._transports','httpx._transports.default',
        'httpcore','httpcore._async','httpcore._sync',
        'h11','anyio','anyio._backends','anyio._backends._asyncio',
        'rich','rich.console','rich.markdown','rich.panel',
        'rich.table','rich.text','rich.tree','rich.syntax',
        'rich.theme','rich.prompt',
        'prompt_toolkit','prompt_toolkit.completion',
        'prompt_toolkit.history','prompt_toolkit.auto_suggest',
        'prompt_toolkit.key_binding','prompt_toolkit.styles',
        'pydantic','pydantic_core','yaml','pyperclip',
        'certifi','idna','sniffio','fnmatch',
        'textual','textual.app','textual.widgets','textual.containers',
        'textual.binding','textual.message','textual.reactive',
        'textual.widget','textual.dom','textual.screen',
        'textual.widgets._header','textual.widgets._footer',
        'textual.widgets._input','textual.widgets._static',
        'textual.widgets._button','textual.widgets._rich_log',
        'textual.widgets._text_area',
        'src','src.config','src.prompts',
        'src.providers','src.providers.base',
        'src.tools','src.tools.definitions','src.tools.executor',
        'src.agent','src.agent.core','src.agent.sub_agent','src.agent.modes',
        'src.mcp','src.mcp.client','src.mcp.manager',
        'src.ui','src.ui.theme','src.ui.logo','src.ui.renderer','src.ui.input_handler',
        'src.commands','src.commands.registry','src.commands.builtins',
        'src.tui','src.tui.app','src.tui.css','src.tui.theme',
    ],
    excludes=['matplotlib','numpy','pandas','PIL','tkinter','unittest','test'],
    noarchive=False,
)
PYEOF

    PYINST="pyinstaller --clean --distpath $BD/dist --workpath $BD/work --specpath $BD"
    if [ -n "$PYINST_ARCH" ]; then
        PYINST="$PYINST --target-arch $PYINST_ARCH"
    fi
    PYINST="$PYINST --onefile $SPEC_FILE"
    eval $PYINST 2>&1 | tail -5

    # Copier le binaire onefile directement dans /usr/bin
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
Description: NEMESIS-CLI - Agent de codage IA autonome
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
mkdir -p "$HOME/.nemesis" 2>/dev/null || true
POSTEOF
    chmod 755 "$PKG/DEBIAN/postinst"

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
build_for "AMD64" "amd64" "x86_64"

if [ "${1}" = "--all" ]; then
    build_for "i386" "i386" "x86"
fi

echo ""
echo "=== Build terminé ==="
ls -lh "$DIST"/*.deb 2>/dev/null || echo "Aucun .deb"
