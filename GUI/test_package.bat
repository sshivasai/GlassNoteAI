@echo off
echo Testing package.bat steps...
echo.

cd /d "%~dp0"

echo Step 1: Creating venv...
python -m venv .venv-test
if errorlevel 1 (
    echo [ERROR] Failed to create venv
    pause
    exit /b 1
)
echo  OK

echo Step 2: Activating venv...
call .venv-test\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate
    pause
    exit /b 1
)
echo  OK

echo Step 3: Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1
echo  OK

echo Step 4: Installing sounddevice...
pip install "sounddevice==0.4.6" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Failed to install sounddevice
    call deactivate
    pause
    exit /b 1
)
echo  OK

echo Step 5: Testing sounddevice import...
python -c "import sounddevice; print('Import successful')"
if errorlevel 1 (
    echo [ERROR] Import failed
    call deactivate
    pause
    exit /b 1
)
echo  OK

echo Step 6: Installing requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Requirements install failed
    call deactivate
    pause
    exit /b 1
)
echo  OK

echo Step 7: Running build.py...
python build.py
set BUILD_EXIT=%errorlevel%

call deactivate

if %BUILD_EXIT% equ 0 (
    echo.
    echo BUILD SUCCESSFUL!
) else (
    echo.
    echo BUILD FAILED (exit code: %BUILD_EXIT%)
)

echo.
echo Cleaning up test venv...
rmdir /s /q .venv-test

pause
