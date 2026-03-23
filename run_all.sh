#!/bin/bash
# -----------------------------------------------
# SFEM Educational Platform — Launch all modules
# -----------------------------------------------

echo "Starting SFEM Educational Platform..."
echo ""

# Start hub
echo "[Hub]          Starting on port 8500..."
streamlit run hub/app.py --server.port 8500 --server.headless true &

# Start FEM app
echo "[FEM Analysis]  Starting on port 8501..."
streamlit run fem_app/app.py --server.port 8501 --server.headless true &

# Start FastAPI for FEM
echo "[FEM API]       Starting on port 8502..."
uvicorn fem_app.api:app --port 8502 &

# Start Section app
echo "[Section Props] Starting on port 8503..."
streamlit run section_app/app.py --server.port 8503 --server.headless true &

# Start Buckling app
echo "[Buckling]      Starting on port 8504..."
streamlit run buckling_app/app.py --server.port 8504 --server.headless true &

echo ""
echo "All modules starting..."
sleep 3

# Open hub in Chrome app mode (optional)
if command -v google-chrome &> /dev/null; then
    google-chrome --app=http://localhost:8500 --new-window &
elif command -v chromium-browser &> /dev/null; then
    chromium-browser --app=http://localhost:8500 --new-window &
else
    echo "Open http://localhost:8500 in your browser."
fi

echo ""
echo "Platform is running. Press Ctrl+C to stop all modules."
echo "  Hub:              http://localhost:8500"
echo "  FEM Analysis:     http://localhost:8501"
echo "  FEM API:          http://localhost:8502"
echo "  Section Props:    http://localhost:8503"
echo "  Buckling Check:   http://localhost:8504"
echo ""

# Wait for all background processes
wait
