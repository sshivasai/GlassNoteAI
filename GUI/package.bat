@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  GlassNote -- Clean Isolated Build
echo ============================================================
echo.

REM ── Locate Python ────────────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Please install Python 3.11+.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PY_VER=%%i
echo  Found: %PY_VER%

REM ── Detect Python architecture ────────────────────────────────────────────────
for /f "tokens=*" %%a in ('python -c "import platform; print(platform.machine())"') do set PY_ARCH=%%a
echo  Architecture: %PY_ARCH%
echo.

REM ── WARN if building with ARM64 Python ───────────────────────────────────────
if /i "%PY_ARCH%"=="ARM64" (
    echo  *** ARCHITECTURE WARNING ***
    echo.
    echo  You are using ARM64 Python. This will produce an ARM64 .exe
    echo  that ONLY runs on ARM64 Windows machines.
    echo.
    echo  For an .exe that works on ALL Windows machines ^(x64 + ARM64^):
    echo    1. Install x64 Python 3.11 from https://python.org/downloads/
    echo       ^(Choose "Windows installer (64-bit^)" -- NOT ARM64^)
    echo    2. Re-run this script using that Python version.
    echo.
    echo  Press any key to continue anyway with ARM64, or close to cancel.
    pause
    echo.
)

REM ── Navigate to script directory ─────────────────────────────────────────────
cd /d "%~dp0"

REM ── Clean old virtual env ────────────────────────────────────────────────────
if exist ".venv-build" (
    echo  Removing old build environment...
    rmdir /s /q ".venv-build"
)

REM ── Create fresh isolated virtual environment ─────────────────────────────────
echo  Creating clean virtual environment (.venv-build)...
python -m venv .venv-build
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

REM ── Activate the virtual environment ─────────────────────────────────────────
call .venv-build\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

REM ── Upgrade pip silently ──────────────────────────────────────────────────────
echo  Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNING] Failed to upgrade pip, continuing anyway...
)

REM ── Install sounddevice 0.4.6 FIRST ───────────────────────────────────────────
echo  Installing sounddevice 0.4.6 (PortAudio stability fix)...
pip install "sounddevice==0.4.6" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install sounddevice 0.4.6.
    call deactivate
    pause
    exit /b 1
)

REM ── Verify PortAudio loads ────────────────────────────────────────────────────
echo  Verifying PortAudio DLL loads...
python -c "import sounddevice; print('OK')" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] PortAudio DLL failed to load.
    echo  This is an ARM64/x64 DLL mismatch. Try building with x64 Python instead.
    echo  Download: https://www.python.org/downloads/ (pick "Windows installer 64-bit")
    echo.
    call deactivate
    pause
    exit /b 1
)
echo   OK

REM ── Install all remaining dependencies ───────────────────────────────────────
echo  Installing remaining dependencies from requirements.txt...
echo  (This may take 2-5 minutes on first run...)
echo.
pip install -r requirements.txt
set INSTALL_EXIT=%errorlevel%
if %INSTALL_EXIT% neq 0 (
    echo.
    echo [ERROR] Dependency installation failed with exit code %INSTALL_EXIT%.
    call deactivate
    pause
    exit /b 1
)
echo.
echo   All dependencies installed successfully.

REM ── Run the build script ──────────────────────────────────────────────────────
echo.
echo  Running build.py...
echo.
python build.py
set BUILD_EXIT=%errorlevel%

REM ── Deactivate venv ───────────────────────────────────────────────────────────
call deactivate

echo.
if %BUILD_EXIT% equ 0 (
    echo ============================================================
    echo  BUILD SUCCESSFUL
    echo  Architecture: %PY_ARCH%
    echo  Exe:          dist\svchost_audio.exe
    echo  Installer:    dist\GlassNote_Setup.iss
    echo.
    if /i "%PY_ARCH%"=="ARM64" (
        echo  NOTE: This ARM64 exe only runs on ARM64 Windows.
        echo  For an exe that works on ALL Windows, rebuild with x64 Python.
    ) else (
        echo  This x64 exe runs on both x64 and ARM64 Windows.
    )
    echo.
    echo  Next steps:
    echo    1. Test: dist\svchost_audio.exe
    echo    2. (Optional) Create installer with Inno Setup
    echo       Download: https://jrsoftware.org/isinfo.php
    echo       Then run: iscc "dist\GlassNote_Setup.iss"
    echo ============================================================
) else (
    echo ============================================================
    echo  BUILD FAILED  (exit code: %BUILD_EXIT%)
    echo  Check the output above for errors.
    echo ============================================================
)

echo.
pause
