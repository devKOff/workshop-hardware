"""Phase 9: Settings persistence and system information diagnostics tests.

Tests:
- Settings persistence across application restarts (re-open same DB)
- Settings validation (invalid input rejected with explanation)
- Never silently switch from hardware to simulation mode
- System information: versions, OS, backend status, database health,
  sensor diagnostics, dependency diagnostics, recent logs
- Hardware availability gating on Settings page
"""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from solar_monitor.backends import SimulatedSensor
from solar_monitor.core.measurement_engine import EngineState, MeasurementEngine
from solar_monitor.database.connection import open_db
from solar_monitor.database.settings import SettingsError, SettingsService


def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_QAPP = _qapp()


def _make_conn(tmp_path):
    db_path = os.path.join(str(tmp_path), "settings.db")
    return open_db(db_path), db_path


# ── Settings persistence tests ─────────────────────────────────────────────


def test_settings_persist_across_restart(tmp_path):
    """Settings saved in one connection must be readable after re-opening
    the same database file (simulating an application restart)."""
    db_path = os.path.join(str(tmp_path), "persist.db")
    conn1 = open_db(db_path)
    svc1 = SettingsService(conn1)
    svc1.set("sampling_interval_s", 7.5)
    svc1.set("sensor_mode", "hardware")
    conn1.close()

    # Simulate restart: new connection to the same DB file.
    conn2 = open_db(db_path)
    svc2 = SettingsService(conn2)
    assert svc2.get("sampling_interval_s") == 7.5
    assert svc2.get("sensor_mode") == "hardware"
    conn2.close()


def test_settings_defaults_when_no_stored_value(tmp_path):
    conn, _ = _make_conn(tmp_path)
    svc = SettingsService(conn)
    assert svc.get("sampling_interval_s") == 2.0
    assert svc.get("sensor_mode") == "simulated"
    assert svc.get("graph_history_seconds") == 300.0
    conn.close()


def test_settings_validation_rejects_invalid(tmp_path):
    conn, _ = _make_conn(tmp_path)
    svc = SettingsService(conn)

    # Negative interval rejected
    with pytest.raises(SettingsError, match="must be > 0"):
        svc.set("sampling_interval_s", -1.0)
    # Zero interval rejected
    with pytest.raises(SettingsError, match="must be > 0"):
        svc.set("sampling_interval_s", 0.0)
    # Non-numeric rejected
    with pytest.raises(SettingsError, match="must be a number"):
        svc.set("sampling_interval_s", "not-a-number")
    # Unknown key rejected
    with pytest.raises(SettingsError, match="unknown setting"):
        svc.set("does_not_exist", "x")
    with pytest.raises(SettingsError, match="unknown setting"):
        svc.get("does_not_exist")
    # Invalid sensor mode rejected
    with pytest.raises(SettingsError, match="must be one of"):
        svc.set("sensor_mode", "not-a-mode")

    # Value unchanged after failed set
    assert svc.get("sampling_interval_s") == 2.0
    conn.close()


def test_settings_valid_values_accepted(tmp_path):
    conn, _ = _make_conn(tmp_path)
    svc = SettingsService(conn)
    svc.set("sampling_interval_s", 0.1)
    assert svc.get("sampling_interval_s") == 0.1
    svc.set("sampling_interval_s", 3600.0)
    assert svc.get("sampling_interval_s") == 3600.0
    svc.set("sensor_mode", "hardware")
    assert svc.get("sensor_mode") == "hardware"
    svc.set("sensor_mode", "simulated")
    assert svc.get("sensor_mode") == "simulated"
    conn.close()


# ── Settings page UI tests ─────────────────────────────────────────────────


def test_settings_page_save_interval_and_mode(tmp_path):
    from solar_monitor.database.settings import SettingsService
    from solar_monitor.gui.main_window import AppContext
    from solar_monitor.gui.pages.settings import SettingsPage

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

    page = SettingsPage(ctx, None)
    page.interval_spin.setValue(7.0)
    page.mode_combo.setCurrentIndex(0)  # simulation
    page._save()
    assert ctx.settings.get("sampling_interval_s") == 7.0
    assert ctx.settings.get("sensor_mode") == "simulated"
    assert engine.sampling_interval_s == 7.0
    assert "Saved:" in page.status_label.text()
    page.close()
    engine.stop()
    conn.close()


def test_settings_page_rejects_hardware_when_unavailable(tmp_path):
    """Selecting Hardware when the INA219 backend is unavailable must be
    rejected with an explanation — never silently fall back to simulation."""
    from solar_monitor.database.settings import SettingsService
    from solar_monitor.backends import INA219HardwareBackend
    from solar_monitor.gui.main_window import AppContext
    from solar_monitor.gui.pages.settings import SettingsPage

    db_path = os.path.join(str(tmp_path), "page_hw.db")
    conn = open_db(db_path)
    settings = SettingsService(conn)
    sim = SimulatedSensor()
    hw = INA219HardwareBackend()  # unavailable on Windows (no driver)
    assert hw.is_available() is False
    engine = MeasurementEngine(sim, db_path=db_path)
    ctx = AppContext.__new__(AppContext)
    ctx.db_path = db_path
    ctx.conn = conn
    ctx.settings = settings
    ctx.sim_backend = sim
    ctx.hw_backend = hw
    ctx.backend = sim  # currently in simulation mode
    ctx.engine = engine

    page = SettingsPage(ctx, None)
    page.mode_combo.setCurrentIndex(1)  # hardware
    page._save()
    # Must reject: mode unchanged, error shown
    assert ctx.settings.get("sensor_mode") == "simulated"
    assert engine.backend_mode == "simulated"
    assert "Invalid setting" in page.status_label.text() or "unavailable" in page.status_label.text()
    page.close()
    engine.stop()
    conn.close()


# ── System information tests ───────────────────────────────────────────────


def test_system_information_page_loads(tmp_path):
    from solar_monitor.database.settings import SettingsService
    from solar_monitor.gui.main_window import AppContext
    from solar_monitor.gui.pages.system_information import SystemInformationPage

    db_path = os.path.join(str(tmp_path), "sys.db")
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

    page = SystemInformationPage(ctx, None)
    _qapp().processEvents()
    # Verify key info labels exist
    found_app = False
    found_python = False
    found_mode = False
    found_db = False
    for child in page.findChildren(QLabel):
        text = child.text()
        if "Application: Solar Panel Performance Monitor" in text:
            found_app = True
        if "Python:" in text:
            found_python = True
        if "Operating mode:" in text:
            found_mode = True
        if "Database path:" in text:
            found_db = True
    assert found_app, "Application label missing"
    assert found_python, "Python version label missing"
    assert found_mode, "Operating mode label missing"
    assert found_db, "Database path label missing"
    page.close()
    engine.stop()
    conn.close()


def test_system_information_database_health(tmp_path):
    from solar_monitor.database.settings import SettingsService
    from solar_monitor.gui.main_window import AppContext
    from solar_monitor.gui.pages.system_information import SystemInformationPage

    db_path = os.path.join(str(tmp_path), "sys_health.db")
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

    page = SystemInformationPage(ctx, None)
    _qapp().processEvents()
    health_text = ""
    for child in page.findChildren(QLabel):
        health_text += child.text() + "\n"
    assert "Integrity check:" in health_text
    assert "Journal mode:" in health_text
    assert "Schema version:" in health_text
    assert "Status: healthy" in health_text
    page.close()
    engine.stop()
    conn.close()


def test_system_information_dependency_diagnostics(tmp_path):
    from solar_monitor.database.settings import SettingsService
    from solar_monitor.gui.main_window import AppContext
    from solar_monitor.gui.pages.system_information import SystemInformationPage

    db_path = os.path.join(str(tmp_path), "sys_deps.db")
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

    page = SystemInformationPage(ctx, None)
    _qapp().processEvents()
    dep_text = ""
    for child in page.findChildren(QLabel):
        dep_text += child.text() + "\n"
    assert "PySide6:" in dep_text
    assert "pyqtgraph:" in dep_text
    assert "sqlite3:" in dep_text
    page.close()
    engine.stop()
    conn.close()


def test_hardware_mode_never_silently_switches_to_simulation(tmp_path):
    """The engine must remain in hardware mode when the user selects hardware
    and hardware is unavailable — never silently substituted by simulation."""
    from solar_monitor.backends import INA219HardwareBackend
    from solar_monitor.database.settings import SettingsService
    from solar_monitor.gui.main_window import AppContext
    from solar_monitor.gui.pages.settings import SettingsPage

    db_path = os.path.join(str(tmp_path), "noswitch.db")
    conn = open_db(db_path)
    settings = SettingsService(conn)
    sim = SimulatedSensor()
    hw = INA219HardwareBackend()
    assert hw.is_available() is False
    engine = MeasurementEngine(sim, db_path=db_path)
    ctx = AppContext.__new__(AppContext)
    ctx.db_path = db_path
    ctx.conn = conn
    ctx.settings = settings
    ctx.sim_backend = sim
    ctx.hw_backend = hw
    ctx.backend = sim
    ctx.engine = engine

    page = SettingsPage(ctx, None)
    page.mode_combo.setCurrentIndex(1)  # hardware
    page._save()
    # Engine must still be simulation (hardware rejected)
    assert engine.backend_mode == "simulated"
    assert ctx.backend.mode == "simulated"
    page.close()
    engine.stop()
    conn.close()


def test_engine_keeps_backend_fixed_at_construction(tmp_path):
    """The backend is fixed at engine construction time; the engine never
    substitutes simulation for hardware."""
    from solar_monitor.backends import INA219HardwareBackend
    from solar_monitor.database.settings import SettingsService

    db_path = os.path.join(str(tmp_path), "fixed.db")
    conn = open_db(db_path)
    settings = SettingsService(conn)
    sim = SimulatedSensor()
    hw = INA219HardwareBackend()
    engine = MeasurementEngine(hw, db_path=db_path)
    assert engine.backend_mode == "hardware"
    assert engine.backend is hw
    engine.stop()
    conn.close()
