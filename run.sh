#!/usr/bin/env bash
# Sales Anomaly Studio — macOS / Linux launcher.
# (The bundled Windows runtime is not used here; this creates a small private environment.)
set -e
cd "$(dirname "$0")"
PY=python3; command -v $PY >/dev/null 2>&1 || PY=python
echo ""
echo "  ==========================================="
echo "   SALES ANOMALY STUDIO"
echo "  ==========================================="
echo ""
if [ ! -x ".venv/bin/python" ]; then
  echo "[1/3] Creating a private environment (first run only)..."
  $PY -m venv .venv || { echo "Python 3.10+ is required (https://www.python.org/downloads/)"; exit 1; }
fi
echo "[2/3] Checking packages..."
if ! .venv/bin/python -c "import streamlit,plotly,pandas,numpy,pyarrow,sklearn" >/dev/null 2>&1; then
  echo "      Installing (one time, needs internet)..."
  .venv/bin/python -m pip install --upgrade pip -q
  .venv/bin/python -m pip install -r requirements.txt
fi
echo "[3/3] Starting the app at http://localhost:8501  (Ctrl+C to stop)"
( sleep 4; (command -v open >/dev/null && open http://localhost:8501) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8501) || true ) &
exec .venv/bin/python -m streamlit run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
