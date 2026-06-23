@echo off
setlocal

cd /d "%~dp0.."

set "LOG_DIR=%USERPROFILE%\.ssmaker\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "LOG_FILE=%LOG_DIR%\summer_coupang_queue_once.log"
set "PYTHONIOENCODING=utf-8"
echo.>> "%LOG_FILE%"
echo ===== %DATE% %TIME% summer_coupang_queue_once start =====>> "%LOG_FILE%"

"C:\Users\HOME\AppData\Local\Programs\Python\Python313\python.exe" "scripts\run_summer_coupang_queue_once.py" %* >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo ===== %DATE% %TIME% summer_coupang_queue_once exit %EXIT_CODE% =====>> "%LOG_FILE%"
exit /b %EXIT_CODE%
