@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo  GlassNote — Clean Isolated Build
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
echo.

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
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

REM ── Activate the virtual environment ─────────────────────────────────────────
call .venv-build\Scripts\activate.bat

REM ── Upgrade pip silently ──────────────────────────────────────────────────────
echo  Upgrading pip...
python -m pip install --upgrade pip --quiet

REM ── Install all dependencies ──────────────────────────────────────────────────
echo  Installing dependencies from requirements.txt...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    call deactivate
    pause
    exit /b 1
)

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
    echo  Exe:      dist\svchost_audio.exe
    echo  Installer: dist\GlassNote_Setup.iss
    echo.
    echo  Next steps:
    echo    1. Download vc_redist.x64.exe into the dist\ folder
    echo       https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo    2. Install Inno Setup: https://jrsoftware.org/isinfo.php
    echo    3. Run: iscc "dist\GlassNote_Setup.iss"
    echo ============================================================
) else (
    echo ============================================================
    echo  BUILD FAILED  (exit code: %BUILD_EXIT%)
    echo  Check the output above for errors.
    echo ============================================================
)

echo.
pause
