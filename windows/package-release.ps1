[CmdletBinding()]
param(
    [string]$Version = "0.4.1",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $SkipBuild) {
    & "$PSScriptRoot\build-app.ps1" -Version $Version
}

$BuiltApp = Join-Path $Root "dist\windows\CUKTECH Screen Controller"
if (-not (Test-Path (Join-Path $BuiltApp "CUKTECH Screen Controller.exe"))) {
    throw "Run windows/build-app.ps1 first."
}
$ReadmeCandidates = @(
    Get-ChildItem -LiteralPath $PSScriptRoot -File -Filter "*-Windows.txt"
)
if ($ReadmeCandidates.Count -ne 1) {
    throw "Expected exactly one localized Windows README, found $($ReadmeCandidates.Count)."
}

$StageName = "CUKTECH-Screen-Controller-$Version-Windows-x64"
$Stage = Join-Path $Root "dist\$StageName"
$Zip = Join-Path $Root "dist\$StageName.zip"
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
if (Test-Path $Zip) { Remove-Item -Force $Zip }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
Copy-Item -Recurse -Force $BuiltApp (Join-Path $Stage "App")
Copy-Item -Force "$PSScriptRoot\Install CUKTECH Screen Controller.cmd" $Stage
Copy-Item -Force "$PSScriptRoot\Install-CUKTECHScreenController.ps1" $Stage
Copy-Item -Force "$PSScriptRoot\Uninstall-CUKTECHScreenController.ps1" $Stage
$StagedReadme = Join-Path $Stage "README-Windows.zh-CN.txt"
Copy-Item -LiteralPath $ReadmeCandidates[0].FullName -Destination $StagedReadme -Force
Copy-Item -Force "$PSScriptRoot\mi-credentials.example.json" $Stage
Copy-Item -Force "$PSScriptRoot\THIRD-PARTY-NOTICES.txt" $Stage
Copy-Item -Force (Join-Path $Root "LICENSE") (Join-Path $Stage "PROJECT-LICENSE.txt")

(Get-Content -LiteralPath $StagedReadme -Raw).Replace("{{VERSION}}", $Version) |
    Set-Content -Encoding UTF8 -LiteralPath $StagedReadme
(Get-Content (Join-Path $Stage "Install-CUKTECHScreenController.ps1") -Raw).Replace("{{VERSION}}", $Version) |
    Set-Content -Encoding UTF8 (Join-Path $Stage "Install-CUKTECHScreenController.ps1")

@{
    name = "CUKTECH Screen Controller"
    version = $Version
    platform = "Windows x64"
    packager = "PyInstaller"
} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Stage "BUILD-MANIFEST.json")

Compress-Archive -Path $Stage -DestinationPath $Zip -CompressionLevel Optimal
$Hash = (Get-FileHash -Algorithm SHA256 $Zip).Hash.ToLowerInvariant()
"$Hash  $StageName.zip" | Set-Content -Encoding ASCII "$Zip.sha256"
Write-Host "Package: $Zip"
Write-Host "SHA-256: $Hash"
