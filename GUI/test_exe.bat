@echo off
echo ============================================================
echo  Testing GlassNote Executable
echo ============================================================
echo.

if not exist "dist\svchost_audio.exe" (
    echo [ERROR] dist\svchost_audio.exe not found!
    echo Run package.bat first to build the executable.
    pause
    exit /b 1
)

echo Executable found: dist\svchost_audio.exe
for %%I in (dist\svchost_audio.exe) do echo Size: %%~zI bytes (%%~zI / 1048576 = ~%%I MB)
echo.
echo Starting GlassNote...
echo.
echo NOTE: The application will open in the system tray.
echo       Look for the tray icon in the bottom-right of your screen.
echo.
pause

start "" "dist\svchost_audio.exe"

echo.
echo Application started!
echo If you don't see it, check your system tray.
echo.
pause
