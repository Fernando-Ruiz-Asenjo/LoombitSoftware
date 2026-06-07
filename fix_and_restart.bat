@echo off
echo ===================================================
echo  Loombit - Fix pywin32 + Restart Server
echo ===================================================

echo.
echo [1/3] Ejecutando pywin32 post-install...
python -m pywin32_postinstall -install
echo.

echo [2/3] Parando proceso en puerto 8787...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8787 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F 2>nul
)
timeout /t 2 /nobreak > nul

echo [3/3] Iniciando Loombit Operator...
cd /d "C:\Users\fernando\loombit-new"
start "Loombit Server" cmd /k "uvicorn loombit_operator.main:app --host 127.0.0.1 --port 8787 --reload"

echo.
echo Servidor iniciado. Verificando en 5 segundos...
timeout /t 5 /nobreak > nul
python -c "import httpx; r=httpx.get('http://127.0.0.1:8787/health',timeout=3); print('SERVER OK:', r.json())"
echo.
pause
