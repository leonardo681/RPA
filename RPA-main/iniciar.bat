@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Crie o ambiente virtual e instale requirements.txt conforme README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" desktop.py
if errorlevel 1 pause
