@echo off
chcp 65001 >nul
echo ============================================================
echo   SSMaker Build Script (venv312)
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

REM Step 1: Clean old build
echo [1/6] Cleaning previous build...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
echo      Done.
echo.

REM Step 2: Install/Update dependencies
echo [2/6] Installing dependencies...
%VENV_PIP% install -r requirements.txt --quiet
if errorlevel 1 (
    echo      ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo      Done.
echo.

REM Step 3: Verify google-genai is installed
echo [3/6] Verifying google-genai SDK...
%VENV_PIP% show google-genai >nul 2>&1
if errorlevel 1 (
    echo      google-genai not found, installing...
    %VENV_PIP% install google-genai>=1.0.0
)
for /f "tokens=2" %%i in ('%VENV_PIP% show google-genai ^| findstr "Version"') do echo      google-genai version: %%i
echo.

REM Step 4: Verify faster-whisper is installed (Skip on Python 3.13+)
set SKIP_WHISPER=0
%VENV_PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)"
if not errorlevel 1 (
    echo [4/6] Python 3.13+ detected, skipping faster-whisper...
    set SKIP_WHISPER=1
) else (
    echo [4/6] Verifying faster-whisper...
    %VENV_PIP% show faster-whisper >nul 2>&1
    if errorlevel 1 (
        echo      faster-whisper not found, installing...
        %VENV_PIP% install faster-whisper>=1.0.0
        if errorlevel 1 (
            echo      ERROR: Failed to install faster-whisper
            pause
            exit /b 1
        )
    )
    for /f "tokens=2" %%i in ('%VENV_PIP% show faster-whisper ^| findstr "Version"') do echo      faster-whisper version: %%i
)
echo.

REM Step 5: Download Whisper models and Fonts
echo [5/6] Downloading Faster-Whisper models and Fonts...
%VENV_PYTHON% download_whisper_models.py
if errorlevel 1 (
    echo      WARNING: Whisper model download failed (will download on first run)
)
%VENV_PYTHON% download_all_fonts.py
if errorlevel 1 (
    echo      WARNING: Font download failed
)
echo.

REM Step 6: Build with PyInstaller
echo [6/6] Building with PyInstaller...
echo      This may take 10-20 minutes...
echo.
%VENV_PYINSTALLER% --clean -y ssmaker.spec
if errorlevel 1 (
    echo      ERROR: Build failed
    pause
    exit /b 1
)
echo.

REM Validate build
echo ============================================================
echo   Validating build...
echo ============================================================
%VENV_PYTHON% validate_build.py
echo.

echo ============================================================
echo   Build Complete!
echo   Output: dist\ssmaker\ssmaker.exe
echo ============================================================
pause
