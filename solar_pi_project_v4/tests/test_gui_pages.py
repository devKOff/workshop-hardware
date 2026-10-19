"""Phase 6 GUI integration tests for the six wired pages.

Uses a real SQLite DB in a temp dir and the real simulation backend. Windows are
closed explicitly to keep Qt teardown orderly.
"""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from solar_monitor.backends import SimulatedSensor
from solar_monitor.core.measurement_engine import EngineState, MeasurementEngine
from solar_monitor.database.connection import open_db
from solar_monitor.database.settings import SettingsService
from solar_monitor.gui.main_window import AppContext


def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_QAPP = _qapp()


def _make_context(tmp_path):
    db_path = os.path.join(str(tmp_path), "phase6.db")
    conn = open_db(db_path)
    settings = SettingsService(conn)
    sim = SimulatedSensor()
    engine = MeasurementEngine(sim, db_path=db_path)
    ctx = AppContext.__new__(AppContext)
    ctx.db_path = db_path
    ctx.conn = conn
    ctx.settings = settings
    ctx.sim_backend = sim
    ctx.hw_backend = sim  # avoid hardware unavailability in tests
    ctx.backend = sim
    ctx.engine = engine
    return ctx


def test_all_six_pages_load_via_nav():
    ctx = _make_context(__import__("tempfile").mkdtemp())
    from solar_monitor.gui.pages.dashboard import DashboardPage
    from solar_monitor.gui.pages.live_monitoring import LiveMonitoringPage
    from solar_monitor.gui.pages.historical_data import HistoricalDataPage
    from solar_monitor.gui.pages.csv_reports import CSVReportsPage
    from solar_monitor.gui.pages.settings import SettingsPage
    from solar_monitor.gui.pages.system_information import SystemInformationPage

    pages = [
        DashboardPage(ctx, None),
        LiveMonitoringPage(ctx, None),
        HistoricalDataPage(ctx, None),
        CSVReportsPage(ctx, None),
        SettingsPage(ctx, None),
        SystemInformationPage(ctx, None),
    ]
    assert len(pages) == 6
    titles = ["Dashboard", "Live Monitoring", "Historical Data", "CSV Reports",
              "Settings", "System Information"]
    for p, expected in zip(pages, titles):
        assert p._heading == expected
        p.close()
    ctx.close()


def test_dashboard_receives_measurements(tmp_path):
    ctx = _make_context(tmp_path)
    from solar_monitor.gui.pages.dashboard import DashboardPage
    page = DashboardPage(ctx, None)
    engine = ctx.engine
    engine.on_measurement = page.on_measurement
    from solar_monitor.core.measurement import Measurement
    m = Measurement("2026-01-01T00:00:00+00:00", 5.5, 100.0, 0.1, 0.55, "simulated", "ok")
    engine.on_measurement(m, None, 0.125)
    _qapp().processEvents()
    assert page._latest is not None
    assert page.voltage_value.text() == f"{m.voltage_v:.2f} V"
    page.close()
    engine.stop()
    ctx.close()


def test_live_monitoring_start_stop_pause_resume(tmp_path):
    ctx = _make_context(tmp_path)
    from solar_monitor.gui.pages.live_monitoring import LiveMonitoringPage
    page = LiveMonitoringPage(ctx, None)
    engine = ctx.engine
    page._start()
    _qapp().processEvents()
    assert engine.state == EngineState.RUNNING
    page._pause()
    _qapp().processEvents()
    assert engine.state == EngineState.PAUSED
    page._resume()
    _qapp().processEvents()
    assert engine.state == EngineState.RUNNING
    page._stop()
    _qapp().processEvents()
    assert engine.state == EngineState.IDLE
    page.close()
    ctx.close()


def test_settings_persist_interval_and_mode(tmp_path):
    ctx = _make_context(tmp_path)
    from solar_monitor.gui.pages.settings import SettingsPage
    page = SettingsPage(ctx, None)
    page.interval_spin.setValue(7.0)
    page.mode_combo.setCurrentIndex(0)  # simulation
    page._save()
    assert ctx.settings.get("sampling_interval_s") == 7.0
    assert ctx.settings.get("sensor_mode") == "simulated"
    assert engine_interval(ctx) == 7.0
    page.close()
    ctx.close()


def engine_interval(ctx):
    return ctx.engine.sampling_interval_s


def test_historical_data_loads_from_db(tmp_path):
    ctx = _make_context(tmp_path)
    from solar_monitor.core.measurement import Measurement
    from solar_monitor.database.dao import create_session, insert_measurement
    from solar_monitor.core.validation import validate_reading

    sid = create_session(ctx.conn, name="s1", sensor_mode="simulated")
    m = validate_reading(5.5, 0.1, 0.55, mode="simulated", status="ok")
    insert_measurement(ctx.conn, sid, m)

    from solar_monitor.gui.pages.historical_data import HistoricalDataPage
    page = HistoricalDataPage(ctx, None)
    _qapp().processEvents()
    assert page.table.model().rowCount() >= 1
    page.close()
    ctx.close()


def test_csv_export_writes_fixed_schema(tmp_path):
    ctx = _make_context(tmp_path)
    from solar_monitor.core.measurement import Measurement
    from solar_monitor.database.dao import create_session, insert_measurement
    from solar_monitor.core.validation import validate_reading
    from solar_monitor.services.csv_export import CSV_COLUMNS, export_measurements

    sid = create_session(ctx.conn, name="csv1", sensor_mode="simulated")
    m = validate_reading(5.5, 0.1, 0.55, mode="simulated", status="ok")
    insert_measurement(ctx.conn, sid, m, energy_increment_wh=0.001,
                       daily_energy_wh=0.001, total_energy_wh=0.001)

    out = os.path.join(str(tmp_path), "out.csv")
    n = export_measurements(out, [m])
    assert n == 1
    with open(out, encoding="utf-8-sig") as fh:
        header = fh.readline().strip().split(",")
        row = fh.readline().strip().split(",")
    assert header == CSV_COLUMNS
    assert len(row) == len(CSV_COLUMNS)
    ctx.close()


def test_csv_export_empty_reports_error(tmp_path):
    ctx = _make_context(tmp_path)
    from solar_monitor.services.csv_export import export_measurements
    out = os.path.join(str(tmp_path), "empty.csv")
    with pytest.raises(ValueError, match="No measurements"):
        export_measurements(out, [])
    ctx.close()


