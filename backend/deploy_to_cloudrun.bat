@echo off
chcp 65001 > nul
setlocal EnableExtensions

echo ====================================
echo   SSMaker Backend - Cloud Run Deploy
echo ====================================
echo.

if "%PROJECT_ID%"=="" set "PROJECT_ID=project-d0118f2c-58f4-4081-864"
if "%REGION%"=="" set "REGION=us-central1"
if "%SERVICE_NAME%"=="" set "SERVICE_NAME=ssmaker-auth-api"
if "%CLOUDSQL_CONN%"=="" set "CLOUDSQL_CONN=project-d0118f2c-58f4-4081-864:us-central1:ssmaker-auth"

REM Must be explicitly set by deployment operator.
if "%ALLOWED_ORIGINS%"=="" (
  echo ERROR: ALLOWED_ORIGINS is required. Example: https://app.example.com
  exit /b 1
)

if "%PAYMENT_API_BASE_URL%"=="" (
  echo ERROR: PAYMENT_API_BASE_URL is required. Example: https://ssmaker-auth-api-XXXX.us-central1.run.app
  exit /b 1
)

REM Secret names can be overridden per environment.
if "%DB_PASSWORD_SECRET%"=="" set "DB_PASSWORD_SECRET=ssmaker-db-password"
if "%JWT_SECRET_KEY_SECRET%"=="" set "JWT_SECRET_KEY_SECRET=ssmaker-jwt-secret"
if "%ADMIN_API_KEY_SECRET%"=="" set "ADMIN_API_KEY_SECRET=ssmaker-admin-api-key"
if "%BILLING_KEY_ENCRYPTION_KEY_SECRET%"=="" set "BILLING_KEY_ENCRYPTION_KEY_SECRET=ssmaker-billing-key-encryption-key"
if "%PAYAPP_USERID_SECRET%"=="" set "PAYAPP_USERID_SECRET=ssmaker-payapp-userid"
if "%PAYAPP_LINKKEY_SECRET%"=="" set "PAYAPP_LINKKEY_SECRET=ssmaker-payapp-linkkey"
if "%PAYAPP_LINKVAL_SECRET%"=="" set "PAYAPP_LINKVAL_SECRET=ssmaker-payapp-linkval"

echo [0/3] Using Secret Manager for sensitive values
echo.

echo [1/3] Set gcloud project
call gcloud config set project %PROJECT_ID%
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: failed to set project.
  exit /b 1
)

echo.
echo [2/3] Deploying Cloud Run service...
cd /d "%~dp0"
call gcloud run deploy %SERVICE_NAME% --source . --region %REGION% --platform managed --allow-unauthenticated --add-cloudsql-instances %CLOUDSQL_CONN% --set-env-vars "DB_USER=ssmaker_user,DB_NAME=ssmaker_auth,CLOUD_SQL_CONNECTION_NAME=%CLOUDSQL_CONN%,ENVIRONMENT=production,ALLOWED_ORIGINS=%ALLOWED_ORIGINS%,PAYMENT_API_BASE_URL=%PAYMENT_API_BASE_URL%" --set-secrets "DB_PASSWORD=%DB_PASSWORD_SECRET%:latest,JWT_SECRET_KEY=%JWT_SECRET_KEY_SECRET%:latest,ADMIN_API_KEY=%ADMIN_API_KEY_SECRET%:latest,BILLING_KEY_ENCRYPTION_KEY=%BILLING_KEY_ENCRYPTION_KEY_SECRET%:latest,PAYAPP_USERID=%PAYAPP_USERID_SECRET%:latest,PAYAPP_LINKKEY=%PAYAPP_LINKKEY_SECRET%:latest,PAYAPP_LINKVAL=%PAYAPP_LINKVAL_SECRET%:latest" --quiet
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Cloud Run deploy failed.
  exit /b 1
)

echo.
echo [3/3] Service URL
gcloud run services describe %SERVICE_NAME% --region %REGION% --format="value(status.url)"

echo.
echo Deployment complete.
exit /b 0
