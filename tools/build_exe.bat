@echo off
rem Builds dist\JackBOTS.exe (needs Python 3.11+). config\ is not bundled, so your keys never get into the exe.
chcp 65001 >nul
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" python -m venv .venv || exit /b 1
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt pyinstaller || exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean jackbots.spec || exit /b 1
echo Done: dist\JackBOTS.exe
