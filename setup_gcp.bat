@echo off
chcp 65001 > nul
echo ========================================================
echo   Google Cloud Platform (Vertex AI) 연결 마법사
echo ========================================================
echo.
echo [1/3] Google 계정 로그인 진행 중...
echo 브라우저 창이 열리면 사용하는 구글 계정(contact@pineoptimizerpro.com)으로 로그인해주세요.
call gcloud auth login
if %ERRORLEVEL% NEQ 0 (
    echo 로그인 실패 또는 취소되었습니다.
    pause
    exit /b
)
echo.

echo [2/3] 애플리케이션 인증 정보(ADC) 설정 중...
echo 브라우저 창이 다시 열리면 '허용'을 클릭해주세요.
call gcloud auth application-default login
if %ERRORLEVEL% NEQ 0 (
    echo ADC 설정 실패.
    pause
    exit /b
)
echo.

echo [3/3] 프로젝트 선택...
echo 현재 계정의 프로젝트 목록을 불러옵니다:
echo --------------------------------------------------------
call gcloud projects list
echo --------------------------------------------------------
echo 위 목록에서 사용할 Project ID를 확인해주세요.
echo (예: pine-optimizer-pro-12345)
echo.
set /p PROJECT_ID="위 목록에서 사용할 Project ID를 입력하세요: "

if "%PROJECT_ID%"=="" (
    echo 프로젝트 ID가 입력되지 않았습니다.
    pause
    exit /b
)

echo.
echo 프로젝트를 %PROJECT_ID%로 설정합니다...
call gcloud config set project %PROJECT_ID%
call gcloud auth application-default set-quota-project %PROJECT_ID%

echo.
echo 설정을 환경 변수 파일(.env)에 저장합니다...
echo VERTEX_PROJECT_ID=%PROJECT_ID% > .env
echo VERTEX_LOCATION=us-central1 >> .env

echo.
echo ========================================================
echo   설정 완료! 이제 Vertex AI가 연결되었습니다.
echo   프로그램을 다시 실행하면 적용됩니다.
echo ========================================================
pause
