#!/usr/bin/env bash
# OVD Platform — Script de build multi-plataforma para el binario `ovd`
#
# Requiere:
#   - Rust toolchain instalado (rustup)
#   - `cross` para targets Linux/Windows: cargo install cross
#
# Uso:
#   ./scripts/build-tui.sh [target]
#
# Targets disponibles:
#   macos-arm64    → aarch64-apple-darwin       (nativo M1/M2/M3)
#   macos-x86      → x86_64-apple-darwin        (Intel / Rosetta)
#   linux          → x86_64-unknown-linux-musl   (estático, sin glibc)
#   windows        → x86_64-pc-windows-gnu
#   all            → todos los anteriores (default)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TUI_DIR="$SCRIPT_DIR/../src/tui"
OUT_DIR="$SCRIPT_DIR/../dist"

mkdir -p "$OUT_DIR"

TARGET="${1:-all}"

# ── Helpers ──────────────────────────────────────────────────────────────────

build_native() {
    local target="$1"
    local out_name="$2"
    echo "→ Compilando $target (cargo nativo)..."
    (cd "$TUI_DIR" && cargo build --release --target "$target")
    cp "$TUI_DIR/target/$target/release/ovd" "$OUT_DIR/$out_name"
    echo "  ✓ $OUT_DIR/$out_name"
}

build_cross() {
    local target="$1"
    local out_name="$2"
    local ext="${3:-}"
    echo "→ Compilando $target (cross)..."
    if ! command -v cross &>/dev/null; then
        echo "  ✗ 'cross' no encontrado. Instala con: cargo install cross"
        exit 1
    fi
    (cd "$TUI_DIR" && cross build --release --target "$target")
    cp "$TUI_DIR/target/$target/release/ovd${ext}" "$OUT_DIR/$out_name"
    echo "  ✓ $OUT_DIR/$out_name"
}

# ── Targets ──────────────────────────────────────────────────────────────────

build_macos_arm64() {
    rustup target add aarch64-apple-darwin 2>/dev/null || true
    build_native "aarch64-apple-darwin" "ovd-macos-arm64"
}

build_macos_x86() {
    rustup target add x86_64-apple-darwin 2>/dev/null || true
    build_native "x86_64-apple-darwin" "ovd-macos-x86_64"
}

build_macos_universal() {
    build_macos_arm64
    build_macos_x86
    echo "→ Creando universal binary (lipo)..."
    lipo -create -output "$OUT_DIR/ovd-macos-universal" \
        "$OUT_DIR/ovd-macos-arm64" \
        "$OUT_DIR/ovd-macos-x86_64"
    echo "  ✓ $OUT_DIR/ovd-macos-universal"
}

build_linux() {
    rustup target add x86_64-unknown-linux-musl 2>/dev/null || true
    build_cross "x86_64-unknown-linux-musl" "ovd-linux-x86_64"
}

build_windows() {
    rustup target add x86_64-pc-windows-gnu 2>/dev/null || true
    build_cross "x86_64-pc-windows-gnu" "ovd-windows-x86_64.exe" ".exe"
}

# ── Dispatch ─────────────────────────────────────────────────────────────────

case "$TARGET" in
    macos-arm64)  build_macos_arm64 ;;
    macos-x86)    build_macos_x86 ;;
    macos)        build_macos_universal ;;
    linux)        build_linux ;;
    windows)      build_windows ;;
    all)
        echo "=== OVD TUI — Build multi-plataforma ==="
        case "$(uname -s)" in
            Darwin)
                build_macos_universal
                build_linux
                build_windows
                ;;
            Linux)
                build_linux
                build_windows
                echo "  (macOS: ejecutar en host macOS)"
                ;;
            *)
                echo "  Sistema no reconocido: $(uname -s)"
                exit 1
                ;;
        esac
        ;;
    *)
        echo "Target desconocido: $TARGET"
        echo "Uso: $0 [macos-arm64|macos-x86|macos|linux|windows|all]"
        exit 1
        ;;
esac

echo ""
echo "=== Artefactos generados en $OUT_DIR ==="
ls -lh "$OUT_DIR"/ovd-* 2>/dev/null || echo "(ninguno)"
