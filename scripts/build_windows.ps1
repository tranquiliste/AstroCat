param(
  [string]$Python = "python",
  [string]$Name = "AstroCat",
  [string]$ZipName = "AstroCat-Windows.zip"
)

$ErrorActionPreference = "Stop"

& $Python -m pip install --upgrade pyinstaller
& $Python -m pip install --upgrade -r requirements.txt

& $Python -m PyInstaller --clean --noconfirm spec/AstroCat-windows.spec

if (Test-Path $ZipName) { Remove-Item $ZipName }

$maxAttempts = 5
$attempt = 0
$zipCreated = $false

while (-not $zipCreated -and $attempt -lt $maxAttempts) {
  $attempt++
  try {
    Compress-Archive -Path "dist/$Name/*" -DestinationPath $ZipName -Force
    $zipCreated = $true
  } catch {
    if ($attempt -ge $maxAttempts) {
      throw
    }
    Write-Warning "Zip attempt $attempt/$maxAttempts failed (likely transient file lock). Retrying..."
    [System.Threading.Thread]::Sleep(1000)
  }
}

Write-Host "Created $ZipName"
