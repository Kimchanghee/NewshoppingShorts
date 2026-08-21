$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$packageVersion = "5.5.0.20241111"
$packageUrl = "https://community.chocolatey.org/api/v2/package/tesseract/$packageVersion"
$expectedPackageSha256 = "56659a4c01e6ea75a0b710ba7e8bb16e9cc6675978d2861323751812aeea6183"
$installerName = "tesseract-ocr-w64-setup-$packageVersion.exe"

$runnerTemp = if (-not [string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
  [System.IO.Path]::GetFullPath($env:RUNNER_TEMP)
} else {
  [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
}
$workRoot = Join-Path $runnerTemp ("ssmaker-tesseract-" + [guid]::NewGuid().ToString("N"))
$packagePath = Join-Path $workRoot "tesseract.nupkg"
$extractRoot = Join-Path $workRoot "package"
New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null

Invoke-WebRequest -Uri $packageUrl -OutFile $packagePath -UseBasicParsing
$actualPackageSha256 = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualPackageSha256 -ne $expectedPackageSha256) {
  throw "Pinned Tesseract package hash mismatch (expected $expectedPackageSha256, got $actualPackageSha256)."
}

[System.IO.Compression.ZipFile]::ExtractToDirectory($packagePath, $extractRoot)
$installer = Join-Path $extractRoot "tools\$installerName"
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
  throw "Pinned Tesseract installer is missing from the verified package: $installer"
}

$install = Start-Process `
  -FilePath $installer `
  -ArgumentList "/S" `
  -Wait `
  -PassThru `
  -WindowStyle Hidden
if ($install.ExitCode -ne 0) {
  throw "Pinned Tesseract installer failed with exit code $($install.ExitCode)."
}

$candidates = @(
  "C:\Program Files\Tesseract-OCR\tesseract.exe",
  "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
)
$tesseractExe = $candidates | Where-Object {
  Test-Path -LiteralPath $_ -PathType Leaf
} | Select-Object -First 1
if (-not $tesseractExe) {
  throw "Tesseract executable was not found after the pinned package installation."
}

$tesseractRoot = Split-Path $tesseractExe -Parent
if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_PATH)) {
  $tesseractRoot | Out-File -FilePath $env:GITHUB_PATH -Encoding utf8 -Append
}
Write-Host "Pinned Tesseract package verified and installed: $tesseractExe"
& $tesseractExe --version
