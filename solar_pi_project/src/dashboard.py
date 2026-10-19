#!/usr/bin/env python3
"""
Solar Panel Performance Monitor - Web Dashboard

A Flask-based web dashboard for the Solar Panel Performance Monitor project.
Compatible with the existing Jinja templates (base.html, index.html, history.html).

Provides real-time solar panel measurements from the INA219 sensor,
historical graphs, and CSV export functionality.
"""

import json
import os
import sqlite3
from datetime import datetime, date
from threading import Thread
from collections import deque
from typing import List, Dict, Any, Optional

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    g,
)

# Project-local imports
from sensor_reader import IN219Sensor, ReadingDatabase, SAMPLING_INTERVAL

# ---------------------------------------------------------------------------
# Flask Application Setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # Disable caching for dynamic data

# Global instances
sensor: Optional[IN219Sensor] = None
database: Optional[ReadingDatabase] = None

# In-memory history shared with the monitoring loop
# Each entry: (timestamp, voltage_V, current_mA, power_W, accumulated_Wh, daily_Wh)
history: deque = deque(maxlen=1000)

# Lock for thread-safe access to shared resources
history_lock = __import__("threading").Lock()

# ---------------------------------------------------------------------------
# Flask Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Main dashboard page - renders the Jinja template."""
    return render_template("index.html")


@app.route("/history")
def history_page():
    """History & CSV page."""
    return render_template("history.html")


@app.route("/api/current")
def api_current():
    """
    API endpoint expected by the Jinja templates.
    Returns: { bus_voltage_v, current_ma, power_mw, daily_wh, energy_wh, ok, timestamp }
    """
    global sensor, database

    if sensor is None:
        return jsonify({
            "bus_voltage_v": None,
            "current_ma": None,
            "power_mw": None,
            "daily_wh": 0,
            "energy_wh": 0,
            "ok": False,
            "timestamp": datetime.now().isoformat(),
        })

    try:
        reading = sensor.safe_read_all()

        # Get energy totals from sensor
        accumulated, daily = sensor.get_accumulated_and_daily() if hasattr(sensor, 'get_accumulated_and_daily') else (0, 0)

        # Convert power from W to mW
        power_mw = reading["power_W"] * 1000 if reading["power_W"] is not None else None
        voltage = reading["voltage_V"]
        current_ma = reading["current_mA"]

        result = {
            "bus_voltage_v": voltage,
            "current_ma": current_ma,
            "power_mw": power_mw,
            "daily_wh": daily,
            "energy_wh": accumulated,
            "ok": reading["status"] == "ok",
            "timestamp": datetime.now().isoformat(),
        }
        return jsonify(result)

    except Exception as e:
        print(f"Error in /api/current: {e}")
        return jsonify({
            "bus_voltage_v": None,
            "current_ma": None,
            "power_mw": None,
            "daily_wh": 0,
            "energy_wh": 0,
            "ok": False,
            "timestamp": datetime.now().isoformat(),
        })


@app.route("/api/history")
def api_history():
    """
    API endpoint expected by the Jinja history template.
    Query params: minutes (default 60)
    Returns: { timestamps[], bus_voltage_v[], current_ma[], power_mw[], energy_wh[] }
    """
    global history, database

    minutes = request.args.get("minutes", 60, type=int)

    # Get from in-memory history
    with history_lock:
        # Get readings from the last N minutes
        cutoff_time = time.time() - (minutes * 60)
        recent = [entry for entry in history if entry[0] >= cutoff_time]

    if not recent:
        return jsonify({
            "timestamps": [],
            "bus_voltage_v": [],
            "current_ma": [],
            "power_mw": [],
            "energy_wh": [],
        })

    # Format timestamps as ISO strings and convert values
    # power_mw is in milliwatts (W * 1000)
    timestamps = []
    voltages = []
    currents = []
    powers_mw = []
    energies = []

    for entry in recent:
        ts, voltage, current, power, accumulated, daily = entry
        if ts is not None:
            dt = datetime.fromtimestamp(ts)
            timestamps.append(dt.isoformat())
            voltages.append(voltage if voltage is not None else None)
            currents.append(current if current is not None else None)
            powers_mw.append((power if power is not None else 0) * 1000)  # mW
            energies.append(accumulated if accumulated is not None else 0)

    return jsonify({
        "timestamps": timestamps,
        "bus_voltage_v": voltages,
        "current_ma": currents,
        "power_mw": powers_mw,
        "energy_wh": energies,
    })


@app.route("/export.csv")
def export_csv():
    """
    CSV export endpoint expected by history.html.
    Query params: start, end (datetime-local format optional)
    """
    global database

    if database is None:
        return "Database not available", 503

    start_str = request.args.get("start")
    end_str = request.args.get("end")

    try:
        if start_str and end_str:
            # Parse datetime-local strings
            # datetime-local format: YYYY-MM-DDTHH:MM
            start_date = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
            end_date = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
            readings = database.get_readings_range(
                start_date.date(), end_date.date()
            )
        else:
            # Export today's readings or all
            all_readings = database.get_all_readings()
            readings = all_readings

        import csv
        output = []
        output.append("ID,Timestamp,Date,Time,Voltage_V,Current_mA,Power_W,Shunt_mV,Accumulated_Wh,Daily_Wh")
        for row in readings:
            output.append(
                f"{row['id']},{row['timestamp']},{row['date']},{row['time_text']},"
                f"{row['voltage_V'] or ''},{row['current_mA'] or ''},{row['power_W'] or ''},"
                f"{row['shunt_mV'] or ''},{row['accumulated_Wh'] or ''},{row['daily_Wh'] or ''}"
            )

        csv_content = "\n".join(output)
        return csv_content, 200, {"Content-Type": "text/csv"}

    except Exception as e:
        print(f"Error exporting CSV: {e}")
        return f"Error: {e}", 500


# ---------------------------------------------------------------------------
# Monitoring & Helpers
# ---------------------------------------------------------------------------


def init_project():
    """Initialize the sensor and database (call once at startup)."""
    global sensor, database

    # Initialize sensor
    try:
        sensor = IN219Sensor()
        print("INA219 sensor initialized successfully")
    except RuntimeError as e:
        print(f"Warning: Could not initialize INA219: {e}")
        sensor = None

    # Initialize database
    try:
        db_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "solar_readings.db"
        )
        database = ReadingDatabase(db_path=db_path)
        print(f"Database initialized at: {db_path}")
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
        database = None


def get_sensor() -> Optional[IN219Sensor]:
    """Return the global sensor instance."""
    return sensor


def get_database() -> Optional[ReadingDatabase]:
    """Return the global database instance."""
    return database


def safe_read_sensor() -> Dict[str, Any]:
    """
    Read sensor data safely and return a dict with results.
    """
    if sensor is None:
        return {
            "success": False,
            "error": "Sensor not initialized",
            "voltage_V": None,
            "current_mA": None,
            "power_W": None,
            "shunt_mV": None,
        }

    reading = sensor.safe_read_all()

    result = {
        "status": reading["status"],
        "voltage_V": reading["voltage_V"],
        "current_mA": reading["current_mA"],
        "power_W": reading["power_W"],
        "shunt_mV": reading["shunt_mV"],
        "timestamp": reading["timestamp"],
    }
    return result


def update_history():
    """Add the latest reading to the in-memory history deque."""
    global history

    reading = safe_read_sensor()
    if reading["voltage_V"] is not None or reading["current_mA"] is not None:
        timestamp = time.time()
        entry = (
            timestamp,
            reading.get("voltage_V"),
            reading.get("current_mA"),
            reading.get("power_W"),
        )
        with history_lock:
            history.append(entry)


def get_history_last_n(n: int = 50) -> List[Tuple]:
    """Get the last N entries from the history deque."""
    with history_lock:
        return list(history)[-n:]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Solar Panel Performance Monitor - Dashboard Server")
    print("=" * 60)

    # Initialize project components
    init_project()

    # Start background monitoring thread
    monitor_thread = Thread(target=_monitoring_loop, daemon=True)
    monitor_thread.start()

    print("\nStarting Flask development server...")
    print("  Local access:    http://127.0.0.1:5000")
    print("  Network access:  http://<PI_IP_ADDRESS>:5000")
    print("  History page:    http://<PI_IP_ADDRESS>:5000/history")
    print("  Press Ctrl+C to stop")
    print("=" * 60)

    # Run Flask app
    # - host='0.0.0.0' makes it accessible on the local network
    # - port=5000 is the default Flask port
    # - threaded=True allows background monitoring to run concurrently
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)


def _monitoring_loop():
    """
    Run in a background thread to periodically read the sensor and update history.
    This keeps the Flask API responsive.
    """
    global sensor, history

    if sensor is None:
        print("Could not start monitoring loop: INA219 not available")
        return

    print("Starting background monitoring loop")

    try:
        import time
        while True:
            # Read and update history
            update_history()

            # Sleep for half the sampling interval
            time.sleep(SAMPLING_INTERVAL / 2)
    except KeyboardInterrupt:
        print("Monitoring loop stopped")