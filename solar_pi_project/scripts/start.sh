#!/usr/bin/env bash
# start.sh — activate the venv and run the Flask dashboard.
set -euo pipefail

if [ ! -d .venv ]; then
    echo "Virtual environment not found. Run scripts/install.sh first."
    exit 1
fi

source .venv/bin/activate

echo "Starting Solar Panel Performance Monitor dashboard..."
echo "Open http://<raspberry-pi-ip-address>:5000 on your phone or computer."
echo "Press Ctrl+C to stop."

python src/app.py
