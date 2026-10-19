"""CSV export service: fixed schema, atomic temp+rename, UTF-8 with BOM.

Exports historical measurements to a user-selected CSV file. The column schema
is fixed and documented so importers can rely on consistent units and
ISO-8601 timestamps.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone

from solar_monitor.database.dao import list_sessions


# Fixed, documented column schema. Units: V, A, W, Wh; timestamps ISO-8601 UTC.
CSV_COLUMNS = [
    "timestamp_utc",
    "session_id",
    "sensor_mode",
    "sensor_status",
    "voltage_v",
    "current_a",
    "power_w",
    "energy_wh_increment",
    "daily_energy_wh",
    "total_energy_wh",
]


def _format_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def export_measurements(csv_path, measurements, session_name=None):
    """Write measurements to CSV at csv_path using the fixed schema.

    Writes to a temp file then atomically renames, so a partial file is never
    left behind on failure. Returns the number of records written.
    Raises OSError on path/permission errors; ValueError on empty dataset.
    """
    if not measurements:
        raise ValueError("No measurements to export")

    csv_path = os.path.abspath(csv_path)
    out_dir = os.path.dirname(csv_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    tmp_path = csv_path + ".tmp"
    written = 0
    try:
        with open(tmp_path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(CSV_COLUMNS)
            for m in measurements:
                writer.writerow([
                    _format_value(getattr(m, "timestamp", "")),
                    _format_value(getattr(m, "session_id", "")),
                    _format_value(getattr(m, "sensor_mode", "")),
                    _format_value(getattr(m, "sensor_status", "")),
                    _format_value(getattr(m, "voltage_v", "")),
                    _format_value(getattr(m, "current_a", "")),
                    _format_value(getattr(m, "power_w", "")),
                    _format_value(getattr(m, "energy_wh_increment", "")),
                    _format_value(getattr(m, "daily_energy_wh", "")),
                    _format_value(getattr(m, "total_energy_wh", "")),
                ])
                written += 1
        os.replace(tmp_path, csv_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    return written
