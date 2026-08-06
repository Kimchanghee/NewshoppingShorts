[CmdletBinding()]
param(
  [string]$SourceDir = "",
  [string]$OutputDir = "",
  [string]$IdentityName = "",
  [string]$Publisher = "",
  [string]$PublisherDisplayName = "",
  [string]$DisplayName = "SSMaker",
  [string]$Description = "AI shopping shorts production and publishing automation",
  [string]$Version = "",
  [string]$MakeAppxPath = "",
  [switch]$AllowDevelopmentIdentity,
  [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][string[]]$Lines
  )

  $encoding = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllLines($Path, $Lines, $encoding)
}

function ConvertTo-XmlAttribute {
  param([Parameter(Mandatory = $true)][string]$Value)

  return [System.Security.SecurityElement]::Escape($Value)
}

function ConvertTo-MsixVersion {
  param([Parameter(Mandatory = $true)][string]$Value)

  if ($Value -notmatch '^(\d+)\.(\d+)\.(\d+)(?:\.\d+)?$') {
    throw "MSIX version must contain three numeric parts (for example 1.5.46): $Value"
  }

  $parts = @([int]$Matches[1], [int]$Matches[2], [int]$Matches[3])
  if ($parts[0] -lt 1 -or $parts[0] -gt 65535) {
    throw "MSIX major version must be between 1 and 65535: $Value"
  }
  foreach ($part in $parts[1..2]) {
    if ($part -lt 0 -or $part -gt 65535) {
      throw "MSIX version parts must be between 0 and 65535: $Value"
    }
  }

  # Microsoft Store reserves the fourth field and requires publisher builds
  # to submit zero in that position.
  return "$($parts[0]).$($parts[1]).$($parts[2]).0"
}

function Find-MakeAppx {
  param([string]$PreferredPath)

  $candidates = New-Object System.Collections.Generic.List[string]
  if (-not [string]::IsNullOrWhiteSpace($PreferredPath)) {
    $candidates.Add($PreferredPath)
  }
  if (-not [string]::IsNullOrWhiteSpace($env:MAKEAPPX_PATH)) {
    $candidates.Add($env:MAKEAPPX_PATH.Trim())
  }
  $command = Get-Command makeappx.exe -ErrorAction SilentlyContinue
  if ($command -and $command.Source) {
    $candidates.Add($command.Source)
  }
  $candidates.Add("C:\Program Files (x86)\Windows Kits\10\App Certification Kit\makeappx.exe")

  $sdkRoot = "C:\Program Files (x86)\Windows Kits\10\bin"
  if (Test-Path $sdkRoot) {
    Get-ChildItem -Path $sdkRoot -Directory -ErrorAction SilentlyContinue |
      Sort-Object Name -Descending |
      ForEach-Object { $candidates.Add((Join-Path $_.FullName "x64\makeappx.exe")) }
  }

  return $candidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
    Select-Object -First 1
}

function New-MsixLogo {
  param(
    [Parameter(Mandatory = $true)][System.Drawing.Bitmap]$SourceBitmap,
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][int]$Width,
    [Parameter(Mandatory = $true)][int]$Height
  )

  $bitmap = New-Object System.Drawing.Bitmap($Width, $Height)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  try {
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality

    $iconSize = [Math]::Max(1, [int]([Math]::Min($Width, $Height) * 0.76))
    $x = [int](($Width - $iconSize) / 2)
    $y = [int](($Height - $iconSize) / 2)
    $graphics.DrawImage($SourceBitmap, $x, $y, $iconSize, $iconSize)
    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
  } finally {
    $graphics.Dispose()
    $bitmap.Dispose()
  }
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($SourceDir)) {
  $SourceDir = Join-Path $Root "dist\ssmaker"
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $Root "dist\store"
}
if ([string]::IsNullOrWhiteSpace($IdentityName)) {
  if ($null -ne $env:MSIX_IDENTITY_NAME) {
    $IdentityName = $env:MSIX_IDENTITY_NAME.Trim()
  }
}
if ([string]::IsNullOrWhiteSpace($Publisher)) {
  if ($null -ne $env:MSIX_PUBLISHER) {
    $Publisher = $env:MSIX_PUBLISHER.Trim()
  }
}
if ([string]::IsNullOrWhiteSpace($PublisherDisplayName)) {
  if ($null -ne $env:MSIX_PUBLISHER_DISPLAY_NAME) {
    $PublisherDisplayName = $env:MSIX_PUBLISHER_DISPLAY_NAME.Trim()
  }
}

if ($AllowDevelopmentIdentity) {
  if ([string]::IsNullOrWhiteSpace($IdentityName)) {
    $IdentityName = "SSMaker.StorePreview"
  }
  if ([string]::IsNullOrWhiteSpace($Publisher)) {
    $Publisher = "CN=SSMaker Store Preview"
  }
  if ([string]::IsNullOrWhiteSpace($PublisherDisplayName)) {
    $PublisherDisplayName = "SSMaker"
  }
}

if ([string]::IsNullOrWhiteSpace($IdentityName) -or [string]::IsNullOrWhiteSpace($Publisher)) {
  throw "Partner Center identity is required. Pass -IdentityName and -Publisher exactly as shown under Product identity."
}
if ([string]::IsNullOrWhiteSpace($PublisherDisplayName)) {
  throw "Publisher display name is required. Pass -PublisherDisplayName."
}
if ($IdentityName -notmatch '^[A-Za-z0-9.-]{3,50}$') {
  throw "Invalid MSIX identity name: $IdentityName"
}

$SourceDir = (Resolve-Path -LiteralPath $SourceDir).Path
$ssmakerExe = Join-Path $SourceDir "ssmaker.exe"
if (-not (Test-Path -LiteralPath $ssmakerExe -PathType Leaf)) {
  throw "Store payload is missing ssmaker.exe: $ssmakerExe"
}

if ([string]::IsNullOrWhiteSpace($Version)) {
  $versionJson = Join-Path $SourceDir "version.json"
  if (-not (Test-Path -LiteralPath $versionJson -PathType Leaf)) {
    $versionJson = Join-Path $Root "version.json"
  }
  $Version = (Get-Content -LiteralPath $versionJson -Raw | ConvertFrom-Json).version
}
$msixVersion = ConvertTo-MsixVersion -Value $Version.Trim()

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$OutputDir = (Resolve-Path -LiteralPath $OutputDir).Path
$templatePath = Join-Path $Root "packaging\msix\AppxManifest.xml.in"
if (-not (Test-Path -LiteralPath $templatePath -PathType Leaf)) {
  throw "MSIX manifest template not found: $templatePath"
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ssmaker-msix-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot | Out-Null

try {
  $assetsDir = Join-Path $tempRoot "Assets"
  New-Item -ItemType Directory -Path $assetsDir | Out-Null

  $manifest = Get-Content -LiteralPath $templatePath -Raw
  $replacements = @{
    "@@IDENTITY_NAME@@" = ConvertTo-XmlAttribute $IdentityName
    "@@PUBLISHER@@" = ConvertTo-XmlAttribute $Publisher
    "@@VERSION@@" = ConvertTo-XmlAttribute $msixVersion
    "@@DISPLAY_NAME@@" = ConvertTo-XmlAttribute $DisplayName
    "@@PUBLISHER_DISPLAY_NAME@@" = ConvertTo-XmlAttribute $PublisherDisplayName
    "@@DESCRIPTION@@" = ConvertTo-XmlAttribute $Description
  }
  foreach ($placeholder in $replacements.Keys) {
    $manifest = $manifest.Replace($placeholder, $replacements[$placeholder])
  }
  if ($manifest -match '@@[A-Z_]+@@') {
    throw "Unresolved placeholder in MSIX manifest: $($Matches[0])"
  }

  $manifestPath = Join-Path $tempRoot "AppxManifest.xml"
  Write-Utf8NoBom -Path $manifestPath -Lines @($manifest)
  [xml](Get-Content -LiteralPath $manifestPath -Raw) | Out-Null

  Add-Type -AssemblyName System.Drawing
  $icon = [System.Drawing.Icon]::ExtractAssociatedIcon($ssmakerExe)
  if (-not $icon) {
    $iconPath = Join-Path $Root "resource\app_icon.ico"
    $icon = New-Object -TypeName System.Drawing.Icon -ArgumentList $iconPath
  }
  $sourceBitmap = $icon.ToBitmap()
  try {
    New-MsixLogo $sourceBitmap (Join-Path $assetsDir "StoreLogo.png") 50 50
    New-MsixLogo $sourceBitmap (Join-Path $assetsDir "Square44x44Logo.png") 44 44
    New-MsixLogo $sourceBitmap (Join-Path $assetsDir "Square150x150Logo.png") 150 150
    New-MsixLogo $sourceBitmap (Join-Path $assetsDir "Wide310x150Logo.png") 310 150
    New-MsixLogo $sourceBitmap (Join-Path $assetsDir "Square310x310Logo.png") 310 310
  } finally {
    $sourceBitmap.Dispose()
    $icon.Dispose()
  }

  $reservedNames = @(
    "AppxManifest.xml",
    "AppxBlockMap.xml",
    "AppxSignature.p7x",
    "[Content_Types].xml"
  )
  $mapping = New-Object System.Collections.Generic.List[string]
  $mapping.Add("[Files]")
  foreach ($file in Get-ChildItem -LiteralPath $SourceDir -Recurse -File | Sort-Object FullName) {
    $relative = $file.FullName.Substring($SourceDir.Length + 1)
    if ($reservedNames -contains $relative) {
      throw "Store payload contains reserved package file: $relative"
    }
    $mapping.Add(('"{0}" "{1}"' -f $file.FullName, $relative))
  }
  $mapping.Add(('"{0}" "AppxManifest.xml"' -f $manifestPath))
  foreach ($asset in Get-ChildItem -LiteralPath $assetsDir -File | Sort-Object Name) {
    $mapping.Add(('"{0}" "Assets\{1}"' -f $asset.FullName, $asset.Name))
  }
  $mappingPath = Join-Path $tempRoot "mapping.txt"
  Write-Utf8NoBom -Path $mappingPath -Lines $mapping.ToArray()

  Write-Host "MSIX identity: $IdentityName"
  Write-Host "MSIX publisher: $Publisher"
  Write-Host "MSIX version: $msixVersion"
  Write-Host "Payload files: $($mapping.Count - 7)"

  if ($ValidateOnly) {
    Write-Host "MSIX manifest, assets, and payload mapping validation passed."
    return
  }

  $makeappx = Find-MakeAppx -PreferredPath $MakeAppxPath
  if (-not $makeappx) {
    throw "makeappx.exe not found. Install the Windows 10/11 SDK or pass -MakeAppxPath."
  }

  $outputPath = Join-Path $OutputDir "SSMaker_${msixVersion}_x64.msix"
  & $makeappx pack /o /f $mappingPath /p $outputPath
  if ($LASTEXITCODE -ne 0) {
    throw "MakeAppx failed with exit code $LASTEXITCODE"
  }
  if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "MakeAppx did not create the expected package: $outputPath"
  }

  $hash = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant()
  $sizeMb = [Math]::Round((Get-Item -LiteralPath $outputPath).Length / 1MB, 1)
  Write-Host "Microsoft Store submission package created: $outputPath (${sizeMb} MB)"
  Write-Host "SHA256: $hash"
} finally {
  $tempFull = [System.IO.Path]::GetFullPath($tempRoot)
  $systemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
  if ($tempFull.StartsWith($systemTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $tempFull -Recurse -Force -ErrorAction SilentlyContinue
  }
}
