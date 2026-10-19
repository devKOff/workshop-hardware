"""Phase 8: Historical data date/time filtering tests.

Tests DAO-level list_measurements filtering (start/end timestamps) and the
Historical Data GUI page filtering behavior. Records persist across restarts
(verified by re-opening the same database file).
"""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from solar_monitor.core.measurement import Measurement
from solar_monitor.core.validation import validate_reading
from solar_monitor.database.connection import open_db
from solar_monitor.database.dao import create_session, insert_measurement, list_measurements


def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_QAPP = _qapp()


def _make_conn(tmp_path):
    db_path = os.path.join(str(tmp_path), "filter.db")
    return open_db(db_path), db_path


def _insert_readings(conn, sid, base, count=5, spacing_s=3600):
    """Insert `count` readings spaced `spacing_s` seconds apart from `base`."""
    from datetime import datetime, timedelta
    base_dt = datetime.fromisoformat(base)
    ids = []
    for i in range(count):
        ts = base_dt + timedelta(seconds=spacing_s * i)
        m = validate_reading(
            5.0 + i * 0.1, 0.1 + i * 0.01, 0.5 + i * 0.05,
            mode="simulated", status="ok",
        )
        m = Measurement(
            timestamp=ts.isoformat(),
            voltage_v=m.voltage_v, current_ma=m.current_ma, current_a=m.current_a,
            power_w=m.power_w, sensor_mode=m.sensor_mode, sensor_status=m.sensor_status,
        )
        insert_measurement(conn, sid, m,
                           energy_increment_wh=0.001 * i,
                           daily_energy_wh=0.001 * i,
                           total_energy_wh=0.001 * i)
        ids.append(m.timestamp)
    return ids


def test_list_measurements_no_filter_returns_all(tmp_path):
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="all", sensor_mode="simulated")
    base = "2026-03-15T10:00:00+00:00"
    _insert_readings(conn, sid, base, count=5, spacing_s=3600)
    rows = list_measurements(conn, limit=1000)
    assert len(rows) == 5
    # Newest first.
    assert rows[0]["timestamp"] > rows[-1]["timestamp"]
    conn.close()


def test_list_measurements_start_filter(tmp_path):
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="start", sensor_mode="simulated")
    base = "2026-03-15T10:00:00+00:00"
    ids = _insert_readings(conn, sid, base, count=5, spacing_s=3600)
    # Only records at or after 12:00 (indices 2,3,4).
    rows = list_measurements(conn, start="2026-03-15T12:00:00+00:00", limit=1000)
    assert len(rows) == 3
    assert all(r["timestamp"] >= "2026-03-15T12:00:00+00:00" for r in rows)
    conn.close()


def test_list_measurements_end_filter(tmp_path):
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="end", sensor_mode="simulated")
    base = "2026-03-15T10:00:00+00:00"
    _insert_readings(conn, sid, base, count=5, spacing_s=3600)
    # Only records at or before 12:00 (indices 0,1,2).
    rows = list_measurements(conn, end="2026-03-15T12:00:00+00:00", limit=1000)
    assert len(rows) == 3
    assert all(r["timestamp"] <= "2026-03-15T12:00:00+00:00" for r in rows)
    conn.close()


def test_list_measurements_start_and_end_filter(tmp_path):
    conn, _ = _make_conn(tmp_path)
    sid = create_session(conn, name="range", sensor_mode="simulated")
    base = "2026-03-15T10:00:00+00:00"
    _insert_readings(conn, sid, base, count=5, spacing_s=3600)
    # Only records from 11:00 to 13:00 (index 1, 2, 3).
    rows = list_measurements(
        conn, start="2026-03-15T11:00:00+00:00",
        end="2026-03-15T13:00:00+00:00", limit=1000,
    )
    assert len(rows) == 3
    assert all("2026-03-15T11:00:00+00:00" <= r["timestamp"] <= "2026-03-15T13:00:00+00:00" for r in rows)
    conn.close()


def test_list_measurements_empty_db(tmp_path):
    conn, _ = _make_conn(tmp_path)
    create_session(conn, name="empty", sensor_mode="simulated")
    rows = list_measurements(conn, limit=1000)
    assert rows == []
    conn.close()


def test_records_persist_across_restart(tmp_path):
    """Records persist across re-opening the same database file (simulating
    application restart)."""
    db_path = os.path.join(str(tmp_path), "persist.db")
    conn1 = open_db(db_path)
    sid = create_session(conn1, name="persist", sensor_mode="simulated")
    m = validate_reading(5.5, 0.1, 0.55, mode="simulated", status="ok")
    insert_measurement(conn1, sid, m, total_energy_wh=0.001)
    conn1.close()

    # Re-open as if the app restarted.
    conn2 = open_db(db_path)
    rows = list_measurements(conn2, limit=1000)
    assert len(rows) == 1
    assert rows[0]["voltage_v"] == 5.5
    assert rows[0]["total_energy_wh"] == 0.001
    conn2.close()


def test_historical_page_applies_date_filter(tmp_path):
    from solar_monitor.backends import SimulatedSensor
    from solar_monitor.core.measurement_engine import MeasurementEngine
    from solar_monitor.database.settings import SettingsService
    from solar_monitor.gui.main_window import AppContext
    from solar_monitor.gui.pages.historical_data import HistoricalDataPage

    db_path = os.path.join(str(tmp_path), "page.db")
    conn = open_db(db_path)
    settings = SettingsService(conn)
    sim = SimulatedSensor()
    engine = MeasurementEngine(sim, db_path=db_path)
    ctx = AppContext.__new__(AppContext)
    ctx.db_path = db_path
    ctx.conn = conn
    ctx.settings = settings
    ctx.sim_backend = sim
    ctx.hw_backend = sim
    ctx.backend = sim
    ctx.engine = engine

    sid = create_session(conn, name="pg", sensor_mode="simulated")
    _insert_readings(conn, sid, "2026-06-01T08:00:00+00:00", count=4, spacing_s=3600)

    page = HistoricalDataPage(ctx, None)
    _qapp().processEvents()
    assert page.table.model().rowCount() == 4

    # Apply a start filter: only records from 10:00 onward (indices 2 and 3).
    page._load(start="2026-06-01T10:00:00+00:00")
    _qapp().processEvents()
    assert page.table.model().rowCount() == 2

    # Clear filter: all records again.
    page._load()
    _qapp().processEvents()
    assert page.table.model().rowCount() == 4

    page.close()
    engine.stop()
    conn.close()
    engine.stop()
    conn.close()
