# setup_venv.ps1 - crea/reconstruye el entorno pinneado de Loombit (.venv con Python 3.12).
#
# Por que 3.12 y no el `py` por defecto: en esta maquina el `py` global apunta a 3.14t
# (free-threaded, experimental), inestable para extensiones C como pywin32/pystray - esa era
# una causa de que el arranque "se rompiera". El venv fija un interprete estable y sus deps.
#
# Reproducible: si algun dia se borra .venv, ejecuta este script y vuelve a quedar igual.
#
# NOTA: ASCII puro a proposito (Windows PowerShell 5.1 rompe con no-ASCII).

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $repo ".venv"

Write-Host "Creando venv (Python 3.12) en $venv ..." -ForegroundColor Cyan
py -3.12 -m venv $venv
$py = Join-Path $venv "Scripts\python.exe"

Write-Host "Actualizando pip e instalando dependencias..." -ForegroundColor Cyan
& $py -m pip install --upgrade pip
& $py -m pip install -r (Join-Path $repo "requirements.txt")

Write-Host "Verificando importaciones criticas..." -ForegroundColor Cyan
& $py -c "import fastapi, uvicorn, pystray, PIL, keyring, cryptography, win32gui, googleapiclient; print('OK: dependencias listas')"

Write-Host "Entorno listo. Crea el acceso directo con scripts\install_desktop_shortcut.ps1" -ForegroundColor Green
