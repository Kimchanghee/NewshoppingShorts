param(
  [string]$ProjectRoot = "",
  [string]$ToolCache = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$GitleaksVersion = "8.30.1"
$GitleaksArchiveSha256 = "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e"
$GitleaksArchiveUrl = "https://github.com/gitleaks/gitleaks/releases/download/v$GitleaksVersion/gitleaks_${GitleaksVersion}_windows_x64.zip"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}

if ([string]::IsNullOrWhiteSpace($ToolCache)) {
  if (-not [string]::IsNullOrWhiteSpace($env:RUNNER_TOOL_CACHE)) {
    $ToolCache = Join-Path $env:RUNNER_TOOL_CACHE "ssmaker-security-tools"
  } else {
    $ToolCache = Join-Path ([System.IO.Path]::GetTempPath()) "ssmaker-security-tools"
  }
}

$toolDir = Join-Path $ToolCache "gitleaks-$GitleaksVersion"
$archive = Join-Path $toolDir "gitleaks.zip"
New-Item -ItemType Directory -Path $toolDir -Force | Out-Null

if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
  Write-Host "Downloading pinned Gitleaks v$GitleaksVersion..."
  Invoke-WebRequest -Uri $GitleaksArchiveUrl -OutFile $archive
}

$actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $GitleaksArchiveSha256) {
  throw "Gitleaks archive SHA-256 mismatch (expected $GitleaksArchiveSha256, got $actualHash)."
}

$config = Join-Path $ProjectRoot ".gitleaks.toml"
if (-not (Test-Path -LiteralPath $config -PathType Leaf)) {
  throw "Gitleaks configuration is missing: $config"
}
$ignore = Join-Path $ProjectRoot ".gitleaksignore"
if (-not (Test-Path -LiteralPath $ignore -PathType Leaf)) {
  throw "Gitleaks reviewed-finding file is missing: $ignore"
}

$runDir = Join-Path $toolDir ("run-{0}-{1}" -f $PID, [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $runDir | Out-Null
try {
  # Extract afresh from the verified archive so a stale/tampered cache cannot
  # substitute an executable after the archive hash check.
  Expand-Archive -LiteralPath $archive -DestinationPath $runDir -Force
  $executable = Join-Path $runDir "gitleaks.exe"
  if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Verified Gitleaks archive does not contain gitleaks.exe."
  }
  $versionOutput = (& $executable version 2>&1 | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch [regex]::Escape($GitleaksVersion)) {
    throw "Pinned Gitleaks executable validation failed: $versionOutput"
  }

  Write-Host "Scanning the source working tree with Gitleaks v$GitleaksVersion (secrets fully redacted)..."
  $reportPath = Join-Path $runDir "findings.json"
  Push-Location $ProjectRoot
  try {
    # A relative scan root keeps fingerprints stable between local and CI paths.
    & $executable dir "." `
      --config $config `
      --gitleaks-ignore-path $ignore `
      --no-banner `
      --no-color `
      --redact=100 `
      --report-format json `
      --report-path $reportPath `
      --max-target-megabytes=20 `
      --max-archive-depth=0 `
      --timeout=180 `
      --exit-code=1
    $scanExitCode = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  if ($scanExitCode -ne 0 -and (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
    $findings = @(Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json)
    foreach ($finding in $findings) {
      # Never print Match, Secret, or Entropy from the report.
      Write-Warning (
        "Gitleaks finding: rule={0} file={1} line={2}" -f `
          [string]$finding.RuleID,
          [string]$finding.File,
          [int]$finding.StartLine
      )
    }
  }
} finally {
  $resolvedRun = [System.IO.Path]::GetFullPath($runDir)
  $resolvedTool = [System.IO.Path]::GetFullPath($toolDir).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if (-not $resolvedRun.StartsWith($resolvedTool, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean a Gitleaks run directory outside the tool cache: $resolvedRun"
  }
  if (Test-Path -LiteralPath $resolvedRun) {
    Remove-Item -LiteralPath $resolvedRun -Recurse -Force
  }
}
if ($scanExitCode -ne 0) {
  throw "Gitleaks rejected the source working tree (exit $scanExitCode). Secret values were redacted."
}

Write-Host "OK: Gitleaks source-secret scan passed."
