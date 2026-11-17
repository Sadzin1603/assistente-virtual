@echo off
rem Atalho da pasta de desenvolvimento. O .venv so funciona no PC onde foi criado;
rem em qualquer outro, este arquivo passa a vez para o pacote portatil em dist\.
cd /d "%~dp0"
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
set PYTHONWARNINGS=ignore
".venv\Scripts\python.exe" -c "" >nul 2>&1
if not errorlevel 1 (
  ".venv\Scripts\python.exe" main.py %*
  pause
  exit /b
)
if exist "dist\AssistenteVirtual\Iniciar.bat" (
  call "dist\AssistenteVirtual\Iniciar.bat" %*
  exit /b
)
echo Esta e a pasta de desenvolvimento e o Python dela so existe no PC original.
echo Use o pacote portatil: extraia AssistenteVirtual-Portatil.zip e abra Iniciar.bat.
pause
