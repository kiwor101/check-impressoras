param(
    [string]$Version = "1.0.0",
    [switch]$SkipPipInstall
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$appName = "Check Impressoras"
$releaseDir = Join-Path $root "release"
$payloadDir = Join-Path $root "build\installer_payload"

Set-Location $root

if (-not $SkipPipInstall) {
    python -m pip install --upgrade pyinstaller
}

$pyArch = python -c "import platform; print(platform.architecture()[0])"
$runtime = if ($pyArch -match "32") { "win-x86" } else { "win-x64" }
$installerBaseName = "Check-Impressoras-Setup-$Version-$runtime"
$installerPath = Join-Path $releaseDir "$installerBaseName.exe"

Remove-Item -LiteralPath (Join-Path $root "build") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $root "dist") -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $payloadDir | Out-Null

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "$appName" `
    --icon "app_icon.ico" `
    --add-data "app_icon.ico;." `
    "check_impressoras_gui.py"

Copy-Item -LiteralPath (Join-Path $root "dist\$appName.exe") -Destination (Join-Path $payloadDir "CheckImpressoras.exe") -Force
Copy-Item -LiteralPath (Join-Path $root "app_icon.ico") -Destination (Join-Path $payloadDir "app_icon.ico") -Force

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "$installerBaseName" `
    --icon "app_icon.ico" `
    --add-data "$payloadDir\CheckImpressoras.exe;." `
    --add-data "$payloadDir\app_icon.ico;." `
    "installer\installer_app.py"

Copy-Item -LiteralPath (Join-Path $root "dist\$installerBaseName.exe") -Destination $installerPath -Force

Write-Host "EXE do app: $(Join-Path $root "dist\$appName.exe")"
Write-Host "Instalador: $installerPath"
Write-Host "Runtime: $runtime"

