param(
  [Parameter(Mandatory = $true)][string]$DistDir,
  [string]$ProjectRoot = "",
  [string]$ToolCache = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BinSkimVersion = "4.4.9.11"
$BinSkimPackageSha512 = "HVko8xQVQgXwVx2EuC8D5iQeA6kcyFBwL+u1XTHIjATwbb2gP6btZDmiYU9jU60mb3HAOZf1+MsBGSkIuE/xYg=="
$BinSkimPackageUrl = "https://api.nuget.org/v3-flatcontainer/microsoft.codeanalysis.binskim/$BinSkimVersion/microsoft.codeanalysis.binskim.$BinSkimVersion.nupkg"

function Get-Sha512Base64 {
  param([Parameter(Mandatory = $true)][string]$Path)

  $algorithm = [System.Security.Cryptography.SHA512]::Create()
  $stream = [System.IO.File]::OpenRead($Path)
  try {
    return [Convert]::ToBase64String($algorithm.ComputeHash($stream))
  } finally {
    $stream.Dispose()
    $algorithm.Dispose()
  }
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
  $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}
$DistDir = (Resolve-Path -LiteralPath $DistDir).Path

if ([string]::IsNullOrWhiteSpace($ToolCache)) {
  if (-not [string]::IsNullOrWhiteSpace($env:RUNNER_TOOL_CACHE)) {
    $ToolCache = Join-Path $env:RUNNER_TOOL_CACHE "ssmaker-security-tools"
  } else {
    $ToolCache = Join-Path ([System.IO.Path]::GetTempPath()) "ssmaker-security-tools"
  }
}

$toolDir = Join-Path $ToolCache "binskim-$BinSkimVersion"
$package = Join-Path $toolDir "binskim.nupkg"
New-Item -ItemType Directory -Path $toolDir -Force | Out-Null

if (-not (Test-Path -LiteralPath $package -PathType Leaf)) {
  Write-Host "Downloading pinned Microsoft BinSkim v$BinSkimVersion..."
  Invoke-WebRequest -Uri $BinSkimPackageUrl -OutFile $package
}

$actualHash = Get-Sha512Base64 -Path $package
if ($actualHash -ne $BinSkimPackageSha512) {
  throw "BinSkim NuGet package SHA-512 mismatch."
}

$targets = New-Object System.Collections.Generic.List[string]
$appExe = Join-Path $DistDir "ssmaker.exe"
if (-not (Test-Path -LiteralPath $appExe -PathType Leaf)) {
  throw "BinSkim target executable is missing: $appExe"
}
$targets.Add($appExe)

# Scan only SSMaker-authored native modules. Third-party DLL policy belongs to
# dependency provenance/audit controls and must not create un-actionable noise.
foreach ($rootName in @("config", "core", "managers", "processors", "prompts", "ui")) {
  $targetRoot = Join-Path $DistDir $rootName
  if (-not (Test-Path -LiteralPath $targetRoot -PathType Container)) {
    continue
  }
  Get-ChildItem -LiteralPath $targetRoot -Filter "*.pyd" -File -Recurse |
    ForEach-Object { $targets.Add($_.FullName) }
}
if ($targets.Count -lt 2) {
  throw "No protected first-party native modules were found for BinSkim."
}

$sarifDir = Join-Path $ProjectRoot "build_staging"
New-Item -ItemType Directory -Path $sarifDir -Force | Out-Null
$sarif = Join-Path $sarifDir "binskim.sarif"
$rules = "BA2008;BA2009;BA2010;BA2015;BA2016;BA2019;BA2021"

$runDir = Join-Path $toolDir ("run-{0}-{1}" -f $PID, [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $runDir | Out-Null
try {
  # Always execute a fresh expansion of the verified package. BinSkim is a
  # framework bundle with many DLLs, so validating only its launcher is not
  # sufficient against a modified cache directory.
  Expand-Archive -LiteralPath $package -DestinationPath $runDir -Force
  $executable = Join-Path $runDir "tools\net9.0\win-x64\BinSkim.exe"
  if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Verified BinSkim package does not contain its Windows x64 executable."
  }
  $versionOutput = (& $executable --version 2>&1 | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch [regex]::Escape($BinSkimVersion)) {
    throw "Pinned BinSkim executable validation failed: $versionOutput"
  }

  Write-Host "Scanning $($targets.Count) first-party PE artifacts with BinSkim v$BinSkimVersion..."
  & $executable analyze @($targets) `
    --output $sarif `
    --run-only-rules $rules `
    --level "Error;Warning" `
    --kind "Fail" `
    --ignorePdbLoadError true `
    --ignoreBinaryAnalysisErrors false `
    --disable-telemetry true `
    --disable-archive-extraction true `
    --quiet true `
    --rich-return-code false `
    --log "ForceOverwrite;Minify"
  $exitCode = $LASTEXITCODE
} finally {
  $resolvedRun = [System.IO.Path]::GetFullPath($runDir)
  $resolvedTool = [System.IO.Path]::GetFullPath($toolDir).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
  if (-not $resolvedRun.StartsWith($resolvedTool, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean a BinSkim run directory outside the tool cache: $resolvedRun"
  }
  if (Test-Path -LiteralPath $resolvedRun) {
    Remove-Item -LiteralPath $resolvedRun -Recurse -Force
  }
}

if (-not (Test-Path -LiteralPath $sarif -PathType Leaf)) {
  throw "BinSkim did not produce its required SARIF report."
}
$report = Get-Content -LiteralPath $sarif -Raw | ConvertFrom-Json -Depth 100
$invocations = @($report.runs[0].invocations)
$results = @($report.runs[0].results)
$failedInvocation = $invocations | Where-Object { $_.executionSuccessful -ne $true }
if ($exitCode -ne 0 -or $failedInvocation -or $results.Count -gt 0) {
  $ruleIds = @($results | ForEach-Object { $_.ruleId } | Sort-Object -Unique)
  throw "BinSkim rejected first-party PE hardening (exit $exitCode; rules: $($ruleIds -join ', ')). See $sarif."
}

Write-Host "OK: BinSkim PE hardening gate passed for $($targets.Count) artifacts."
