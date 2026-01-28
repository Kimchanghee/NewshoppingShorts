@echo off
chcp 65001 >nul
echo ============================================================
echo   SSMaker Admin Dashboard Build Script
echo ============================================================
echo.

REM Check if venv312 exists
if not exist "venv312\Scripts\python.exe" (
    echo [ERROR] venv312 not found!
    echo Please create virtual environment first:
    echo   py -3.12 -m venv venv312
    echo   venv312\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Use venv312 Python and pip
set VENV_PYTHON=venv312\Scripts\python.exe
set VENV_PIP=venv312\Scripts\pip.exe
set VENV_PYINSTALLER=venv312\Scripts\pyinstaller.exe

echo [INFO] Using Python: %VENV_PYTHON%
for /f "tokens=*" %%i in ('%VENV_PYTHON% --version') do echo      %%i
echo.

REM Step 1: Clean old admin build
echo [1/3] Cleaning previous admin build...
if exist "dist\SSMaker_Admin" rmdir /s /q dist\SSMaker_Admin
if exist "build\SSMaker_Admin" rmdir /s /q build\SSMaker_Admin
echo      Done.
echo.

REM Step 2: Ensure PyQt5 and requests are installed
echo [2/3] Checking dependencies...
%VENV_PIP% show PyQt5 >nul 2>&1
if errorlevel 1 (
    echo      Installing PyQt5...
    %VENV_PIP% install PyQt5
)
%VENV_PIP% show requests >nul 2>&1
if errorlevel 1 (
    echo      Installing requests...
    %VENV_PIP% install requests
)
echo      Done.
echo.

REM Step 3: Build with PyInstaller
echo [3/3] Building Admin Dashboard...
%VENV_PYINSTALLER% --clean -y admin.spec
if errorlevel 1 (
    echo      ERROR: Build failed
    pause
    exit /b 1
)
echo.

echo ============================================================
echo   Build Complete!
echo   Output: dist\SSMaker_Admin\SSMaker_Admin.exe
echo ============================================================
pause
