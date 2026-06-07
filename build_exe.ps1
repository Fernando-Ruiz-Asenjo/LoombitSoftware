# build_exe.ps1 — Compila Loombit Operator en un ejecutable Windows
# Uso: .\build_exe.ps1
# Resultado: dist\Loombit\Loombit.exe

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Loombit Operator — Build EXE" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Verificar Python ───────────────────────────────────────────────────────
Write-Host "[1/5] Verificando Python..." -ForegroundColor Yellow
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    Write-Host "ERROR: Python no encontrado en PATH" -ForegroundColor Red
    exit 1
}
$pyVersion = & python --version 2>&1
Write-Host "  OK: $pyVersion" -ForegroundColor Green

# ── 2. Instalar dependencias de build ─────────────────────────────────────────
Write-Host ""
Write-Host "[2/5] Instalando pyinstaller y pystray..." -ForegroundColor Yellow
python -m pip install --quiet pyinstaller pystray pillow
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR al instalar dependencias" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: dependencias instaladas" -ForegroundColor Green

# ── 3. Generar icono ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/5] Generando icono Loombit..." -ForegroundColor Yellow
python scripts/generate_icon.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR al generar icono" -ForegroundColor Red
    exit 1
}
Write-Host "  OK: icono generado en loombit_operator/assets/" -ForegroundColor Green

# ── 4. Limpiar build anterior ─────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/5] Limpiando build anterior..." -ForegroundColor Yellow
if (Test-Path "dist\Loombit") { Remove-Item -Recurse -Force "dist\Loombit" }
if (Test-Path "build\Loombit") { Remove-Item -Recurse -Force "build\Loombit" }
Write-Host "  OK: limpio" -ForegroundColor Green

# ── 5. Compilar con PyInstaller ───────────────────────────────────────────────
Write-Host ""
Write-Host "[5/5] Compilando con PyInstaller..." -ForegroundColor Yellow
Write-Host "  (esto puede tardar 1-3 minutos)" -ForegroundColor Gray
python -m PyInstaller loombit.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: PyInstaller falló. Revisa los logs arriba." -ForegroundColor Red
    exit 1
}

# ── Resultado ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  BUILD COMPLETADO" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
$exePath = Resolve-Path "dist\Loombit\Loombit.exe" -ErrorAction SilentlyContinue
if ($exePath) {
    $size = (Get-Item $exePath).Length / 1MB
    Write-Host "  Exe: $exePath" -ForegroundColor White
    Write-Host "  Tamaño: $([Math]::Round($size, 1)) MB" -ForegroundColor White
    Write-Host ""
    Write-Host "  Para lanzar: doble clic en Loombit.exe" -ForegroundColor Cyan
    Write-Host "  El icono aparece en la bandeja del sistema." -ForegroundColor Cyan
} else {
    Write-Host "  ADVERTENCIA: no se encontró el exe en dist\Loombit\" -ForegroundColor Yellow
}
Write-Host ""
