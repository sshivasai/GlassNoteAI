@echo off
echo Testing sounddevice in build venv...
echo.

if not exist ".venv-build\Scripts\python.exe" (
    echo [ERROR] .venv-build not found. Run package.bat first.
    pause
    exit /b 1
)

echo [TEST 1] Activating venv...
call .venv-build\Scripts\activate.bat

echo [TEST 2] Checking Python...
where python
python --version
echo.

echo [TEST 3] Checking if sounddevice is installed...
pip show sounddevice
echo.

echo [TEST 4] Testing import with full output...
python -c "import sounddevice; print('SUCCESS: sounddevice imported'); print('Version:', sounddevice.__version__)"
set TEST_EXIT=%errorlevel%
echo Exit code: %TEST_EXIT%
echo.

if %TEST_EXIT% equ 0 (
    echo [PASS] sounddevice works!
) else (
    echo [FAIL] sounddevice import failed
)

call deactivate
pause
