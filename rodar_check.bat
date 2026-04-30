@echo off
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw ".\check_impressoras_gui.py"
  exit /b
) 

where python >nul 2>nul
if %errorlevel%==0 (
  start "" python ".\check_impressoras_gui.py"
) else (
  start "" py ".\check_impressoras_gui.py"
)
