@echo off
title 2D FEM Web Application
cd /d "%~dp0"

echo ==========================================
echo   2D FEM Web Application
echo ==========================================
echo.
echo   Starting servers...
echo     Streamlit UI:  http://localhost:8501
echo     FastAPI:       http://localhost:8502
echo.

start "FastAPI" python -m uvicorn api:app --host 0.0.0.0 --port 8502
start "Streamlit" python -m streamlit run app.py --server.port 8501 --server.headless true

echo   Both servers started.
echo   Close this window or press Ctrl+C to stop.
echo ==========================================
pause
