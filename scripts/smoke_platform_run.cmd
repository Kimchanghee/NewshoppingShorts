@echo off
rem 3플랫폼 소싱 스모크 — Job 독립 실행 래퍼(자동화/테스트용)
chcp 65001 >nul
set PYTHONUTF8=1
cd /d D:\Dithub\NewshoppingShorts-1
set URL=%~1
if "%URL%"=="" set URL=https://www.coupang.com/vp/products/9555806781
"C:\Users\HOME\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 scripts\smoke_platform_sourcing.py "%URL%" > "%TEMP%\smoke_run_out.log" 2>&1
echo EXITCODE=%ERRORLEVEL% >> "%TEMP%\smoke_run_out.log"
