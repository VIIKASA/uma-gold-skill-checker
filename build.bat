@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    where py >nul 2>nul
    if errorlevel 1 (
        echo Python 3 is required to build this application.
        goto :failed
    )
    py -3 -m venv "%~dp0.venv"
    if errorlevel 1 goto :failed
)

"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :failed

"%VENV_PY%" -m pip install -r requirements.txt "pyinstaller>=6.11"
if errorlevel 1 goto :failed

"%VENV_PY%" -m PyInstaller --noconfirm --clean UmaGoldSkill.spec
if errorlevel 1 goto :failed

echo.
echo Build complete: dist\UmaGoldSkill.exe
exit /b 0

:failed
echo.
echo Build failed. Review the error above.
pause
exit /b 1