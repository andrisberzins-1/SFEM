#!/bin/bash
# -----------------------------------------------
# run.sh — Launch both Streamlit and FastAPI servers
#
# Usage: bash run.sh
#   Streamlit: http://localhost:8501
#   FastAPI:   http://localhost:8502
#   API docs:  http://localhost:8502/docs
# -----------------------------------------------

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Auto-detect Python command
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo "ERROR: Python not found. Install Python 3 first."
    exit 1
fi

echo "=========================================="
echo "  2D FEM Web Application"
echo "=========================================="
echo ""
echo "  Starting servers..."
echo "    Streamlit UI:  http://localhost:8501"
echo "    FastAPI:       http://localhost:8502"
echo "    API docs:      http://localhost:8502/docs"
echo ""

# Start FastAPI in the background
$PY -m uvicorn api:app --host 0.0.0.0 --port 8502 &
API_PID=$!
echo "  FastAPI started (PID: $API_PID)"

# Start Streamlit in the foreground
$PY -m streamlit run app.py --server.port 8501 --server.headless true &
STREAMLIT_PID=$!
echo "  Streamlit started (PID: $STREAMLIT_PID)"

echo ""
echo "  Press Ctrl+C to stop both servers."
echo "=========================================="

# Trap Ctrl+C to kill both processes
cleanup() {
    echo ""
    echo "  Stopping servers..."
    kill $API_PID 2>/dev/null
    kill $STREAMLIT_PID 2>/dev/null
    echo "  Done."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Wait for both background processes
wait
