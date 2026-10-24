"""Tests for SQLite persistence (app/database.py)."""

import os
import tempfile
from datetime import datetime, timedelta

import pytest

from app.database import Database, DatabaseError
from app.models import DailyEnergy, Measurement


def _m(ts, power_w):
    return Measurement(ts, 6.0, power_w / 6.0 * 1000.0, power_w / 6.0, power_w)


def test_insert_and_retrieve_measurement(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    m = _m(datetime(2026, 10, 19, 10, 0, 0), 3.0)
    row_id = db.insert_measurement(m)
    assert isinstance(row_id, int) and row_id > 0

    latest = db.get_latest()
    assert latest is not None
    assert latest.voltage_v == pytest.approx(6.0)
    assert latest.power_w == pytest.approx(3.0)
    assert latest.sensor_ok is True


def test_insert_failed_measurement(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    m = Measurement(
        datetime(2026, 10, 19, 10, 0, 0),
        0.0, 0.0, 0.0, 0.0,
        sensor_ok=False, error_message="sensor disconnected",
    )
    db.insert_measurement(m)
    latest = db.get_latest()
    assert latest.sensor_ok is False
    assert latest.error_message == "sensor disconnected"


def test_get_measurements_time_range(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    base = datetime(2026, 10, 19, 10, 0, 0)
    for i in range(5):
        db.insert_measurement(_m(base + timedelta(minutes=i), float(i + 1)))

    all_m = db.get_measurements()
    assert len(all_m) == 5
    # Oldest first.
    assert all_m[0].power_w == pytest.approx(1.0)
    assert all_m[-1].power_w == pytest.approx(5.0)

    window = db.get_measurements(
        start=base + timedelta(minutes=1),
        end=base + timedelta(minutes=3),
    )
    assert len(window) == 3

    limited = db.get_measurements(limit=2)
    assert len(limited) == 2


def test_database_restart_persistence(tmp_path):
    path = str(tmp_path / "restart.db")
    db1 = Database(path)
    db1.insert_measurement(_m(datetime(2026, 10, 19, 10, 0, 0), 3.0))
    db1.close()

    # "Restart": open a new connection to the same file.
    db2 = Database(path)
    assert db2.get_measurement_count() == 1
    latest = db2.get_latest()
    assert latest.power_w == pytest.approx(3.0)
    db2.close()


def test_database_empty_returns_none(tmp_path):
    db = Database(str(tmp_path / "empty.db"))
    assert db.get_latest() is None
    assert db.get_measurements() == []
    assert db.get_measurement_count() == 0


def test_upsert_and_get_daily_summaries(tmp_path):
    db = Database(str(tmp_path / "daily.db"))
    db.upsert_daily_summary(DailyEnergy("2026-10-18", 12.5, 1.0, 5.0, 3.0, 10))
    db.upsert_daily_summary(DailyEnergy("2026-10-19", 25.0, 2.0, 6.0, 4.0, 20))

    summaries = db.get_daily_summaries()
    assert len(summaries) == 2
    assert summaries[0].date == "2026-10-18"
    assert summaries[0].energy_wh == pytest.approx(12.5)

    filtered = db.get_daily_summaries(start_date="2026-10-19")
    assert len(filtered) == 1
    assert filtered[0].date == "2026-10-19"


def test_database_error_on_bad_path(tmp_path):
    # A path in a non-existent directory should raise DatabaseError.
    bad = str(tmp_path / "no_such_dir" / "test.db")
    with pytest.raises(DatabaseError):
        Database(bad)
