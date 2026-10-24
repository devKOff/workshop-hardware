"""Tests for CSV and JSON exports (app/api.py export endpoints)."""

import csv
import io
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.config import Config
from app.models import Measurement


@pytest.fixture
def client(tmp_path):
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path / "export_test.db"),
        }
    )
    app = create_app(cfg)
    base = datetime(2026, 10, 19, 10, 0, 0)
    for i in range(4):
        app.solar_database.insert_measurement(
            Measurement(
                base + timedelta(minutes=i),
                6.0,
                100.0,
                0.6,
                0.6,
                shunt_voltage_mv=0.6,
                bus_voltage_v=6.0,
                load_voltage_v=5.9994,
            )
        )
    return app.test_client()


def test_csv_export_structure(client):
    res = client.get("/api/export/csv")
    assert res.status_code == 200
    assert res.headers["Content-Disposition"].startswith("attachment")
    text = res.data.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    assert len(rows) == 4
    expected_cols = {
        "timestamp", "voltage_v", "current_ma", "current_a", "power_w",
        "shunt_voltage_mv", "bus_voltage_v", "load_voltage_v", "sensor_ok", "error_message",
    }
    assert expected_cols.issubset(set(reader.fieldnames))
    assert all(float(r["voltage_v"]) == 6.0 for r in rows)


def test_json_export_structure(client):
    res = client.get("/api/export/json")
    assert res.status_code == 200
    body = res.get_json()
    assert body["count"] == 4
    assert len(body["measurements"]) == 4
    assert "exported_at" in body
    m = body["measurements"][0]
    assert "timestamp" in m
    assert "power_w" in m


def test_export_respects_range(client):
    start = "2026-10-19T10:01:00"
    end = "2026-10-19T10:02:00"
    res = client.get(f"/api/export/json?start={start}&end={end}")
    assert res.status_code == 200
    body = res.get_json()
    assert body["count"] == 2


def test_export_invalid_timestamp(client):
    res = client.get("/api/export/csv?start=not-a-date")
    assert res.status_code == 400
