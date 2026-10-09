@echo off
rem JackBOTS: run from source. The first run creates .venv and installs the dependencies.
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the .venv environment ...
    python -m venv .venv || goto :no_python
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || goto :pip_failed
".venv\Scripts\python.exe" -m app %*
pause
exit /b

:no_python
echo Python 3.11+ not found. Install it from https://www.python.org/downloads/ (check "Add to PATH").
pause
exit /b 1

:pip_failed
echo Could not install the dependencies - check your internet connection and try again.
pause
exit /b 1
