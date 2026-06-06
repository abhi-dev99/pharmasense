@echo off
echo ==============================================
echo Starting Pharmasense Enterprise Dashboard...
echo ==============================================

echo [1/2] Starting Python FastAPI Backend...
start "Pharmasense Backend" cmd /k "cd /d %~dp0 && set PYTHONUTF8=1 && uvicorn backend.main:app --reload --port 8000"

echo [2/2] Starting Next.js Frontend...
start "Pharmasense Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Both servers have been launched in separate terminal windows.
echo The backend is running on http://localhost:8000
echo The frontend is running on http://localhost:3000
echo.
pause
