$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$shortcutPath = Join-Path $baseDir "Abrir Check Impressoras.lnk"
$vbsPath = Join-Path $baseDir "Abrir Check Impressoras.vbs"
$iconPath = Join-Path $baseDir "app_icon.ico"
$wscriptPath = Join-Path $env:WINDIR "System32\wscript.exe"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $wscriptPath
$shortcut.Arguments = '"' + $vbsPath + '"'
$shortcut.WorkingDirectory = $baseDir
$shortcut.IconLocation = $iconPath
$shortcut.Description = "Abrir Check Impressoras"
$shortcut.Save()

Write-Host "Atalho criado: $shortcutPath"

