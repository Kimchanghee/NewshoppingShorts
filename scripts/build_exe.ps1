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

$Python = Join-Path $Root "venv311\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = Join-Path $Root "venv314\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
  $Python = "python"
}

# Read version from version.json for Inno Setup
$versionJson = Join-Path $Root "version.json"
$AppVersion = "0.0.0"
if (Test-Path $versionJson) {
  $vdata = Get-Content $versionJson -Raw | ConvertFrom-Json
  $AppVersion = $vdata.version
}

try {
  Write-Host "Project root: $Root"
  Write-Host "Python: $Python"
  Write-Host "App version: $AppVersion"
  Push-Location $Root

  Write-Host "`n[1/5] Cleaning build artifacts..."
  Remove-Item -Path `
    (Join-Path $Root "build"), `
    (Join-Path $Root "dist"), `
    (Join-Path $Root "build_staging"), `
    (Join-Path $Root "scripts\build"), `
    (Join-Path $Root "scripts\dist") `
    -Recurse -Force -ErrorAction SilentlyContinue

  Invoke-Native "[1.5/5] Materializing faster-whisper models (dereference HF cache symlinks)..." $Python @(
    (Join-Path $Root "scripts\materialize_whisper_models.py")
  )

  Write-Host "`n[1.7/5] Staging Tesseract OCR runtime (for end-user OCR/blur)..."
  $stageRoot = Join-Path $Root "build_staging\tesseract"
  Remove-Item -Path $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Path $stageRoot | Out-Null

  $tesseractExe = $null
  try {
    $cmd = Get-Command tesseract -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -and (Test-Path $cmd.Source)) {
      $tesseractExe = $cmd.Source
    }
  } catch {
    $tesseractExe = $null
  }

  $candidates = @(
    $tesseractExe,
    "C:\Program Files\Tesseract-OCR\tesseract.exe",
    "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Tesseract-OCR\tesseract.exe")
  ) | Where-Object { $_ -and (Test-Path $_) }

  $tesseractExe = $candidates | Select-Object -First 1
  if (-not $tesseractExe) {
    throw "Tesseract not found on build machine. Install it once (recommended): winget install UB-Mannheim.TesseractOCR"
  }

  $tessRoot = Split-Path $tesseractExe -Parent
  Copy-Item -Path $tesseractExe -Destination (Join-Path $stageRoot "tesseract.exe") -Force
  Copy-Item -Path (Join-Path $tessRoot "*.dll") -Destination $stageRoot -Force -ErrorAction SilentlyContinue

  $stageTessdata = Join-Path $stageRoot "tessdata"
  New-Item -ItemType Directory -Path $stageTessdata | Out-Null

  $installedTessdata = Join-Path $tessRoot "tessdata"
  foreach ($lang in @("eng", "kor", "chi_sim", "osd")) {
    $dst = Join-Path $stageTessdata ("$lang.traineddata")
    $src = Join-Path $installedTessdata ("$lang.traineddata")
    if ((Test-Path $src) -and -not (Test-Path $dst)) {
      Copy-Item -Path $src -Destination $dst -Force
    }
  }

  $tessdataFastBase = "https://github.com/tesseract-ocr/tessdata_fast/raw/main"
  foreach ($lang in @("eng", "kor", "chi_sim")) {
    $dst = Join-Path $stageTessdata ("$lang.traineddata")
    if (-not (Test-Path $dst)) {
      Write-Host "Downloading tessdata_fast: $lang.traineddata"
      Invoke-WebRequest -Uri ("$tessdataFastBase/$lang.traineddata") -OutFile $dst -UseBasicParsing
    }
  }

  foreach ($lang in @("eng", "kor", "chi_sim")) {
    $dst = Join-Path $stageTessdata ("$lang.traineddata")
    if (-not (Test-Path $dst)) {
      throw "Missing required tessdata after staging: $dst"
    }
  }
  Write-Host "OK: Staged Tesseract to $stageRoot"

  # ── PyInstaller: onedir build ──────────────────────────────────────────────
  Invoke-Native "[2/5] Building ssmaker (onedir)..." $Python @(
    "-m", "PyInstaller", "--noconfirm", "--clean",
    "--distpath", (Join-Path $Root "dist"),
    "--workpath", (Join-Path $Root "build"),
    (Join-Path $Root "ssmaker.spec")
  )

  $distDir = Join-Path $Root "dist\ssmaker"
  $ssmakerExe = Join-Path $distDir "ssmaker.exe"

  if (-not (Test-Path $ssmakerExe)) {
    throw "Build output missing: ${ssmakerExe}"
  }

  # ── Verify output directory contents ───────────────────────────────────────
  Write-Host "`n[3/5] Verifying build output in dist\ssmaker\..."

  # Collect all relative paths in the output directory for verification
  $allFiles = Get-ChildItem -Path $distDir -Recurse -File | ForEach-Object {
    $_.FullName.Substring($distDir.Length + 1)
  }

  # Must-have items — 빌드에 반드시 포함되어야 하는 모든 핵심 항목
  $mustContain = @(
    # ── Core ──
    "ssmaker.exe",
    "version.json",

    # ── Video / FFmpeg ──
    "imageio_ffmpeg",

    # ── Korean Fonts (전체) ──
    "fonts\Pretendard-ExtraBold.ttf",
    "fonts\Pretendard-Bold.ttf",
    "fonts\Pretendard-SemiBold.ttf",
    "fonts\GmarketSansTTFBold.ttf",
    "fonts\SpoqaHanSansNeo-Bold.ttf",
    "fonts\Paperlogy-9Black.ttf",
    "fonts\SeoulHangangB.ttf",
    "fonts\IBMPlexSansKR-Bold.ttf",

    # ── Tesseract OCR runtime ──
    "tesseract\tesseract.exe",
    "tesseract\tessdata\eng.traineddata",
    "tesseract\tessdata\kor.traineddata",
    "tesseract\tessdata\chi_sim.traineddata",

    # ── Python packages (UI) ──
    "PyQt6",

    # ── Python packages (AI / ML) ──
    "faster_whisper",
    "ctranslate2",

    # ── Python packages (Video / Audio) ──
    "moviepy",
    "cv2",
    "pydub",
    "edge_tts",
    "av",

    # ── Python packages (Network / API) ──
    "requests",

    # ── Python packages (Automation) ──
    "selenium",
    "webdriver_manager",
    "bs4",

    # ── Python packages (OCR) ──
    "pytesseract",

    # ── TLS / CA certificates ──
    "certifi"
  )

  foreach ($item in $mustContain) {
    $found = $allFiles | Where-Object { $_ -like "*$item*" }
    if (-not $found) {
      throw "Missing required item in dist\ssmaker\: ${item}"
    }
  }

  # imageio dist-info metadata
  $imageioMeta = $allFiles | Where-Object { $_ -like "*imageio*dist-info*METADATA*" }
  if (-not $imageioMeta) {
    throw "imageio package metadata (dist-info/METADATA) not found in build output."
  }

  # Sensitive files must NOT be in the output
  $mustNotContain = @(
    ".env",
    ".secure_config.enc",
    ".secrets",
    ".encryption_key",
    "info.on",
    "temp_pw.txt",
    "vertex-credentials",
    ".key"
  )
  foreach ($item in $mustNotContain) {
    # Exact filename match (not substring) to avoid false positives like "certifi/.key" matching registry keys
    $found = $allFiles | Where-Object {
      $name = Split-Path $_ -Leaf
      $name -eq $item
    }
    if ($found) {
      throw "Sensitive file found in build output: ${found}"
    }
  }

  # certifi CA bundle allowed; block other .pem files
  $pemFiles = $allFiles | Where-Object { $_ -like "*.pem" }
  foreach ($pem in $pemFiles) {
    if ($pem -notlike "*certifi*cacert.pem*") {
      throw "Unexpected .pem file in build output: ${pem}"
    }
  }
  # Summary: file count and total size
  $fileCount = ($allFiles | Measure-Object).Count
  $totalSizeMB = [math]::Round(((Get-ChildItem -Path $distDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB), 1)
  Write-Host "OK: build output verified. ($fileCount files, ${totalSizeMB} MB)"

  # ── Inno Setup: create installer ───────────────────────────────────────────
  Write-Host "`n[4/5] Building Windows installer with Inno Setup..."

  # Find ISCC.exe (Inno Setup Compiler)
  $iscc = $null
  $isccCandidates = @(
    (Get-Command iscc -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
  ) | Where-Object { $_ -and (Test-Path $_) }
  $iscc = $isccCandidates | Select-Object -First 1

  if (-not $iscc) {
    throw "Inno Setup not found. Install: winget install JRSoftware.InnoSetup  OR  choco install innosetup -y"
  }

  $issFile = Join-Path $Root "installer.iss"
  Invoke-Native "[4/5] Compiling installer..." $iscc @(
    "/DMyAppVersion=$AppVersion",
    $issFile
  )

  $installerExe = Join-Path $Root "dist\SSMaker_Setup_v${AppVersion}.exe"
  if (-not (Test-Path $installerExe)) {
    throw "Installer output missing: ${installerExe}"
  }

  # ── Done ───────────────────────────────────────────────────────────────────
  $installerSize = [math]::Round((Get-Item $installerExe).Length / 1MB, 1)
  Write-Host "`n[5/5] Build complete."
  Write-Host "Distribute:"
  Write-Host " - $installerExe  (${installerSize} MB)"

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
