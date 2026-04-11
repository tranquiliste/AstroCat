param(
  [string]$Python = "python",
  [string]$Name = "AstroCat",
  [string]$ZipName = "AstroCat-Windows.zip"
)

$ErrorActionPreference = "Stop"

& $Python -m pip install --upgrade pyinstaller
& $Python -m pip install --upgrade -r requirements.txt
& $Python scripts/strip_metadata_notes.py

& $Python -m PyInstaller --clean --noconfirm spec/AstroCat-windows.spec

if (Test-Path $ZipName) { Remove-Item $ZipName }
Compress-Archive -Path "dist/$Name/*" -DestinationPath $ZipName
Write-Host "Created $ZipName"
