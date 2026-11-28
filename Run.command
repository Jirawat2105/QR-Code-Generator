#!/bin/bash
# Double-click in Finder: install Python/dependencies as needed, then run.
set -euo pipefail
trap 'status=$?; if [ "$status" -ne 0 ]; then printf "\nQR Generator could not start. Check the error above and internet access, then retry.\n" >&2; if [ -t 0 ]; then read -r -p "Press Return to close..." || true; fi; fi' EXIT

ROOT="$(CDPATH= cd -P "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [ "$(uname -s)" != 'Darwin' ]; then
    printf 'Run.command is for macOS. On Windows, open run.bat.\n' >&2
    exit 1
fi
UV_VERSION='0.13.10'
case "$(uname -m)" in
    arm64|aarch64)
        UV_TARGET='aarch64-apple-darwin'
        UV_SHA256='e419bf07533bdbf48795fc793601c834dd79db57a8c49ce8e25cfe3a8639958d'
        ;;
    x86_64)
        UV_TARGET='x86_64-apple-darwin'
        UV_SHA256='153e03197588204c04fc4c81cc4bafbfa4280222a385e4ee36a87aeec0ae63b4'
        ;;
    *) printf 'Unsupported Mac CPU: %s\n' "$(uname -m)" >&2; exit 1 ;;
esac
TOOLS="$HOME/Library/Application Support/QRGenerator/tools/uv-$UV_VERSION-$UV_TARGET"
UV="$TOOLS/uv"
if [ ! -x "$UV" ]; then
    printf 'Installing the Python setup tool (first run only)...\n'
    mkdir -p "$TOOLS"
    STAGING="$(mktemp -d "$TOOLS/download.XXXXXX")"
    ARCHIVE="$STAGING/uv.tar.gz"
    curl --fail --location --retry 2 --proto '=https' --tlsv1.2 \
        "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$UV_TARGET.tar.gz" -o "$ARCHIVE"
    printf '%s  %s\n' "$UV_SHA256" "$ARCHIVE" | shasum -a 256 -c -
    tar -xzf "$ARCHIVE" -C "$STAGING" "uv-$UV_TARGET/uv"
    chmod 755 "$STAGING/uv-$UV_TARGET/uv"
    mv -f "$STAGING/uv-$UV_TARGET/uv" "$UV"
    rm -f "$ARCHIVE"
    rmdir "$STAGING/uv-$UV_TARGET" "$STAGING"
fi
PYTHON="$ROOT/.python-env/bin/python"
if [ ! -x "$PYTHON" ]; then
    printf 'Preparing Python 3.13 (downloaded automatically if needed)...\n'
    "$UV" --no-config venv --python 3.13 "$ROOT/.python-env"
fi
printf 'Checking and installing application dependencies...\n'
"$UV" --no-config pip install --python "$PYTHON" -r "$ROOT/requirements.txt"
if ! "$UV" --no-config pip check --python "$PYTHON"; then
    printf 'Repairing incomplete dependencies...\n'
    "$UV" --no-config pip install --reinstall --python "$PYTHON" -r "$ROOT/requirements.txt"
    "$UV" --no-config pip check --python "$PYTHON"
fi
if [ "${1:-}" = '--prepare-only' ]; then
    printf 'Ready. Open Run.command to start QR Generator.\n'
    exit 0
fi
printf 'Starting QR Generator using Python...\n'
"$PYTHON" "$ROOT/src/main.py"
