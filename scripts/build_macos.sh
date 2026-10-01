#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$PROJECT_DIR/apps/web-extractor/frontend"
BUILD_DIR="$PROJECT_DIR/build"
BROWSER_DIR="$BUILD_DIR/playwright-browsers"
BUILD_VENV="$PROJECT_DIR/.venv-build"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "The macOS application must be built on macOS." >&2
  exit 1
fi

mkdir -p "$BUILD_DIR"

echo "Building the React interface..."
npm --prefix "$FRONTEND_DIR" ci
npm --prefix "$FRONTEND_DIR" run build

echo "Installing packaging dependencies..."
if [[ ! -x "$BUILD_VENV/bin/python" ]]; then
  python3 -m venv "$BUILD_VENV"
fi
"$BUILD_VENV/bin/python" -m pip install -r "$PROJECT_DIR/requirements-build.txt"

echo "Bundling Chromium for rendered-page extraction..."
PLAYWRIGHT_BROWSERS_PATH="$BROWSER_DIR" "$BUILD_VENV/bin/python" -m playwright install chromium

echo "Packaging Content Extract.app..."
cd "$PROJECT_DIR"
PYINSTALLER_CONFIG_DIR="$BUILD_DIR/pyinstaller-config" \
  "$BUILD_VENV/bin/python" -m PyInstaller \
  --noconfirm \
  --clean \
  packaging/content-extract.spec

APP_PATH="$PROJECT_DIR/dist/Content Extract.app"
FRONTEND_FILE="$(find "$APP_PATH" -path '*/apps/web-extractor/frontend/dist/index.html' -print -quit)"
if [[ -z "$FRONTEND_FILE" ]]; then
  echo "Could not locate the packaged application resources." >&2
  exit 1
fi
RESOURCE_DIR="${FRONTEND_FILE%/apps/web-extractor/frontend/dist/index.html}"

echo "Adding the bundled Chromium runtime..."
ditto "$BROWSER_DIR" "$RESOURCE_DIR/ms-playwright"
# Frozen Python resolves its root under Frameworks; keep the browser resource reachable there.
if [[ ! -e "$APP_PATH/Contents/Frameworks/ms-playwright" ]]; then
  ln -s ../Resources/ms-playwright "$APP_PATH/Contents/Frameworks/ms-playwright"
fi

echo "Applying a local ad-hoc signature..."
CONTENT_EXTRACT_BUILD_REVISION="$(git -C "$PROJECT_DIR" rev-parse HEAD)" \
  "$BUILD_VENV/bin/python" - "$APP_PATH/Contents/Info.plist" <<'PY'
import os
import plistlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
with path.open("rb") as stream:
    info = plistlib.load(stream)
info["ContentExtractRevision"] = os.environ["CONTENT_EXTRACT_BUILD_REVISION"]
with path.open("wb") as stream:
    plistlib.dump(info, stream)
PY
codesign --force --deep --sign - "$APP_PATH"

echo
echo "Built: $APP_PATH"
echo "Open it with: open '$APP_PATH'"
