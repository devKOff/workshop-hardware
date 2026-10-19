#!/usr/bin/env bash
#
# start.sh — Start the Solar Panel Performance Monitor dashboard.
#
# Usage: ./scripts/start.sh
#
set -euo pipefail

cd "$(dirname "$0")/.."

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

if [ -f .venv/bin/activate ]; then
    # shellcheck disable=SC1091
    . .venv/bin/activate
fi

# Sensor mode defaults to hardware on the Pi; override with SENSOR_MODE=simulation.
export SENSOR_MODE="${SENSOR_MODE:-hardware}"
export DATABASE_PATH="${DATABASE_PATH:-solar_monitor.db}"

if [ -f "$LOG_DIR/solar_monitor.pid" ] && kill -0 "$(cat "$LOG_DIR/solar_monitor.pid")" 2>/dev/null; then
    echo "Already running (PID $(cat "$LOG_DIR/solar_monitor.pid")). Use scripts/stop.sh first."
    exit 0
fi

nohup python run.py > "$LOG_DIR/solar_monitor.log" 2>&1 &
PID=$!
echo "$PID" > "$LOG_DIR/solar_monitor.pid"

echo "Solar Panel Performance Monitor started (PID $PID)."
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):5000/"
echo "Logs:      $LOG_DIR/solar_monitor.log"
