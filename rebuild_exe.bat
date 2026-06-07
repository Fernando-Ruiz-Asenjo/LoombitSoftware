@echo off
echo ============================================
echo  Loombit — Rebuild ejecutable
echo ============================================
cd /d "%~dp0"

echo.
echo [1/3] Verificando sintaxis Python...
python -m py_compile loombit_operator\tools\base.py && echo base.py OK
python -m py_compile loombit_operator\agent\memory.py && echo memory.py OK
python -m py_compile loombit_operator\agent\loop.py && echo loop.py OK
python -m py_compile loombit_operator\skill_blanca_gmail.py && echo gmail.py OK

echo.
echo [2/3] Limpiando build anterior...
if exist dist\Loombit rmdir /s /q dist\Loombit
if exist build\loombit rmdir /s /q build\loombit

echo.
echo [3/3] Compilando con PyInstaller...
pyinstaller loombit.spec

echo.
if exist dist\Loombit\Loombit.exe (
    echo ============================================
    echo  EXITO: dist\Loombit\Loombit.exe creado
    echo ============================================
    echo Prueba: doble click en dist\Loombit\Loombit.exe
) else (
    echo ERROR: El ejecutable no se creo. Revisa el log arriba.
)
pause
