Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Native {
  param(
    [Parameter(Mandatory = $true)][string]$Step,
    [Parameter(Mandatory = $true)][string]$Exe,
    [Parameter(Mandatory = $true)][object[]]$Args
  )

  Write-Host "`n$Step"
  $tail = New-Object System.Collections.Generic.List[string]

  # Some native tools (including PyInstaller) write INFO logs to stderr.
  # In Windows PowerShell 5.x, merging stderr into the pipeline can produce non-terminating
  # error records; with $ErrorActionPreference='Stop' this aborts the script prematurely.
  $oldEAP = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    & $Exe @Args 2>&1 | ForEach-Object {
      # Preserve full logs (for local runs) while keeping only the last N lines for CI annotations.
      $_
      $line = $_.ToString()
      $tail.Add($line)
      if ($tail.Count -gt 40) {
        $tail.RemoveAt(0)
      }
    }
  } finally {
    $ErrorActionPreference = $oldEAP
  }

  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    $tailText = ($tail -join " | ")
    throw "${Step} failed with exit code ${exitCode}: ${Exe} $($Args -join ' ') | tail: ${tailText}"
  }
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$Python = Join-Path $Root "venv311\\Scripts\\python.exe"
if (-not (Test-Path $Python)) {
  $Python = Join-Path $Root "venv314\\Scripts\\python.exe"
}
if (-not (Test-Path $Python)) {
  $Python = "python"
}

try {
  Write-Host "Project root: $Root"
  Write-Host "Python: $Python"
  Push-Location $Root

  Write-Host "`n[1/5] Cleaning build artifacts..."
  Remove-Item -Path `
    (Join-Path $Root "build"), `
    (Join-Path $Root "dist"), `
    (Join-Path $Root "scripts\\build"), `
    (Join-Path $Root "scripts\\dist") `
    -Recurse -Force -ErrorAction SilentlyContinue

  Invoke-Native "[1.5/5] Materializing faster-whisper models (dereference HF cache symlinks)..." $Python @(
    (Join-Path $Root "scripts\\materialize_whisper_models.py")
  )

  Invoke-Native "[2/5] Building updater.exe (for bundling)..." $Python @(
    "-m", "PyInstaller", "--noconfirm", "--clean",
    "--distpath", (Join-Path $Root "dist"),
    "--workpath", (Join-Path $Root "build"),
    (Join-Path $Root "updater.spec")
  )

  Invoke-Native "[3/5] Building ssmaker.exe..." $Python @(
    "-m", "PyInstaller", "--noconfirm", "--clean",
    "--distpath", (Join-Path $Root "dist"),
    "--workpath", (Join-Path $Root "build"),
    (Join-Path $Root "ssmaker.spec")
  )

  $ssmakerExe = Join-Path $Root "dist\\ssmaker.exe"
  $updaterExe = Join-Path $Root "dist\\updater.exe"

  if (-not (Test-Path $ssmakerExe)) {
    throw "Build output missing: ${ssmakerExe}"
  }

  Write-Host "`n[4/5] Verifying bundled contents inside ssmaker.exe..."
  # Use the module entrypoint instead of relying on `pyi-archive_viewer(.exe)` being on PATH.
  # On GitHub Actions, python.exe is typically in the install root while scripts are in a separate `Scripts\` dir.
  $listing = "l`nq`n" | & $Python -m PyInstaller.utils.cliutils.archive_viewer $ssmakerExe

# Must-have bundle items
$mustContain = @(
  "updater.exe",
  "version.json",
  # Ensure we ship an ffmpeg binary (we rely on imageio_ffmpeg, not a local resource/bin copy).
  "imageio_ffmpeg\\binaries\\ffmpeg",
  # Ensure bundled Korean font assets are present for subtitle/UI rendering.
  "fonts\\Pretendard-ExtraBold.ttf"
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
# NOTE: Even if these files exist only on the build machine, bundling them would be catastrophic.
$mustNotContain = @(
  ".env",
  ".secure_config.enc",
  # SecretsManager fallback file + dev key (should never be bundled)
  ".secrets",
  ".encryption_key",
  # Legacy/local remember-me file (can contain ID/PW)
  "info.on",
  # Credential / key files (must never ship)
  "temp_pw.txt",
  "vertex-credentials",
  ".key"
)
foreach ($item in $mustNotContain) {
  if ($listing | Select-String -SimpleMatch $item) {
    throw "Sensitive file was bundled into ssmaker.exe: ${item}"
  }
}

# certifi CA bundle is required for TLS verification at runtime.
# Block all other .pem files.
$allowedPem = @(
  "certifi\\cacert.pem"
)
$pemHits = $listing | Select-String -SimpleMatch ".pem"
foreach ($hit in $pemHits) {
  $line = $hit.ToString()
  $isAllowed = $false
  foreach ($allow in $allowedPem) {
    if ($line -like "*$allow*") {
      $isAllowed = $true
      break
    }
  }
  if (-not $isAllowed) {
    throw "Sensitive file was bundled into ssmaker.exe: $line"
  }
}
Write-Host "OK: bundle contents verified."

Write-Host "`n[5/5] Removing standalone dist\\updater.exe (single-file distribution)..."
Remove-Item -Path $updaterExe -Force -ErrorAction SilentlyContinue

Write-Host "`nDone."
Write-Host "Distribute only:"
Write-Host " - $ssmakerExe"

} catch {
  $msg = $_.Exception.Message
  if (-not $msg) {
    $msg = ($_ | Out-String)
  }
  $msg = ($msg -replace "[\r\n]+", " | ").Trim()
  Write-Host "::error::build_exe.ps1 failed: $msg"
  Write-Host "::error::python=$Python last_exit_code=$LASTEXITCODE"
  throw
} finally {
  Pop-Location
}
