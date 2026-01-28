@echo off
chcp 65001 > nul
echo ====================================
echo   SSMaker Backend - Cloud Run 배포
echo ====================================
echo.

REM 1. gcloud 로그인
echo [1/3] Google Cloud 로그인...
call gcloud auth login
if errorlevel 1 (
    echo 로그인 실패!
    pause
    exit /b 1
)

REM 2. 프로젝트 설정
echo.
echo [2/3] 프로젝트 설정...
call gcloud config set project project-d0118f2c-58f4-4081-864

REM 3. Cloud Run 배포
echo.
echo [3/3] Cloud Run 배포 중... (약 2-5분 소요)
echo.
cd /d "%~dp0"
call gcloud run deploy ssmaker-auth-api --source . --region us-central1 --platform managed --allow-unauthenticated --add-cloudsql-instances project-d0118f2c-58f4-4081-864:us-central1:ssmaker-auth --set-env-vars "DB_USER=ssmaker_user,DB_NAME=ssmaker_auth,CLOUD_SQL_CONNECTION_NAME=project-d0118f2c-58f4-4081-864:us-central1:ssmaker-auth,ENVIRONMENT=production,ALLOWED_ORIGINS=*" --set-secrets "DB_PASSWORD=ssmaker-db-password:latest,JWT_SECRET_KEY=ssmaker-jwt-secret:latest"

echo.
echo ====================================
echo   배포 완료!
echo ====================================
echo.
echo 위에 표시된 Service URL을 복사해서 Claude에게 알려주세요.
echo.
pause
