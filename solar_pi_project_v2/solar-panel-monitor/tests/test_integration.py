"""End-to-end integration tests for the full application stack."""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app import create_app
from app.config import Config
from app.database import Database
from app.hardware.simulated_sensor import SimulatedSensor, SimulatedSensorError
from app.models import Measurement
from app.services.sensor_service import SensorService, SensorServiceError


def test_full_sample_persist_api_roundtrip(tmp_path):
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path / "int.db"),
        }
    )
    app = create_app(cfg)
    app.sensor_service.start_sampling()
    time.sleep(3)  # several samples at 1s interval

    c = app.test_client()
    cur = c.get("/api/measurements/current").get_json()
    assert cur is not None
    assert cur["sensor_ok"] is True
    assert cur["power_w"] >= 0

    hist = c.get("/api/measurements/history").get_json()
    assert hist["count"] >= 2

    summ = c.get("/api/energy/summary").get_json()
    assert summ["sample_count"] >= 2
    assert summ["total_energy_wh"] >= 0

    app.sensor_service.shutdown()


def test_duplicate_sampler_prevention(tmp_path):
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path / "dup.db"),
        }
    )
    app = create_app(cfg)
    app.sensor_service.start_sampling()
    with pytest.raises(SensorServiceError):
        app.sensor_service.start_sampling()  # duplicate
    app.sensor_service.shutdown()


def test_graceful_shutdown_stops_sampler(tmp_path):
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path / "shutdown.db"),
        }
    )
    app = create_app(cfg)
    app.sensor_service.start_sampling()
    assert app.sensor_service.is_running()
    app.sensor_service.shutdown()
    assert app.sensor_service.is_running() is False


def test_database_exception_is_surfaced(tmp_path):
    # Point the database at a path that cannot be created.
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": "/proc/impossible/should_not_exist.db",
        }
    )
    from app.database import DatabaseError
    with pytest.raises(DatabaseError):
        Database(cfg.database_path)


def test_simulated_sensor_error_propagation():
    # A sensor whose .read() raises should propagate through the service
    # without being replaced by simulated data.
    class FailingSensor:
        mode = "simulation"
        connected = True
        def read(self):
            raise SimulatedSensorError("boom")

    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path := __import__("pathlib").Path(__import__("tempfile").mkdtemp()) / "fail.db"),
        }
    )
    db = Database(cfg.database_path)
    service = SensorService(cfg, db, sensor=FailingSensor())
    with pytest.raises(SensorServiceError):
        service.take_reading()
    status = service.status()
    assert status.connected is False
    assert status.error_message is not None


def test_dashboard_shows_disconnected_state_when_sensor_fails(tmp_path):
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path / "disc.db"),
        }
    )
    app = create_app(cfg)

    class FailingSensor:
        mode = "simulation"
        connected = False
        last_error = "link down"
        def read(self):
            raise SimulatedSensorError("link down")

    app.sensor_service._sensor = FailingSensor()
    app.sensor_service._record_failure("link down")
    c = app.test_client()
    health = c.get("/api/health").get_json()
    assert health["sensor"]["connected"] is False


def test_restart_preserves_history(tmp_path):
    path = str(tmp_path / "persist.db")
    app1 = create_app(Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": path,
        }
    ))
    app1.solar_database.insert_measurement(
        Measurement(datetime(2026, 10, 19, 10, 0, 0), 6.0, 100.0, 0.6, 0.6)
    )
    app1.solar_database.close()

    # Simulate restart: new app instance over the same database file.
    app2 = create_app(Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": path,
        }
    ))
    c = app2.test_client()
    cur = c.get("/api/measurements/current").get_json()
    assert cur is not None
    assert cur["power_w"] == 0.6


def test_polling_endpoints_return_consistent_schema(tmp_path):
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path / "schema.db"),
        }
    )
    app = create_app(cfg)
    app.solar_database.insert_measurement(
        Measurement(datetime(2026, 10, 19, 10, 0, 0), 6.0, 100.0, 0.6, 0.6)
    )
    c = app.test_client()
    for endpoint in [
        "/api/health",
        "/api/measurements/current",
        "/api/energy/summary",
        "/api/energy/daily",
        "/api/sampling/status",
    ]:
        res = c.get(endpoint)
        assert res.status_code == 200, endpoint
        assert res.is_json
