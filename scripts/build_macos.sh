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

echo "Applying a local ad-hoc signature..."
codesign --force --deep --sign - "$APP_PATH"

echo
echo "Built: $APP_PATH"
echo "Open it with: open '$APP_PATH'"
