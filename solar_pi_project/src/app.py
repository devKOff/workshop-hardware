"""Flask web dashboard for the Solar Panel Performance Monitor.

Architecture:
- A background thread samples the INA219 every SAMPLE_INTERVAL_SEC seconds,
  integrates energy, and writes every sample (valid or failed) to SQLite.
- Flask routes read from SQLite, so the dashboard is always consistent with
  the log and survives sensor disconnections / app restarts gracefully.
- Current readings are also kept in a small in-memory dict for fast API
  responses, but the authoritative source is the database.

Run:
    python src/app.py
Then open http://<raspberry-pi-ip>:5000 from a phone or computer on the LAN.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from flask import Flask, jsonify, render_template, request, Response

from .config import (
    DB_PATH,
    SAMPLE_INTERVAL_SEC,
    FLASK_HOST,
    FLASK_PORT,
)
from .database import Database
from .ina219_reader import SolarSensor, Reading
from .energy_tracker import EnergyTracker

app = Flask(__name__)

db = Database(DB_PATH)
sensor = SolarSensor()
tracker = EnergyTracker(db)

_stop = threading.Event()
_sampler_thread: Optional[threading.Thread] = None

# Fast in-memory snapshot of the most recent sample (authoritative copy is in DB).
latest: dict = {
    "ok": False,
    "error": "sampling not started",
    "timestamp": None,
    "bus_voltage_v": None,
    "current_ma": None,
    "power_mw": None,
    "energy_wh": None,
    "daily_wh": None,
}


def _sample_loop() -> None:
    """Background thread: read sensor, integrate energy, persist to SQLite."""
    sensor.initialize()
    while not _stop.is_set():
        r: Reading = sensor.read()

        if r.ok and r.power_mw is not None:
            power_w = r.power_mw / 1000.0
            cumulative, daily, _ = tracker.add(power_w, r.timestamp)
            db.insert_reading(r, cumulative)
            latest.update(
                {
                    "ok": True,
                    "error": None,
                    "timestamp": r.timestamp,
                    "bus_voltage_v": r.bus_voltage_v,
                    "current_ma": r.current_ma,
                    "power_mw": r.power_mw,
                    "energy_wh": cumulative,
                    "daily_wh": daily,
                }
            )
        else:
            # Record the failure so gaps are visible; energy keeps its last value.
            db.insert_reading(r, tracker.cumulative())
            latest.update(
                {
                    "ok": False,
                    "error": r.error or "read failed",
                    "timestamp": r.timestamp,
                    "bus_voltage_v": r.bus_voltage_v,
                    "current_ma": r.current_ma,
                    "power_mw": r.power_mw,
                    "energy_wh": tracker.cumulative(),
                    "daily_wh": tracker.daily(),
                }
            )

        _stop.wait(SAMPLE_INTERVAL_SEC)


# ------------------------------------------------------------------ routes

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/history")
def history_page():
    return render_template("history.html")


@app.route("/api/current")
def api_current():
    """Most recent sample (valid or failed)."""
    return jsonify(latest)


@app.route("/api/history")
def api_history():
    """Valid readings for charting. Query: ?minutes=60 (default) or ?start=&end=."""
    minutes = request.args.get("minutes", type=int)
    start = request.args.get("start")
    end = request.args.get("end")

    if start or end:
        rows = db.history(start=start, end=end, limit=5000)
    elif minutes:
        since = (datetime.now() - timedelta(minutes=minutes)).isoformat(
            timespec="seconds"
        )
        rows = db.history(start=since, limit=5000)
    else:
        rows = db.history(limit=5000)

    # Chart.js expects arrays ordered oldest first.
    rows = list(reversed(rows))
    return jsonify(
        {
            "timestamps": [r["timestamp"] for r in rows],
            "bus_voltage_v": [r["bus_voltage_v"] for r in rows],
            "current_ma": [r["current_ma"] for r in rows],
            "power_mw": [r["power_mw"] for r in rows],
            "energy_wh": [r["energy_wh"] for r in rows],
        }
    )


@app.route("/api/daily")
def api_daily():
    """Daily totals for the last 30 days."""
    return jsonify(db.daily_totals(days=30))


@app.route("/export.csv")
def export_csv():
    """CSV download of valid readings. Query: ?start=...&end=..."""
    start = request.args.get("start")
    end = request.args.get("end")
    csv_text = db.export_csv(start=start, end=end)
    filename = f"solar_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ------------------------------------------------------------------ sampling lifecycle

def start_sampling() -> None:
    global _sampler_thread
    if _sampler_thread is None or not _sampler_thread.is_alive():
        _stop.clear()
        _sampler_thread = threading.Thread(target=_sample_loop, daemon=True)
        _sampler_thread.start()


def stop_sampling() -> None:
    _stop.set()
    if _sampler_thread is not None:
        _sampler_thread.join(timeout=5)


start_sampling()

# Flask dev server is single-threaded by default in older versions; enable
# threading so API polling and the background sampler coexist cleanly.
if __name__ == "__main__":
    try:
        app.run(host=FLASK_HOST, port=FLASK_PORT, threaded=True, use_reloader=False)
    finally:
        stop_sampling()
