#!/usr/bin/env bash
set -euo pipefail

ZIP_NAME="AstroCat-Linux.zip"

python3 -m pip install --upgrade pyinstaller
python3 -m pip install --upgrade -r requirements.txt
python3 scripts/strip_metadata_notes.py

python3 -m PyInstaller --clean --noconfirm spec/AstroCat-linux.spec

if [ -f "$ZIP_NAME" ]; then
  rm "$ZIP_NAME"
fi

cd dist
zip -r "../$ZIP_NAME" "AstroCat"
echo "Created $ZIP_NAME"
