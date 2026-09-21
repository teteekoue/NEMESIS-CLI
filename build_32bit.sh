#!/usr/bin/env bash
# ==============================================================================
# NEMESIS CLI - Script de compilation 32 bits multi-architecture (ARMv7 / i686)
# Compatible avec Termux (Android 32-bit), Raspberry Pi (armhf) et Linux x86 32-bit
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================="
echo "   NEMESIS CLI - Construction de binaires et roues pip 32 bits   "
echo "================================================================="

TARGET="${1:-all}"

# Enregistrement des emulateurs QEMU pour le support multiplateforme
echo "[1/4] Verification de l'emulation multi-architecture Docker (binfmt)..."
docker run --privileged --rm tonistiigi/binfmt --install arm,386 > /dev/null 2>&1 || true

build_target() {
    local ARCH_NAME="$1"
    local DOCKER_PLATFORM="$2"
    local TAG_NAME="nemesis-builder:$ARCH_NAME"
    local OUT_DIR="$SCRIPT_DIR/dist/32bit_$ARCH_NAME"

    echo ""
    echo "-----------------------------------------------------------------"
    echo ">>> Construction pour l'architecture 32-bit : $ARCH_NAME ($DOCKER_PLATFORM)"
    echo "-----------------------------------------------------------------"

    mkdir -p "$OUT_DIR/wheels" "$OUT_DIR/bin"

    # 1. Construction de l'image Docker 32 bits
    echo "[+] Creation de l'environnement de build Docker ($ARCH_NAME)..."
    docker build -f Dockerfile.32bit --platform "$DOCKER_PLATFORM" -t "$TAG_NAME" .

    # 2. Compilation des roues (wheels) des dependances et de nemesis-cli
    echo "[+] Compilation et telechargement des roues pip compatibles 32-bit..."
    docker run --rm --platform "$DOCKER_PLATFORM" -v "$OUT_DIR:/out" "$TAG_NAME" bash -c "
        mkdir -p /out/wheels &&
        pip wheel -r requirements.txt -w /out/wheels &&
        pip wheel --no-deps -w /out/wheels .
    "

    # 3. Creation du script d'installation Termux
    echo "[+] Generation du script d'installation Termux dedie..."
    cat << 'EOF' > "$OUT_DIR/install_termux.sh"
#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "=== Installation de NEMESIS CLI sur Termux 32-bit ==="
pkg update -y
pkg install -y python python-pip libyaml
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pip install --no-index --find-links="$DIR/wheels" nemesis-cli
echo ""
echo "[✓] Succes ! Lancez 'nemesis' ou 'nemesis-cli'"
EOF
    chmod +x "$OUT_DIR/install_termux.sh"

    # 4. Archivage de distribution
    echo "[+] Creation de l'archive tar.gz prete a deployer..."
    tar -czf "$SCRIPT_DIR/dist/nemesis-termux-32bit-$ARCH_NAME.tar.gz" -C "$SCRIPT_DIR/dist" "32bit_$ARCH_NAME"

    echo "[✓] Fini pour $ARCH_NAME : Voir dist/32bit_$ARCH_NAME et dist/nemesis-termux-32bit-$ARCH_NAME.tar.gz"
}

case "$TARGET" in
    i386|386|x86)
        build_target "i386" "linux/386"
        ;;
    arm|armv7|arm32|termux)
        build_target "armv7" "linux/arm/v7"
        ;;
    all|*)
        build_target "i386" "linux/386"
        build_target "armv7" "linux/arm/v7"
        ;;
esac

echo ""
echo "================================================================="
echo "[✓] Tous les artefacts 32 bits ont ete generes avec succes !"
echo "================================================================="
