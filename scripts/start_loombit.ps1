# start_loombit.ps1 - Arranque solido de Loombit Operator (sin recompilar nada).
#
# Ejecuta el codigo VIVO del repo con el interprete pinneado del venv (.venv, Python 3.12),
# no el `py` global (que en esta maquina apunta al 3.14t free-threaded, inestable para
# pywin32/pystray). Lo invoca Loombit.vbs de forma oculta; tambien vale a mano.
#
# Solido por diseno: elige el interprete con fallback, registra el arranque, y delega en
# launcher.py (que hace instancia unica, log a fichero y MessageBox si algo falla).
#
# NOTA: este fichero es ASCII puro a proposito (Windows PowerShell 5.1 rompe con no-ASCII).

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

function Find-Pythonw {
    # 1) venv del repo (lo normal). 2) Python 3.12 del usuario. 3) cualquier pythonw del PATH.
    $candidatos = @(
        (Join-Path $repo ".venv\Scripts\pythonw.exe"),
        "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
    )
    foreach ($c in $candidatos) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$logDir = Join-Path $repo "runtime\local"
New-Item -ItemType Directory -Force $logDir | Out-Null
$startLog = Join-Path $logDir "launcher_start.log"

$pyw = Find-Pythonw
if (-not $pyw) {
    $msg = "Loombit: no se encontro Python. Crea el entorno con scripts\setup_venv.ps1."
    "$(Get-Date -Format o)  ERROR  $msg" | Out-File $startLog -Append -Encoding utf8
    (New-Object -ComObject WScript.Shell).Popup($msg, 0, "Loombit Operator", 0x10) | Out-Null
    exit 1
}

"$(Get-Date -Format o)  start  python=$pyw" | Out-File $startLog -Append -Encoding utf8

# Lanza el launcher (servidor + bandeja + navegador). Oculto: launcher.py registra y avisa.
Start-Process -FilePath $pyw `
    -ArgumentList "-m", "loombit_operator.launcher" `
    -WorkingDirectory $repo `
    -WindowStyle Hidden
