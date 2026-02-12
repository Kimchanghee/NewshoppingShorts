@echo off
chcp 65001 > nul
echo ============================================
echo   관리자 대시보드 빌드 (admin_dashboard.exe)
echo ============================================
echo.

REM 프로젝트 루트로 이동
cd /d "%~dp0"

REM 기존 빌드 결과 정리
echo [1/3] 이전 빌드 정리 중...
if exist "dist\admin_dashboard.exe" del "dist\admin_dashboard.exe"

REM PyInstaller 빌드
echo [2/3] PyInstaller 빌드 시작...
python -m PyInstaller admin_dashboard.spec --noconfirm

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 빌드 실패! 오류를 확인하세요.
    pause
    exit /b 1
)

REM 결과 확인
echo.
echo [3/3] 빌드 완료!
if exist "dist\admin_dashboard.exe" (
    echo ✅ 생성된 파일: dist\admin_dashboard.exe
    for %%A in ("dist\admin_dashboard.exe") do echo    파일 크기: %%~zA bytes
    echo.
    echo 이 파일을 다른 PC에 복사하여 실행할 수 있습니다.
    echo 주의: .env 파일이 함께 번들됩니다 (SSMAKER_ADMIN_KEY 포함)
) else (
    echo ❌ admin_dashboard.exe가 생성되지 않았습니다.
)

echo.
pause
