#!/bin/bash
set -e

echo "Ensuring data directory exists..."
mkdir -p $DATA_DIR

echo "Starting PTT Analyzer (Fetching fresh data)..."
python ptt_analyzer.py

echo "Analyzer complete. Launching Web Dashboard..."
exec python web_dashboard.py