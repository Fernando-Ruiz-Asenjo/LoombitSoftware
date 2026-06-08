# install_desktop_shortcut.ps1 - crea (o actualiza) el acceso directo "Loombit" en el escritorio.
#
# El acceso directo ejecuta wscript -> Loombit.vbs (oculto) -> start_loombit.ps1 -> launcher.py.
# Apunta al codigo vivo del repo: NO hay que recompilar nada al cambiar el codigo.
# Idempotente: vuelve a ejecutarlo cuando quieras para refrescar icono/ruta.
#
# NOTA: ASCII puro a proposito (Windows PowerShell 5.1 rompe con no-ASCII).

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$vbs = Join-Path $repo "Loombit.vbs"
$ico = Join-Path $repo "loombit_operator\assets\loombit.ico"

if (-not (Test-Path $vbs)) { throw "No existe $vbs" }

$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "Loombit.lnk"

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnkPath)
$sc.TargetPath = Join-Path $env:WINDIR "System32\wscript.exe"
$sc.Arguments = '"' + $vbs + '"'
$sc.WorkingDirectory = $repo
if (Test-Path $ico) { $sc.IconLocation = $ico }
$sc.Description = "Loombit Operator - operador de IA local-first"
$sc.WindowStyle = 7  # minimizado (wscript no muestra ventana de todas formas)
$sc.Save()

Write-Host "Acceso directo creado: $lnkPath" -ForegroundColor Green
Write-Host ("  -> wscript " + $vbs + " (icono: " + $ico + ")") -ForegroundColor Gray
