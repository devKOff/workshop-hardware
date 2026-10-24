"""Tests for the session recorder and CSV export."""

import csv
import os
import tempfile
import time

import pytest

import recorder
from recorder import Recorder, SessionConfig
from sensor import SimulatedSensor


def tempfile_dir():
    return tempfile.gettempdir()


# ------------------------------------------------------------------ #
# Fake sensor
# ------------------------------------------------------------------ #
class FakeSensor:
    def __init__(self, readings=None, detect_ok=True, fail_after=None,
                 fail_every_read=False, data_source="test"):
        self.readings = readings or [
            {"bus_voltage_v": 5.4, "shunt_voltage_v": 0.02, "current_ma": 200.0,
             "overflow": False}
        ]
        self.detect_ok = detect_ok
        self.fail_after = fail_after          # fail on read N+1
        self.fail_every_read = fail_every_read
        self.data_source = data_source
        self.name = "FakeSensor"
        self.read_count = 0
        self.closed = False

    def detect(self):
        return self.detect_ok

    def read_raw(self):
        self.read_count += 1
        if self.fail_every_read:
            raise RuntimeError("simulated read failure")
        if self.fail_after is not None and self.read_count > self.fail_after:
            raise RuntimeError(f"read failure after {self.fail_after}")
        r = self.readings[(self.read_count - 1) % len(self.readings)]
        return dict(r)

    def close(self):
        self.closed = True


# ------------------------------------------------------------------ #
# Simulator: plausible + labeled
# ------------------------------------------------------------------ #
def test_simulator_values_plausible_and_labeled():
    sim = SimulatedSensor(seed=7)
    assert sim.detect()
    assert sim.data_source == "simulation"
    rec = Recorder(SessionConfig(duration_s=0.2, interval_s=0.05))
    rec.start(sim)
    # Wait for the session to auto-complete.
    deadline = time.time() + 5
    while rec.is_monitoring() and time.time() < deadline:
        time.sleep(0.02)
    rec.close()
    assert rec.status == recorder.STATUS_COMPLETED
    assert rec.sample_count() > 0
    for s in rec._samples:
        assert s["data_source"] == "simulation"
        assert 0.0 <= s["voltage_v"] <= 32.0
        assert 0.0 <= s["current_ma"] <= 2000.0
        assert s["status"] == "ok"


# ------------------------------------------------------------------ #
# Power calculation
# ------------------------------------------------------------------ #
def test_power_is_voltage_times_current():
    from sensor import validate_reading
    r = validate_reading(bus_voltage_v=5.0, shunt_voltage_v=0.0, current_ma=1000.0)
    assert r.power_w == pytest.approx(5.0 * 1.0)


# ------------------------------------------------------------------ #
# Validation: invalid readings never become zero
# ------------------------------------------------------------------ #
def test_invalid_readings_stored_not_zero(recorder_with_fake):
    rec, fake = recorder_with_fake
    # NaN bus voltage -> read_error, values None (not 0)
    fake.readings = [{"bus_voltage_v": float("nan"), "shunt_voltage_v": 0.0,
                      "current_ma": 100.0, "overflow": False}]
    rec.start(fake)
    time.sleep(0.2)
    rec.stop()
    rec._thread.join(timeout=5)
    assert rec.sample_count() >= 1
    bad = [s for s in rec._samples if s["status"] != "ok"]
    assert bad, "expected at least one invalid sample"
    for s in bad:
        assert s["voltage_v"] is None
        assert s["current_ma"] is None
        assert s["power_w"] is None


# ------------------------------------------------------------------ #
# Auto-complete
# ------------------------------------------------------------------ #
def test_auto_complete_on_duration(recorder_with_fake):
    rec, fake = recorder_with_fake
    rec.config.duration_s = 0.4
    rec.config.interval_s = 0.1
    rec.start(fake)
    deadline = time.time() + 5
    while rec.is_monitoring() and time.time() < deadline:
        time.sleep(0.02)
    rec._thread.join(timeout=5)
    assert rec.status == recorder.STATUS_COMPLETED
    assert rec.sample_count() >= 1


# ------------------------------------------------------------------ #
# Early stop keeps partial data
# ------------------------------------------------------------------ #
def test_early_stop_keeps_partial_data(recorder_with_fake):
    rec, fake = recorder_with_fake
    rec.config.duration_s = 60.0
    rec.config.interval_s = 0.05
    rec.start(fake)
    time.sleep(0.2)  # let a few samples land
    rec.stop()
    rec._thread.join(timeout=5)
    assert rec.status == recorder.STATUS_STOPPED
    assert rec.sample_count() >= 1
    # Partial data remains exportable.
    path = os.path.join(tempfile_dir(), "partial.csv")
    count = rec.export_csv(path)
    assert count == rec.sample_count()


# ------------------------------------------------------------------ #
# No second worker while monitoring
# ------------------------------------------------------------------ #
def test_no_second_worker(recorder_with_fake):
    rec, fake = recorder_with_fake
    rec.config.duration_s = 60.0
    rec.start(fake)
    with pytest.raises(RuntimeError):
        rec.start(fake)
    rec.stop()
    rec._thread.join(timeout=5)


# ------------------------------------------------------------------ #
# Sensor failure at start (never falls back)
# ------------------------------------------------------------------ #
def test_sensor_failure_at_start():
    rec = Recorder(SessionConfig(duration_s=60.0, interval_s=0.1))
    fake = FakeSensor(detect_ok=False)
    with pytest.raises(RuntimeError) as excinfo:
        rec.start(fake)
    assert "not detected" in str(excinfo.value).lower() or "wiring" in str(excinfo.value).lower()
    assert rec.status == recorder.STATUS_READY
    assert rec.sample_count() == 0


# ------------------------------------------------------------------ #
# Error mid-run: per-sample read failures become read_error samples,
# never zero, and the session continues (auto-completes or stops).
# ------------------------------------------------------------------ #
def test_error_mid_run_records_read_error_not_zero():
    rec = Recorder(SessionConfig(duration_s=0.5, interval_s=0.05))
    fake = FakeSensor(fail_after=2)  # first 2 ok, then every read fails
    rec.start(fake)
    deadline = time.time() + 5
    while rec.is_monitoring() and time.time() < deadline:
        time.sleep(0.02)
    rec._thread.join(timeout=5)
    assert rec.status == recorder.STATUS_COMPLETED
    assert rec.sample_count() >= 3
    errors = [s for s in rec._samples if s["status"] == "read_error"]
    ok = [s for s in rec._samples if s["status"] == "ok"]
    assert ok, "expected some ok samples before failures"
    assert errors, "expected some read_error samples after failures"
    for s in errors:
        assert s["voltage_v"] is None
        assert s["current_ma"] is None
        assert s["power_w"] is None


# ------------------------------------------------------------------ #
# CSV read-back: header, row count, timestamps, values
# ------------------------------------------------------------------ #
def test_csv_export_readback(recorder_with_fake):
    rec, fake = recorder_with_fake
    rec.config.duration_s = 0.3
    rec.config.interval_s = 0.1
    rec.start(fake)
    deadline = time.time() + 5
    while rec.is_monitoring() and time.time() < deadline:
        time.sleep(0.02)
    rec._thread.join(timeout=5)
    assert rec.status == recorder.STATUS_COMPLETED

    path = os.path.join(tempfile_dir(), "readback.csv")
    count = rec.export_csv(path)
    assert count == rec.sample_count()

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = list(csv.reader(f))
    assert reader[0] == recorder.CSV_COLUMNS
    assert len(reader) - 1 == count
    # Every data row has the right column count.
    for row in reader[1:]:
        assert len(row) == len(recorder.CSV_COLUMNS)
    # Timestamps are timezone-aware ISO 8601.
    for row in reader[1:]:
        assert "+" in row[0] or row[0].endswith("Z")
    # Values are present for ok rows.
    ok_rows = [r for r in reader[1:] if r[5] == "ok"]
    assert ok_rows
    assert ok_rows[0][2] != ""   # voltage_v
    assert ok_rows[0][3] != ""   # current_ma
    assert ok_rows[0][4] != ""   # power_w


def test_csv_export_empty_raises():
    rec = Recorder()
    with pytest.raises(ValueError):
        rec.export_csv(os.path.join(tempfile_dir(), "empty.csv"))


def test_csv_export_bad_path_raises_no_half_file():
    rec = Recorder(SessionConfig(duration_s=0.2, interval_s=0.05))
    sim = SimulatedSensor(seed=1)
    rec.start(sim)
    time.sleep(0.15)
    rec.stop()
    rec._thread.join(timeout=5)
    # A path that cannot be written.
    bad = "/nonexistent_directory_xyz/readings.csv"
    with pytest.raises(OSError):
        rec.export_csv(bad)
    # No half-written file should exist at the bad path.
    assert not os.path.exists(bad)
    sim.close()


def test_csv_utf8_bom():
    rec = Recorder(SessionConfig(duration_s=0.2, interval_s=0.05))
    sim = SimulatedSensor(seed=1)
    rec.start(sim)
    time.sleep(0.15)
    rec.stop()
    rec._thread.join(timeout=5)
    path = os.path.join(tempfile_dir(), "bom.csv")
    rec.export_csv(path)
    with open(path, "rb") as f:
        raw = f.read()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    sim.close()


@pytest.fixture
def recorder_with_fake():
    rec = Recorder(SessionConfig(duration_s=60.0, interval_s=0.05))
    fake = FakeSensor()
    return rec, fake
