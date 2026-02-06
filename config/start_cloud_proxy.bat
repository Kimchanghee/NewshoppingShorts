@echo off
echo Starting Cloud SQL Proxy...
echo Connection: project-d0118f2c-58f4-4081-864:us-central1:ssmaker-auth
echo Port: 3306
echo.
.\cloud-sql-proxy.exe project-d0118f2c-58f4-4081-864:us-central1:ssmaker-auth
pause
