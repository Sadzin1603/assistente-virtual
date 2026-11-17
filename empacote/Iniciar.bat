@echo off
chcp 65001 >nul
title Jarvis
cd /d "%~dp0"
if not exist "runtime\python.exe" (
  echo Extraia o zip inteiro para uma pasta antes de abrir este arquivo.
  pause
  exit /b 1
)
"runtime\python.exe" lancador.py %*
echo.
pause
