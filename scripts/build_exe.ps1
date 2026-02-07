Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$Python = Join-Path $Root "venv314\\Scripts\\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

Write-Host "Project root: $Root"
Write-Host "Python: $Python"

Write-Host "`n[1/5] Cleaning build artifacts..."
Remove-Item -Path (Join-Path $Root "build"), (Join-Path $Root "dist") -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "`n[1.5/5] Materializing faster-whisper models (dereference HF cache symlinks)..."
& $Python (Join-Path $Root "scripts\\materialize_whisper_models.py")

Write-Host "`n[2/5] Building updater.exe (for bundling)..."
& $Python -m PyInstaller --noconfirm --clean (Join-Path $Root "updater.spec")

Write-Host "`n[3/5] Building ssmaker.exe..."
& $Python -m PyInstaller --noconfirm --clean (Join-Path $Root "ssmaker.spec")

$ssmakerExe = Join-Path $Root "dist\\ssmaker.exe"
$updaterExe = Join-Path $Root "dist\\updater.exe"

Write-Host "`n[4/5] Verifying bundled contents inside ssmaker.exe..."
# Use the module entrypoint instead of relying on `pyi-archive_viewer(.exe)` being on PATH.
# On GitHub Actions, python.exe is typically in the install root while scripts are in a separate `Scripts\` dir.
$listing = "l`nq`n" | & $Python -m PyInstaller.utils.cliutils.archive_viewer $ssmakerExe

# Must-have bundle items
$mustContain = @(
  "updater.exe",
  "resource\\bin\\ffmpeg.exe",
  "resource\\bin\\ffprobe.exe",
  "fonts\\Pretendard-ExtraBold.ttf",
  "version.json",
  "ui_preferences.json"
)

foreach ($item in $mustContain) {
  if (-not ($listing | Select-String -SimpleMatch $item)) {
    throw "Missing required bundle item: ${item}"
  }
}

# imageio runtime requires dist-info metadata for importlib.metadata at runtime.
$imageioMeta = $listing | Select-String -SimpleMatch "imageio-" | Select-String -SimpleMatch "dist-info\\METADATA"
if (-not $imageioMeta) {
  throw "imageio package metadata (dist-info/METADATA) not found inside ssmaker.exe archive."
}

# Make sure we are not accidentally shipping local secrets/configs.
$mustNotContain = @(".env", ".secure_config.enc")
foreach ($item in $mustNotContain) {
  if ($listing | Select-String -SimpleMatch $item) {
    throw "Sensitive file was bundled into ssmaker.exe: ${item}"
  }
}
Write-Host "OK: bundle contents verified."

Write-Host "`n[5/5] Removing standalone dist\\updater.exe (single-file distribution)..."
Remove-Item -Path $updaterExe -Force -ErrorAction SilentlyContinue

Write-Host "`nDone."
Write-Host "Distribute only:"
Write-Host " - $ssmakerExe"
