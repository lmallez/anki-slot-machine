#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$REPO_ROOT/src/anki_slot_machine"
MANIFEST_PATH="$SRC_DIR/manifest.json"
ARCHIVE_PATH="$REPO_ROOT/dist/anki_slot_machine.ankiaddon"
INSTALL_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$INSTALL_DIR"
}

trap cleanup EXIT

PACKAGE_NAME="$(
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["package"])' \
    "$MANIFEST_PATH"
)"

if [[ -n "${ANKI_ADDONS_DIR:-}" ]]; then
  ADDONS_DIR="$ANKI_ADDONS_DIR"
elif [[ -d "$HOME/Library/Application Support/Anki2/addons21" ]]; then
  ADDONS_DIR="$HOME/Library/Application Support/Anki2/addons21"
elif [[ -d "$HOME/.local/share/Anki2/addons21" ]]; then
  ADDONS_DIR="$HOME/.local/share/Anki2/addons21"
else
  echo "Could not find an Anki add-ons directory." >&2
  exit 1
fi

TARGET_DIR="$ADDONS_DIR/$PACKAGE_NAME"

"$REPO_ROOT/build.sh"
mkdir -p "$TARGET_DIR"
unzip -oq "$ARCHIVE_PATH" -d "$INSTALL_DIR"

rsync -a --delete \
  --exclude "meta.json" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  "$INSTALL_DIR/" "$TARGET_DIR/"

echo "Installed into $TARGET_DIR"
