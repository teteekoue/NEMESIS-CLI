#!/bin/bash
set -e
VERSION="3.0.0"
DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD="$DIR/build_deb"
DIST="$DIR/dist"

echo "=== NEMESIS-CLI v${VERSION} Build ==="
rm -rf "$BUILD" "$DIST"
mkdir -p "$DIST"
pip install pyinstaller --quiet 2>/dev/null

build_for() {
    local ARCH=$1 DEB=$2
    echo "--- Build $ARCH ($DEB) ---"
    local BD="$BUILD/$ARCH" PKG="$BD/nemesis-cli_${VERSION}_${DEB}"
    rm -rf "$BD"
    mkdir -p "$PKG/DEBIAN" "$PKG/usr/bin" "$PKG/usr/share/nemesis-cli/prompts"
    pyinstaller --clean --distpath "$BD/dist" --workpath "$BD/work" --specpath "$BD" nemesis.spec 2>&1 | tail -3
    cp "$BD/dist/nemesis/nemesis" "$PKG/usr/bin/nemesis" && chmod +x "$PKG/usr/bin/nemesis"
    cp prompts/*.txt "$PKG/usr/share/nemesis-cli/prompts/" 2>/dev/null || true
    cat > "$PKG/DEBIAN/control" << EOF
Package: nemesis-cli
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${DEB}
Depends: python3 (>= 3.10), libssl3, ca-certificates
Maintainer: teteekoue <teteekoue@users.noreply.github.com>
Description: NEMESIS-CLI - Agent de codage IA moderne
Homepage: https://github.com/teteekoue/NEMESIS-CLI
EOF
    chmod +x "$PKG/DEBIAN/control"
    dpkg-deb --build "$PKG" "$DIST/" 2>/dev/null || echo "dpkg-deb non dispo (build manuel)"
    echo "--- $ARCH OK ---"
}

build_for amd64 amd64
echo "=== Build terminé ==="
ls -lh dist/ 2>/dev/null || true
