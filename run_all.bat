@echo off
REM -----------------------------------------------
REM SFEM Educational Platform — Launch all modules
REM -----------------------------------------------

echo Starting SFEM Educational Platform...
echo.

REM Start hub
echo [Hub]         Starting on port 8500...
start /B streamlit run hub/app.py --server.port 8500 --server.headless true

REM Start FEM app
echo [FEM Analysis] Starting on port 8501...
start /B streamlit run fem_app/app.py --server.port 8501 --server.headless true

REM Start FastAPI for FEM
echo [FEM API]      Starting on port 8502...
start /B uvicorn fem_app.api:app --port 8502

REM Start Section app
echo [Section Props] Starting on port 8503...
start /B streamlit run section_app/app.py --server.port 8503 --server.headless true

REM Start Buckling app
echo [Buckling]      Starting on port 8504...
start /B streamlit run buckling_app/app.py --server.port 8504 --server.headless true

echo.
echo All modules starting... waiting 3 seconds for servers to initialize.
timeout /t 3 /nobreak > nul

REM Open hub in Chrome app mode
echo Opening hub in browser...
start chrome --app=http://localhost:8500 --new-window

echo.
echo Platform is running. Close this window to stop all modules.
echo   Hub:              http://localhost:8500
echo   FEM Analysis:     http://localhost:8501
echo   FEM API:          http://localhost:8502
echo   Section Props:    http://localhost:8503
echo   Buckling Check:   http://localhost:8504
echo.
pause
