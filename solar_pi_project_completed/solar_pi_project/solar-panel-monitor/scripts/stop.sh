#!/usr/bin/env bash
#
# stop.sh — Stop the Solar Panel Performance Monitor dashboard.
#
set -euo pipefail

cd "$(dirname "$0")/.."

PID_FILE="logs/solar_monitor.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No PID file found. Is the app running?"
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    # Wait briefly for graceful shutdown.
    for i in $(seq 1 10); do
        if ! kill -0 "$PID" 2>/dev/null; then
            break
        fi
        sleep 0.5
    done
    if kill -0 "$PID" 2>/dev/null; then
        echo "Process did not exit; forcing kill."
        kill -9 "$PID" 2>/dev/null || true
    fi
    echo "Stopped (PID $PID)."
else
    echo "Process $PID not running."
fi

rm -f "$PID_FILE"
