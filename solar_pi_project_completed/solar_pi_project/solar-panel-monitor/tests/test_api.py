"""Tests for the Flask JSON API (app/api.py) using the test client."""

from datetime import datetime, timedelta

import pytest

from app import create_app
from app.config import Config
from app.database import Database
from app.models import Measurement
from app.services.history_service import HistoryService
from app.services.sensor_service import SensorService


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path / "api_test.db"),
            "DEBUG": False,
        }
    )
    cfg.validate()
    app = create_app(cfg)
    # Seed a couple of measurements so history/export endpoints have data.
    base = datetime(2026, 10, 19, 10, 0, 0)
    for i in range(3):
        app.solar_database.insert_measurement(
            Measurement(base + timedelta(minutes=i), 6.0, 100.0 * (i + 1), 0.1 * (i + 1), 0.6 * (i + 1))
        )
    return app.test_client()


def _json(res):
    return res.get_json()


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = _json(res)
    assert body["status"] in {"ok", "degraded"}
    assert "sensor" in body
    assert body["sensor"]["mode"] == "simulation"
    assert "utc_timestamp" in body


def test_status_alias(client):
    res = client.get("/api/status")
    assert res.status_code == 200


def test_current_measurement(client):
    res = client.get("/api/measurements/current")
    assert res.status_code == 200
    body = _json(res)
    assert "timestamp" in body
    assert "voltage_v" in body
    assert "current_ma" in body
    assert "power_w" in body


def test_measurement_history(client):
    res = client.get("/api/measurements/history")
    assert res.status_code == 200
    body = _json(res)
    assert body["count"] == 3
    assert len(body["measurements"]) == 3


def test_measurement_history_invalid_limit(client):
    res = client.get("/api/measurements/history?limit=0")
    assert res.status_code == 400


def test_measurement_history_invalid_timestamp(client):
    res = client.get("/api/measurements/history?start=not-a-date")
    assert res.status_code == 400


def test_measurement_history_range(client):
    base = "2026-10-19T10:00:00"
    end = "2026-10-19T10:03:00"
    res = client.get(f"/api/measurements/history?start={base}&end={end}")
    assert res.status_code == 200
    body = _json(res)
    assert body["count"] == 3


def test_energy_summary(client):
    res = client.get("/api/energy/summary")
    assert res.status_code == 200
    body = _json(res)
    assert "total_energy_wh" in body
    assert "avg_power_w" in body
    assert "sample_count" in body


def test_energy_summary_invalid_timestamp(client):
    res = client.get("/api/energy/summary?start=bad")
    assert res.status_code == 400


def test_daily_energy(client):
    res = client.get("/api/energy/daily")
    assert res.status_code == 200
    body = _json(res)
    assert "daily" in body
    assert isinstance(body["daily"], list)


def test_export_json(client):
    res = client.get("/api/export/json")
    assert res.status_code == 200
    body = _json(res)
    assert body["count"] == 3
    assert len(body["measurements"]) == 3


def test_export_csv(client):
    res = client.get("/api/export/csv")
    assert res.status_code == 200
    assert "text/csv" in res.content_type
    text = res.data.decode("utf-8")
    assert text.startswith("timestamp,voltage_v,current_ma")
    assert text.count("\n") >= 3


def test_export_empty_range(client):
    res = client.get("/api/export/csv?start=2020-01-01T00:00:00&end=2020-01-01T01:00:00")
    assert res.status_code == 404


def test_sampling_start_stop(client):
    res = client.post("/api/sampling/start")
    assert res.status_code == 200
    assert _json(res)["sampling"] is True

    res = client.post("/api/sampling/stop")
    assert res.status_code == 200
    assert _json(res)["sampling"] is False

    res = client.get("/api/sampling/status")
    assert res.status_code == 200


def test_index_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.content_type
    assert b"Solar Panel Monitor" in res.data


def test_health_page(client):
    res = client.get("/health")
    assert res.status_code == 200


def test_current_measurement_none_when_empty(tmp_path, monkeypatch):
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path / "empty_api.db"),
        }
    )
    app = create_app(cfg)
    c = app.test_client()
    res = c.get("/api/measurements/current")
    assert res.status_code == 404
