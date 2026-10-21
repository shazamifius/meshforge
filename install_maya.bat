@echo off
setlocal enabledelayedexpansion
title MeshForge for Maya - Automated Installer

echo ======================================================================
echo              MeshForge for Maya - Automated Installer
echo ======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
:: Remove trailing backslash if present
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "PKG_DIR=%SCRIPT_DIR%\meshforge_maya"
if not exist "%PKG_DIR%" (
    echo [ERROR] Could not find folder meshforge_maya in:
    echo %SCRIPT_DIR%
    echo Please make sure you run install_maya.bat from the MeshForge folder.
    pause
    exit /b 1
)

set "MAYA_DOCS=%USERPROFILE%\Documents\maya"
set "MODULES_DIR=%MAYA_DOCS%\modules"
set "SCRIPTS_DIR=%MAYA_DOCS%\scripts"

echo [*] Registering MeshForge Maya Module...
if not exist "%MODULES_DIR%" mkdir "%MODULES_DIR%"
if not exist "%SCRIPTS_DIR%" mkdir "%SCRIPTS_DIR%"

set "MOD_FILE=%MODULES_DIR%\meshforge_maya.mod"
(
    echo + meshforge_maya 0.2.0 %PKG_DIR%
    echo PYTHONPATH +:= ..
) > "%MOD_FILE%"

echo [OK] Created module descriptor: "%MOD_FILE%"

echo [*] Registering startup integration...
set "USERSETUP=%SCRIPTS_DIR%\userSetup.py"

:: Check if already registered in userSetup.py
findstr /C:"MeshForge Maya Startup Integration" "%USERSETUP%" >nul 2>&1
if errorlevel 1 (
    (
        echo.
        echo # --- MeshForge Maya Startup Integration ---
        echo import sys
        echo mf_path = r'%SCRIPT_DIR%'
        echo if mf_path not in sys.path:
        echo     sys.path.insert^(0, mf_path^)
    ) >> "%USERSETUP%"
    echo [OK] Registered in "%USERSETUP%"
) else (
    echo [OK] Startup integration was already active in userSetup.py
)

echo.
echo ======================================================================
echo   SUCCESS: MeshForge for Maya has been successfully installed!
echo ======================================================================
echo.
echo You can now:
echo   1. Launch Maya (2020, 2022, 2023, 2024, 2025, 2026, 2027+)
echo   2. Run this command in Maya's Python Script Editor:
echo          import meshforge_maya; meshforge_maya.show()
echo      Or drag "install.mel" into Maya's 3D viewport to get a Shelf button!
echo.
pause
