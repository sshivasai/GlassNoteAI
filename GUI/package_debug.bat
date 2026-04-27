@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  GlassNote -- DEBUG BUILD (with detailed logging)
echo ============================================================
echo.

REM ── Navigate to script directory ─────────────────────────────────────────────
cd /d "%~dp0"

REM ── Check Python ──────────────────────────────────────────────────────────────
echo [DEBUG] Checking for Python...
where python
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    pause
    exit /b 1
)

python --version
python -c "import platform; print('Architecture:', platform.machine())"
echo.

REM ── Create venv ───────────────────────────────────────────────────────────────
echo [DEBUG] Creating virtual environment...
if exist ".venv-build" (
    echo [DEBUG] Removing old .venv-build...
    rmdir /s /q ".venv-build"
)

python -m venv .venv-build
echo [DEBUG] venv creation exit code: %errorlevel%
if errorlevel 1 (
    echo [ERROR] venv creation failed!
    pause
    exit /b 1
)

REM ── Activate venv ─────────────────────────────────────────────────────────────
echo [DEBUG] Activating venv...
if not exist ".venv-build\Scripts\activate.bat" (
    echo [ERROR] activate.bat not found!
    pause
    exit /b 1
)

call .venv-build\Scripts\activate.bat
echo [DEBUG] Activation exit code: %errorlevel%
echo [DEBUG] Python location after activation:
where python
echo.

REM ── Upgrade pip ───────────────────────────────────────────────────────────────
echo [DEBUG] Upgrading pip...
python -m pip install --upgrade pip
echo [DEBUG] pip upgrade exit code: %errorlevel%
echo.

REM ── Install sounddevice ───────────────────────────────────────────────────────
echo [DEBUG] Installing sounddevice==0.4.6...
pip install "sounddevice==0.4.6"
echo [DEBUG] sounddevice install exit code: %errorlevel%
echo.

REM ── Test sounddevice import ───────────────────────────────────────────────────
echo [DEBUG] Testing sounddevice import...
echo [DEBUG] Running: python -c "import sounddevice; print('Import successful')"
python -c "import sounddevice; print('Import successful')"
set SD_EXIT=%errorlevel%
echo [DEBUG] Import test exit code: %SD_EXIT%

if %SD_EXIT% neq 0 (
    echo.
    echo [ERROR] sounddevice import FAILED!
    echo [DEBUG] This is the error that stops the script.
    echo.
    echo [DEBUG] Trying to get more info...
    python -c "import sys; print('Python:', sys.executable); print('Version:', sys.version)"
    echo.
    echo [DEBUG] Trying import with traceback...
    python -c "import sounddevice"
    echo.
    call deactivate
    pause
    exit /b 1
)
echo [DEBUG] sounddevice import succeeded!
echo.

REM ── Install remaining dependencies ────────────────────────────────────────────
echo [DEBUG] Installing remaining dependencies...
pip install -r requirements.txt
echo [DEBUG] requirements.txt install exit code: %errorlevel%
echo.

REM ── Run build ─────────────────────────────────────────────────────────────────
echo [DEBUG] Running build.py...
python build.py
set BUILD_EXIT=%errorlevel%
echo [DEBUG] build.py exit code: %BUILD_EXIT%

call deactivate

echo.
echo ============================================================
if %BUILD_EXIT% equ 0 (
    echo  BUILD SUCCESSFUL
    echo  Check dist\svchost_audio.exe
) else (
    echo  BUILD FAILED (exit code: %BUILD_EXIT%)
)
echo ============================================================
echo.
pause
