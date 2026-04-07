#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$REPO_ROOT/src/anki_slot_machine"
MANIFEST_PATH="$SRC_DIR/manifest.json"
ARCHIVE_PATH="$REPO_ROOT/dist/anki_slot_machine.ankiaddon"
BUILD_DIR="$(mktemp -d)"
DEFAULT_VERSION="$(
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' \
    "$MANIFEST_PATH"
)"

RAW_VERSION="${VERSION:-$DEFAULT_VERSION}"
VERSION_VALUE="${RAW_VERSION#v}"
MOD_VALUE="$(date -u +%s)"

cleanup() {
  rm -rf "$BUILD_DIR"
}

trap cleanup EXIT

if [[ ! "$VERSION_VALUE" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9]+)*$ ]]; then
  echo "Invalid version: $RAW_VERSION" >&2
  exit 1
fi

mkdir -p "$REPO_ROOT/dist"
cp -R "$SRC_DIR/." "$BUILD_DIR/"

python3 - "$BUILD_DIR/manifest.json" "$VERSION_VALUE" "$MOD_VALUE" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest["version"] = sys.argv[2]
manifest["mod"] = int(sys.argv[3])
manifest_path.write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY

cd "$BUILD_DIR"
rm -f "$ARCHIVE_PATH"
zip -r "$ARCHIVE_PATH" . -x "__pycache__/*" "*/__pycache__/*" "*.pyc"

echo "Built $ARCHIVE_PATH"
