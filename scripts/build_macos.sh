#!/usr/bin/env bash
set -euo pipefail

APP_NAME="AstroCat"
ZIP_NAME="AstroCat-macOS.zip"

python3 -m pip install --upgrade pyinstaller
python3 -m pip install --upgrade -r requirements.txt

python3 -m PyInstaller --clean --noconfirm spec/AstroCat-macos.spec

ditto -c -k --sequesterRsrc --keepParent \
  "dist/$APP_NAME.app" \
  "$ZIP_NAME"

echo "Created $ZIP_NAME"
