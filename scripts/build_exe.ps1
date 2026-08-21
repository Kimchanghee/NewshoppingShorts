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

function Get-CoupangLinkContractProjection {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$ExpectedContractId = ""
  )

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw "Coupang link contract smoke report was not created: $Path"
  }
  $report = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
  if ($report.schema_version -ne 1) {
    throw "Unsupported Coupang link contract schema in ${Path}: $($report.schema_version)"
  }
  if ([string]::IsNullOrWhiteSpace([string]$report.contract_id)) {
    throw "Coupang link contract report has no contract_id: $Path"
  }
  if ($ExpectedContractId -and $report.contract_id -ne $ExpectedContractId) {
    throw "Coupang link contract ID mismatch in ${Path}: expected $ExpectedContractId, got $($report.contract_id)"
  }
  if ($report.ok -ne $true) {
    throw "Coupang link contract smoke failed: $Path"
  }
  $stableCases = @(
    $report.cases | ForEach-Object {
      [ordered]@{
        id = [string]$_.id
        accepted = [bool]$_.accepted
        links = @($_.links)
        reason_code = [string]$_.reason_code
      }
    }
  )
  return ([ordered]@{
    schema_version = [int]$report.schema_version
    contract_id = [string]$report.contract_id
    ok = [bool]$report.ok
    cases = $stableCases
  } | ConvertTo-Json -Depth 20 -Compress)
}

function Assert-AuthenticodeArtifact {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string]$ExpectedThumbprint,
    [Parameter(Mandatory = $true)][ValidateSet("public", "integrity-bridge")][string]$SigningMode,
    [Parameter(Mandatory = $true)][string]$SignToolPath,
    [Parameter(Mandatory = $true)][string]$Label
  )

  $expectedThumb = ($ExpectedThumbprint -replace '\s', '').ToUpperInvariant()
  $signature = Get-AuthenticodeSignature -LiteralPath $Path
  $actualThumb = ""
  if ($signature.SignerCertificate -and $signature.SignerCertificate.Thumbprint) {
    $actualThumb = ($signature.SignerCertificate.Thumbprint -replace '\s', '').ToUpperInvariant()
  }
  if ($actualThumb -ne $expectedThumb) {
    throw "$Label signer mismatch (expected $expectedThumb, got $actualThumb)."
  }

  $codeSigningEku = "1.3.6.1.5.5.7.3.3"
  $ekuOids = @(
    $signature.SignerCertificate.EnhancedKeyUsageList |
      ForEach-Object { [string]$_.ObjectId.Value }
  )
  if ($codeSigningEku -notin $ekuOids) {
    if ($SigningMode -eq "public" -or $ekuOids.Count -gt 0) {
      throw "$Label signer certificate is missing the Code Signing EKU ($codeSigningEku)."
    }
    Write-Warning "$Label uses the exact pinned integrity-bridge signer without an EKU extension."
  }
  if ($null -eq $signature.TimeStamperCertificate) {
    throw "$Label signature is missing its trusted RFC 3161 timestamp."
  }

  if ($SigningMode -eq "public") {
    $legacyBridgeThumb = "4FE575D5119B0FC5DAFB6C1684B2968D340EE8F0"
    if ($actualThumb -eq $legacyBridgeThumb) {
      throw "$Label uses the v1.5.64 legacy integrity-bridge signer, which is never public trust."
    }
    if ($signature.SignerCertificate.Subject -eq $signature.SignerCertificate.Issuer) {
      throw "$Label uses a self-issued signer; public releases require a public certificate chain."
    }
    if ([string]$signature.Status -ne "Valid") {
      throw "$Label public signature requires Authenticode Status Valid; got $($signature.Status). UnknownError is not accepted in public mode."
    }
    Invoke-Native "$Label public Authenticode verification (/pa /all)..." $SignToolPath @(
      "verify", "/pa", "/all", "/v", $Path
    )
    Write-Host "OK: $Label is public-trusted (expected signer, Code Signing EKU, timestamp, and /pa /all verification)."
    return
  }

  if ([string]$signature.Status -notin @("Valid", "UnknownError")) {
    throw "$Label integrity-bridge signature is invalid: $($signature.Status)."
  }
  Write-Warning "$Label uses integrity-bridge trust; publication is allowed only for the exact baked transition version."
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$Python = ""
if (-not [string]::IsNullOrWhiteSpace($env:SSMAKER_PYTHON)) {
  $Python = $env:SSMAKER_PYTHON.Trim()
}
if ([string]::IsNullOrWhiteSpace($Python)) {
  $Python = Join-Path $Root "venv311\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
  $Python = Join-Path $Root "venv314\Scripts\python.exe"
}
if (-not (Test-Path $Python)) {
  $Python = "python"
}

# Release guardrail: enforce Python 3.11 to prevent ABI-mismatched wheels.
$pyVersionRaw = (& $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')").Trim()
$pyVersionMM = ($pyVersionRaw -split '\.')[0..1] -join '.'
if (($env:SSMAKER_ALLOW_NON311 -ne "1") -and ($pyVersionMM -ne "3.11")) {
  throw "Unsupported build interpreter: Python $pyVersionRaw. Use Python 3.11 for release builds (override only for local experiments with SSMAKER_ALLOW_NON311=1)."
}

# Read version from version.json for Inno Setup
$versionJson = Join-Path $Root "version.json"
$AppVersion = "0.0.0"
if (Test-Path $versionJson) {
  $vdata = Get-Content $versionJson -Raw | ConvertFrom-Json
  $AppVersion = $vdata.version
}

$autoUpdaterPath = Join-Path $Root "utils\auto_updater.py"
$autoUpdaterText = Get-Content -LiteralPath $autoUpdaterPath -Raw
if ($autoUpdaterText -notmatch 'CURRENT_VERSION\s*=\s*["'']([^"'']+)["'']') {
  throw "Could not read CURRENT_VERSION from $autoUpdaterPath"
}
$EmbeddedAppVersion = $Matches[1]
if ($EmbeddedAppVersion -ne $AppVersion) {
  throw "Version mismatch: version.json=$AppVersion but auto_updater.py=$EmbeddedAppVersion"
}

$PackageTarget = "installer"
if (-not [string]::IsNullOrWhiteSpace($env:SSMAKER_PACKAGE_TARGET)) {
  $PackageTarget = $env:SSMAKER_PACKAGE_TARGET.Trim().ToLowerInvariant()
}
if ($PackageTarget -notin @("installer", "msix")) {
  throw "Unsupported SSMAKER_PACKAGE_TARGET: $PackageTarget (expected installer or msix)."
}
$StorePackageBuild = $PackageTarget -eq "msix"

$SigningMode = "public"
if (-not [string]::IsNullOrWhiteSpace($env:SSMAKER_SIGNING_MODE)) {
  $SigningMode = $env:SSMAKER_SIGNING_MODE.Trim().ToLowerInvariant()
}
if ($SigningMode -notin @("public", "integrity-bridge")) {
  throw "Unsupported SSMAKER_SIGNING_MODE: $SigningMode (expected public or integrity-bridge)."
}

$signThumb = ""
if (-not $StorePackageBuild) {
  if ($null -ne $env:SIGN_CERT_THUMBPRINT) {
    $signThumb = ($env:SIGN_CERT_THUMBPRINT -replace '\s', '').Trim().ToUpperInvariant()
  }
  if ([string]::IsNullOrWhiteSpace($signThumb)) {
    throw "SIGN_CERT_THUMBPRINT is required for direct-download release builds."
  }
}

try {
  Write-Host "Project root: $Root"
  Write-Host "Python: $Python"
  Write-Host "App version: $AppVersion"
  Write-Host "Package target: $PackageTarget"
  if (-not $StorePackageBuild) {
    Write-Host "Signing mode: $SigningMode"
  }
  Push-Location $Root

  if (-not $StorePackageBuild) {
    Invoke-Native "[0.2/5] Validating baked signing identity policy..." $Python @(
      "-c",
      "import sys; from utils.authenticode import validate_build_signing_configuration as validate; ok, reason = validate(sys.argv[1], sys.argv[2], sys.argv[3]); print(reason); raise SystemExit(0 if ok else 1)",
      $SigningMode,
      $AppVersion,
      $signThumb
    )
  }

  # Validate the exact build interpreter before deleting a known-good dist.
  # This catches stale local venvs and missing YouTube discovery data that
  # PyInstaller's import analysis alone cannot detect.
  Invoke-Native "[0.5/5] Validating YouTube OAuth build runtime..." $Python @(
    (Join-Path $Root "scripts\validate_youtube_runtime.py"),
    "--requirements", (Join-Path $Root "requirements.txt")
  )

  Write-Host "`n[1/5] Cleaning build artifacts..."
  Remove-Item -Path `
    (Join-Path $Root "build"), `
    (Join-Path $Root "dist"), `
    (Join-Path $Root "build_staging"), `
    (Join-Path $Root "scripts\build"), `
    (Join-Path $Root "scripts\dist") `
    -Recurse -Force -ErrorAction SilentlyContinue

  # Scan the current source tree before downloading models or creating build
  # outputs. The pinned OSS binary is hash-verified and always redacts findings.
  Invoke-Native "[1.1/5] Scanning source for embedded secrets (Gitleaks)..." "pwsh" @(
    "-NoProfile",
    "-File", (Join-Path $Root "scripts\run_gitleaks.ps1"),
    "-ProjectRoot", $Root
  )

  Invoke-Native "[1.5/5] Materializing faster-whisper models (dereference HF cache symlinks)..." $Python @(
    (Join-Path $Root "scripts\materialize_whisper_models.py")
  )

  Invoke-Native "[1.55/5] Verifying pinned faster-whisper model revisions and hashes..." $Python @(
    (Join-Path $Root "scripts\download_whisper_models.py"),
    "--verify-only"
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

  $tessdataFastCommit = "87416418657359cb625c412a48b6e1d6d41c29bd"
  $tessdataFastBase = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/$tessdataFastCommit"
  $expectedTessFast = @{
    "eng" = @{ Size = 4113088; Hash = "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2" }
    "kor" = @{ Size = 1677415; Hash = "6b85e11d9bbf07863b97b3523b1b112844c43e713df8b66418a081fd1060b3b2" }
    "chi_sim" = @{ Size = 2469156; Hash = "a5fcb6f0db1e1d6d8522f39db4e848f05984669172e584e8d76b6b3141e1f730" }
  }
  foreach ($lang in @("eng", "kor", "chi_sim")) {
    $dst = Join-Path $stageTessdata ("$lang.traineddata")
    $candidate = "$dst.download"
    try {
      Write-Host "Downloading tessdata_fast: $lang.traineddata"
      Invoke-WebRequest -Uri ("$tessdataFastBase/$lang.traineddata") -OutFile $candidate -UseBasicParsing
      $actualSize = (Get-Item -LiteralPath $candidate).Length
      $actualHash = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant()
      $expected = $expectedTessFast[$lang]
      if ($actualSize -ne $expected.Size -or $actualHash -ne $expected.Hash) {
        throw "tessdata_fast integrity mismatch for $lang.traineddata (expected $($expected.Size)/$($expected.Hash), got $actualSize/$actualHash)"
      }
      Move-Item -LiteralPath $candidate -Destination $dst -Force
    } finally {
      Remove-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
    }
  }

  foreach ($lang in @("eng", "kor", "chi_sim")) {
    $dst = Join-Path $stageTessdata ("$lang.traineddata")
    if (-not (Test-Path $dst)) {
      throw "Missing required tessdata after staging: $dst"
    }
  }
  Write-Host "OK: Staged Tesseract to $stageRoot"

  # fonts/ is intentionally not a trusted persistent input. Materialize the
  # exact pinned catalog before PyInstaller, then verify source assets/notices.
  Invoke-Native "[1.8/5] Synchronizing pinned font catalog..." $Python @(
    (Join-Path $Root "scripts\download_all_fonts_final.py")
  )
  Invoke-Native "[1.9/5] Verifying source font assets and license notices..." $Python @(
    (Join-Path $Root "scripts\verify_font_assets.py"),
    "--fonts-dir", (Join-Path $Root "fonts"),
    "--licenses-dir", (Join-Path $Root "resources\licenses")
  )

  # Run the parser contract from checked-in source before freezing anything.
  # The stable projection becomes the reference for frozen and installed EXEs.
  $sourceLinkContractReport = Join-Path $Root "build\coupang_link_contract_source.json"
  New-Item -ItemType Directory -Path (Split-Path $sourceLinkContractReport -Parent) -Force | Out-Null
  Remove-Item -LiteralPath $sourceLinkContractReport -Force -ErrorAction SilentlyContinue
  $previousLinkContractReport = $env:SSMAKER_COUPANG_LINK_CONTRACT_REPORT
  try {
    $env:SSMAKER_COUPANG_LINK_CONTRACT_REPORT = $sourceLinkContractReport
    Invoke-Native "[1.92/5] Running source Coupang link contract smoke test..." $Python @(
      (Join-Path $Root "ssmaker.py"),
      "--coupang-link-contract-smoke"
    )
  } finally {
    $env:SSMAKER_COUPANG_LINK_CONTRACT_REPORT = $previousLinkContractReport
  }
  $sourceLinkProjection = Get-CoupangLinkContractProjection -Path $sourceLinkContractReport
  $sourceLinkContractData = Get-Content -LiteralPath $sourceLinkContractReport -Raw | ConvertFrom-Json

  # Capture Git and external CI identity only after the tracked-tree policy can
  # be evaluated. Untracked files are intentionally neither read nor changed.
  $buildManifest = Join-Path $Root "build_staging\build_manifest.json"
  Invoke-Native "[1.94/5] Generating build provenance manifest..." $Python @(
    (Join-Path $Root "scripts\generate_build_manifest.py"),
    "--project-root", $Root,
    "--version-json", $versionJson,
    "--output", $buildManifest
  )
  $buildManifestData = Get-Content -LiteralPath $buildManifest -Raw | ConvertFrom-Json
  if ($buildManifestData.url_contract_id -ne $sourceLinkContractData.contract_id) {
    throw "Build manifest URL contract ID does not match the source smoke report."
  }
  if ($buildManifestData.url_contract_schema_version -ne $sourceLinkContractData.schema_version) {
    throw "Build manifest URL contract schema does not match the source smoke report."
  }

  $windowsVersionInfo = Join-Path $Root "build_staging\windows_version_info.txt"
  Invoke-Native "[1.95/5] Generating Windows executable metadata..." $Python @(
    (Join-Path $Root "scripts\generate_windows_version_info.py"),
    "--version-json", $versionJson,
    "--build-manifest", $buildManifest,
    "--output", $windowsVersionInfo
  )

  # Compile prompt templates and proprietary pipeline modules to native
  # extensions from a string-obfuscated staging tree.  The extensions are
  # installed beside their sources only for PyInstaller module resolution and
  # are removed in the finally block even when packaging fails.
  $protectionScript = Join-Path $Root "scripts\build_protected_modules.py"
  $protectionManifest = Join-Path $Root "build_staging\protected_modules_manifest.json"
  # ── PyInstaller: onedir build ──────────────────────────────────────────────
  try {
    Invoke-Native "[1.97/5] Compiling protected native modules..." $Python @(
      $protectionScript,
      "prepare",
      "--project-root", $Root,
      "--manifest", $protectionManifest
    )

    Invoke-Native "[2/5] Building ssmaker (onedir)..." $Python @(
      "-m", "PyInstaller", "--noconfirm", "--clean",
      "--distpath", (Join-Path $Root "dist"),
      "--workpath", (Join-Path $Root "build"),
      (Join-Path $Root "ssmaker.spec")
    )
  } finally {
    Invoke-Native "[2.05/5] Removing protected build overlay..." $Python @(
      $protectionScript,
      "cleanup",
      "--project-root", $Root,
      "--manifest", $protectionManifest
    )
  }

  $distDir = Join-Path $Root "dist\ssmaker"
  $ssmakerExe = Join-Path $distDir "ssmaker.exe"

  if (-not (Test-Path $ssmakerExe)) {
    throw "Build output missing: ${ssmakerExe}"
  }

  $distBuildManifest = Join-Path $distDir "build_manifest.json"
  if (-not (Test-Path -LiteralPath $distBuildManifest -PathType Leaf)) {
    throw "Frozen application is missing build_manifest.json: $distBuildManifest"
  }
  $stagingManifestHash = (Get-FileHash -LiteralPath $buildManifest -Algorithm SHA256).Hash
  $distManifestHash = (Get-FileHash -LiteralPath $distBuildManifest -Algorithm SHA256).Hash
  if ($stagingManifestHash -ne $distManifestHash) {
    throw "Frozen build manifest differs from the source staging manifest."
  }

  if ($buildManifestData.whisper_assets.verified -ne $true) {
    throw "Build manifest does not contain verified immutable Whisper assets."
  }
  foreach ($modelProperty in $buildManifestData.whisper_assets.models.PSObject.Properties) {
    foreach ($fileProperty in $modelProperty.Value.files.PSObject.Properties) {
      $frozenModelFile = Join-Path $distDir (
        "faster_whisper_models\$($modelProperty.Name)\$($fileProperty.Name)"
      )
      if (-not (Test-Path -LiteralPath $frozenModelFile -PathType Leaf)) {
        throw "Frozen Whisper asset is missing: $frozenModelFile"
      }
      $actualHash = (Get-FileHash -LiteralPath $frozenModelFile -Algorithm SHA256).Hash.ToLowerInvariant()
      if ($actualHash -ne ([string]$fileProperty.Value).ToLowerInvariant()) {
        throw "Frozen Whisper asset hash mismatch: $frozenModelFile"
      }
    }
  }

  $tesseractProperties = @($buildManifestData.tesseract_assets.files.PSObject.Properties)
  if ($tesseractProperties.Count -eq 0) {
    throw "Build manifest does not contain captured Tesseract assets."
  }
  foreach ($fileProperty in $tesseractProperties) {
    $frozenTesseractFile = Join-Path $distDir (
      "tesseract\$($fileProperty.Name.Replace('/', '\'))"
    )
    if (-not (Test-Path -LiteralPath $frozenTesseractFile -PathType Leaf)) {
      throw "Frozen Tesseract asset is missing: $frozenTesseractFile"
    }
    $actualHash = (Get-FileHash -LiteralPath $frozenTesseractFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne ([string]$fileProperty.Value).ToLowerInvariant()) {
      throw "Frozen Tesseract asset hash mismatch: $frozenTesseractFile"
    }
  }

  $frozenLinkContractReport = Join-Path $Root "build\coupang_link_contract_frozen.json"
  Remove-Item -LiteralPath $frozenLinkContractReport -Force -ErrorAction SilentlyContinue
  $previousLinkContractReport = $env:SSMAKER_COUPANG_LINK_CONTRACT_REPORT
  try {
    $env:SSMAKER_COUPANG_LINK_CONTRACT_REPORT = $frozenLinkContractReport
    Invoke-Native "[2.08/5] Running frozen Coupang link contract smoke test..." $ssmakerExe @(
      "--coupang-link-contract-smoke"
    )
  } finally {
    $env:SSMAKER_COUPANG_LINK_CONTRACT_REPORT = $previousLinkContractReport
  }
  $frozenLinkProjection = Get-CoupangLinkContractProjection `
    -Path $frozenLinkContractReport `
    -ExpectedContractId ([string]$sourceLinkContractData.contract_id)
  if ($frozenLinkProjection -cne $sourceLinkProjection) {
    throw "Source and frozen Coupang link contract reports are not structurally identical."
  }
  Write-Host "OK: source and frozen Coupang link contract smoke reports match."

  # Fail closed if a protected module entered PYZ as bytecode, if a native
  # module is absent, or if source prompt/algorithm literals are recoverable
  # from the executable payload.
  Invoke-Native "[2.1/5] Verifying release confidentiality..." $Python @(
    (Join-Path $Root "scripts\verify_release_confidentiality.py"),
    "--project-root", $Root,
    "--dist-dir", $distDir
  )

  # Validate exploit-mitigation flags in the app bootloader and every
  # SSMaker-authored native extension. This is a security gate, not a claim of
  # anti-decompilation: it checks CFG, ASLR, DEP/NX, and PE section policy.
  Invoke-Native "[2.15/5] Verifying first-party PE hardening (BinSkim)..." "pwsh" @(
    "-NoProfile",
    "-File", (Join-Path $Root "scripts\run_binskim.ps1"),
    "-ProjectRoot", $Root,
    "-DistDir", $distDir
  )

  Invoke-Native "[2.2/5] Verifying packaged font assets and license notices..." $Python @(
    (Join-Path $Root "scripts\verify_font_assets.py"),
    "--fonts-dir", (Join-Path $distDir "fonts"),
    "--licenses-dir", (Join-Path $distDir "licenses")
  )

  # Direct-download artifacts need Authenticode here. Microsoft signs Store
  # MSIX packages after Partner Center certification, so those payloads do not
  # require a private PFX in CI.
  $signtool = $null
  if (-not $StorePackageBuild) {
    $signtool = (Get-Command signtool -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
    if (-not $signtool) {
      $sdkBins = Get-ChildItem -Path "C:\Program Files (x86)\Windows Kits\10\bin" -Directory -ErrorAction SilentlyContinue |
        Sort-Object -Property Name -Descending
      foreach ($sdkBin in $sdkBins) {
        $candidate = Join-Path $sdkBin.FullName "x64\signtool.exe"
        if (Test-Path $candidate) {
          $signtool = $candidate
          break
        }
      }
    }
    if (-not $signtool) {
      throw "signtool.exe not found in PATH. Install Windows SDK Signing Tools."
    }

    Invoke-Native "[2.5/5] Code signing ssmaker.exe..." $signtool @(
      "sign",
      "/fd", "SHA256",
      "/tr", "https://timestamp.digicert.com",
      "/td", "SHA256",
      "/u", "1.3.6.1.5.5.7.3.3",
      "/sha1", $signThumb,
      $ssmakerExe
    )
    Assert-AuthenticodeArtifact `
      -Path $ssmakerExe `
      -ExpectedThumbprint $signThumb `
      -SigningMode $SigningMode `
      -SignToolPath $signtool `
      -Label "ssmaker.exe"
  } else {
    Write-Host "`n[2.5/5] Store build: package signing is delegated to Microsoft Store."
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
    "build_manifest.json",
    "browser-extension\manifest.json",
    "browser-extension\service_worker.js",

    # ── Video / FFmpeg ──
    "imageio_ffmpeg",

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
    "google",
    "googleapiclient",
    "google_auth_oauthlib",
    "google_auth_httplib2",
    "httplib2",
    "requests_oauthlib",
    "oauthlib",
    "googleapiclient\discovery_cache\documents\youtube.v3.json",

    # ── Python packages (Automation) ──
    "selenium",
    "webdriver_manager",
    "bs4",

    # ── Python packages (OCR) ──
    "pytesseract",

    # ── TLS / CA certificates ──
    "certifi"
  )

  # Exact package-folder checks prevent a dist-info-only build from passing a
  # loose substring test. These are the import roots used by YouTube OAuth and
  # the Google GenAI provider on an end-user PC.
  $mustHaveDirectories = @(
    "google\genai",
    "google\api_core",
    "google\auth",
    "google\oauth2",
    "googleapiclient",
    "google_auth_oauthlib",
    "httplib2",
    "requests_oauthlib",
    "oauthlib",
    "requests",
    "keyring"
  )

  foreach ($directory in $mustHaveDirectories) {
    $directoryPath = Join-Path $distDir $directory
    if (-not (Test-Path -LiteralPath $directoryPath -PathType Container)) {
      throw "Missing required Python package directory in dist\ssmaker\: ${directory}"
    }
  }

  foreach ($item in $mustContain) {
    $found = $allFiles | Where-Object { $_ -like "*$item*" }
    if (-not $found) {
      throw "Missing required item in dist\ssmaker\: ${item}"
    }
  }

  # ABI consistency check: all CPython-tagged binaries must match the build interpreter.
  $pyParts = $pyVersionMM -split '\.'
  $expectedAbiTag = "cp$($pyParts[0])$($pyParts[1])"
  $abiTaggedBinaries = Get-ChildItem -Path $distDir -Recurse -File |
    Where-Object { $_.Name -match '\.cp\d{2,3}-(win_amd64|win32)\.(pyd|dll|lib)$' }
  $mismatchedAbi = @()
  foreach ($bin in $abiTaggedBinaries) {
    if ($bin.Name -match '\.cp(\d{2,3})-') {
      $tag = "cp$($matches[1])"
      if ($tag -ne $expectedAbiTag) {
        $mismatchedAbi += $bin.FullName.Substring($distDir.Length + 1)
      }
    }
  }
  if ($mismatchedAbi.Count -gt 0) {
    $preview = ($mismatchedAbi | Select-Object -First 10) -join ", "
    throw "ABI mismatch detected in build output. Expected $expectedAbiTag but found other tags. Examples: $preview"
  }

  # NumPy core sanity check (common startup crash point if stale files remain).
  $numpyCore = Join-Path $distDir "numpy\_core"
  $umathFiles = @()
  if (Test-Path $numpyCore) {
    $umathFiles = @(Get-ChildItem -Path $numpyCore -File -Filter "_multiarray_umath*.pyd")
  }
  if ($umathFiles.Count -eq 0) {
    throw "NumPy core binary missing: numpy\\_core\\_multiarray_umath*.pyd"
  }
  $badUmath = $umathFiles | Where-Object { $_.Name -notmatch "\.$expectedAbiTag-(win_amd64|win32)\.pyd$" }
  if ($badUmath) {
    $badNames = ($badUmath | Select-Object -ExpandProperty Name) -join ", "
    throw "NumPy ABI mismatch: expected $expectedAbiTag but found $badNames"
  }

  # pkg_resources runtime hook may need jaraco.text's sample resource file.
  # Accept either standalone jaraco path or setuptools vendored path.
  $jaracoCandidates = @(
    "jaraco\text\Lorem ipsum.txt",
    "setuptools\_vendor\jaraco\text\Lorem ipsum.txt"
  )
  $jaracoFound = $false
  foreach ($candidate in $jaracoCandidates) {
    $match = $allFiles | Where-Object { $_ -like "*$candidate*" }
    if ($match) {
      $jaracoFound = $true
      break
    }
  }
  if (-not $jaracoFound) {
    throw "Missing jaraco text resource file (required by pkg_resources runtime hook): $($jaracoCandidates -join ' OR ')"
  }

  # imageio dist-info metadata
  $imageioMeta = $allFiles | Where-Object { $_ -like "*imageio*dist-info*METADATA*" }
  if (-not $imageioMeta) {
    throw "imageio package metadata (dist-info/METADATA) not found in build output."
  }

  # Import every native protected module and compare fixed-input prompt hashes.
  # This catches extension initialization failures and semantic changes that
  # source-mode tests cannot see after Cython compilation.
  $protectedRuntimeReport = Join-Path $Root "build\protected_runtime_frozen.json"
  Remove-Item -LiteralPath $protectedRuntimeReport -Force -ErrorAction SilentlyContinue
  $previousProtectedRuntimeReport = $env:SSMAKER_PROTECTED_RUNTIME_REPORT
  try {
    $env:SSMAKER_PROTECTED_RUNTIME_REPORT = $protectedRuntimeReport
    Invoke-Native "[3.4/5] Running frozen protected-module runtime smoke test..." $ssmakerExe @(
      "--protected-runtime-smoke"
    )
  } finally {
    $env:SSMAKER_PROTECTED_RUNTIME_REPORT = $previousProtectedRuntimeReport
  }
  if (-not (Test-Path $protectedRuntimeReport)) {
    throw "Frozen protected-module runtime smoke report was not created: $protectedRuntimeReport"
  }
  $protectedRuntimeData = Get-Content -LiteralPath $protectedRuntimeReport -Raw | ConvertFrom-Json
  if (-not $protectedRuntimeData.ok) {
    $failedProtectedModules = @(
      $protectedRuntimeData.modules.PSObject.Properties |
        Where-Object { -not $_.Value.ok } |
        ForEach-Object { "$($_.Name): $($_.Value.error_type)" }
    ) -join "; "
    throw "Frozen protected-module runtime validation failed: $failedProtectedModules"
  }
  Write-Host "OK: frozen protected-module runtime smoke test passed."

  # Execute the frozen EXE itself in a non-UI, non-network diagnostic mode.
  # This proves PyInstaller included all dynamic OAuth imports and YouTube v3
  # discovery data, not merely that similarly named folders exist.
  $youtubeRuntimeReport = Join-Path $Root "build\youtube_runtime_frozen.json"
  Remove-Item -LiteralPath $youtubeRuntimeReport -Force -ErrorAction SilentlyContinue
  $previousRuntimeReport = $env:SSMAKER_YOUTUBE_RUNTIME_REPORT
  try {
    $env:SSMAKER_YOUTUBE_RUNTIME_REPORT = $youtubeRuntimeReport
    try {
      Invoke-Native "[3.5/5] Running frozen YouTube OAuth runtime smoke test..." $ssmakerExe @(
        "--youtube-runtime-smoke"
      )
    } catch {
      if (Test-Path $youtubeRuntimeReport) {
        $failedRuntimeData = Get-Content -LiteralPath $youtubeRuntimeReport -Raw | ConvertFrom-Json
        throw "Frozen YouTube OAuth runtime validation failed: $($failedRuntimeData.error)"
      }
      throw
    }
  } finally {
    $env:SSMAKER_YOUTUBE_RUNTIME_REPORT = $previousRuntimeReport
  }
  if (-not (Test-Path $youtubeRuntimeReport)) {
    throw "Frozen YouTube runtime smoke report was not created: $youtubeRuntimeReport"
  }
  $youtubeRuntimeData = Get-Content -LiteralPath $youtubeRuntimeReport -Raw | ConvertFrom-Json
  if (-not $youtubeRuntimeData.ok) {
    throw "Frozen YouTube OAuth runtime validation failed: $($youtubeRuntimeData.error)"
  }
  Write-Host "OK: frozen YouTube OAuth runtime smoke test passed."

  # Exercise lazy-loaded integrations from the frozen executable. PyInstaller
  # cannot discover the __import__ calls in main.py, so this blocks releases
  # that would otherwise show ST-U204 / ST-U205 on every startup.
  $optionalManagerReport = Join-Path $Root "build\optional_manager_runtime_frozen.json"
  Remove-Item -LiteralPath $optionalManagerReport -Force -ErrorAction SilentlyContinue
  $previousOptionalManagerReport = $env:SSMAKER_OPTIONAL_MANAGER_RUNTIME_REPORT
  try {
    $env:SSMAKER_OPTIONAL_MANAGER_RUNTIME_REPORT = $optionalManagerReport
    try {
      Invoke-Native "[3.6/5] Running frozen optional-manager runtime smoke test..." $ssmakerExe @(
        "--optional-manager-runtime-smoke"
      )
    } catch {
      if (Test-Path $optionalManagerReport) {
        $failedOptionalManagerData = Get-Content -LiteralPath $optionalManagerReport -Raw | ConvertFrom-Json
        $failedOptionalManagers = @(
          $failedOptionalManagerData.managers.PSObject.Properties |
            Where-Object { -not $_.Value.ok } |
            ForEach-Object { "$($_.Name): $($_.Value.error)" }
        ) -join "; "
        throw "Frozen optional-manager runtime validation failed: $failedOptionalManagers"
      }
      throw
    }
  } finally {
    $env:SSMAKER_OPTIONAL_MANAGER_RUNTIME_REPORT = $previousOptionalManagerReport
  }
  if (-not (Test-Path $optionalManagerReport)) {
    throw "Frozen optional-manager runtime smoke report was not created: $optionalManagerReport"
  }
  $optionalManagerData = Get-Content -LiteralPath $optionalManagerReport -Raw | ConvertFrom-Json
  if (-not $optionalManagerData.ok) {
    throw "Frozen optional-manager runtime validation failed."
  }
  Write-Host "OK: frozen optional-manager runtime smoke test passed."

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

  # Allow only known CA bundles; block all other .pem files
  $allowedPemPatterns = @(
    "*certifi*cacert.pem*",
    "*grpc*_cython*_credentials*roots.pem*"
  )
  $pemFiles = $allFiles | Where-Object { $_ -like "*.pem" }
  foreach ($pem in $pemFiles) {
    $isAllowed = $false
    foreach ($pattern in $allowedPemPatterns) {
      if ($pem -like $pattern) {
        $isAllowed = $true
        break
      }
    }
    if (-not $isAllowed) {
      throw "Unexpected .pem file in build output: ${pem}"
    }
  }
  # Summary: file count and total size
  $fileCount = ($allFiles | Measure-Object).Count
  $totalSizeMB = [math]::Round(((Get-ChildItem -Path $distDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB), 1)
  Write-Host "OK: build output verified. ($fileCount files, ${totalSizeMB} MB)"

  if ($StorePackageBuild) {
    Write-Host "`n[5/5] Store application payload build complete."
    Write-Host "Package source: $distDir"
    return
  }

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
  # Inno invokes this named signing tool for both its generated uninstaller and
  # the final Setup executable. $q and $f are Inno placeholders and therefore
  # intentionally remain literal here.
  $innoSignCommand = '$q' + $signtool + '$q sign /fd SHA256 /tr https://timestamp.digicert.com /td SHA256 /u 1.3.6.1.5.5.7.3.3 /sha1 ' + $signThumb + ' $f'
  Invoke-Native "[4/5] Compiling installer..." $iscc @(
    "/DMyAppVersion=$AppVersion",
    "/DSignToolAvailable",
    "/Sssmaker=$innoSignCommand",
    $issFile
  )

  $installerExe = Join-Path $Root "dist\SSMaker_Setup_v${AppVersion}.exe"
  if (-not (Test-Path $installerExe)) {
    throw "Installer output missing: ${installerExe}"
  }

  Assert-AuthenticodeArtifact `
    -Path $installerExe `
    -ExpectedThumbprint $signThumb `
    -SigningMode $SigningMode `
    -SignToolPath $signtool `
    -Label "final installer"

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
