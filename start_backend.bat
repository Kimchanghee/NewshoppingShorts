@echo off
echo Starting Backend Server...
cd backend
..\githubNewshoppingShortsMakervenv312\Scripts\uvicorn.exe app.main:app --reload --port 8000
pause
