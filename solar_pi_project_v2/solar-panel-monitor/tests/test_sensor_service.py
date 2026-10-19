"""Tests for the simulated sensor, INA219 driver, and sensor service."""

from datetime import datetime, timedelta
from importlib.util import find_spec
from unittest.mock import patch

import pytest

from app.config import Config

_INA219_INSTALLED = find_spec("ina219") is not None
requires_ina219 = pytest.mark.skipif(
    not _INA219_INSTALLED, reason="ina219 library not installed (Windows dev machine)"
)
no_ina219 = pytest.mark.skipif(
    _INA219_INSTALLED, reason="ina219 installed; hardware-only test not applicable"
)
from app.database import Database
from app.hardware.simulated_sensor import SimulatedSensor, SimulatedSensorError
from app.hardware.ina219_sensor import INA219Sensor, INA219SensorError
from app.models import Measurement
from app.services.sensor_service import SensorService, SensorServiceError


# ------------------------------------------------------------------ #
# Simulated sensor
# ------------------------------------------------------------------ #
def test_simulated_sensor_read_returns_measurement():
    sensor = SimulatedSensor(peak_power_w=3.0, voltage_v=6.0, noise=0.0, seed=1)
    m = sensor.read()
    assert isinstance(m, Measurement)
    assert m.sensor_ok is True
    assert m.voltage_v > 0
    assert m.power_w >= 0
    # Power = voltage * current (within rounding).
    assert abs(m.power_w - m.voltage_v * m.current_a) < 0.01
    assert m.current_ma == pytest.approx(m.current_a * 1000.0, rel=1e-2)


def test_simulated_sensor_modes():
    sensor = SimulatedSensor()
    assert sensor.mode == "simulation"
    assert sensor.connected is True


def test_simulated_sensor_night_returns_zero_power():
    fixed_time = datetime(2026, 10, 19, 23, 0, 0)  # after sunset
    sensor = SimulatedSensor(
        peak_power_w=3.0,
        voltage_v=6.0,
        sunrise_hour=6.0,
        sunset_hour=18.0,
        noise=0.0,
        clock=lambda: fixed_time,
    )
    m = sensor.read()
    assert m.power_w == 0.0
    assert m.current_a == 0.0


def test_simulated_sensor_daytime_produces_power():
    fixed_time = datetime(2026, 10, 19, 12, 0, 0)  # solar noon
    sensor = SimulatedSensor(
        peak_power_w=3.0,
        voltage_v=6.0,
        sunrise_hour=6.0,
        sunset_hour=18.0,
        noise=0.0,
        clock=lambda: fixed_time,
    )
    m = sensor.read()
    assert m.power_w > 0
    assert m.current_ma > 0


def test_simulated_sensor_deterministic_with_seed():
    t = datetime(2026, 10, 19, 12, 0, 0)
    s1 = SimulatedSensor(noise=0.5, seed=42, clock=lambda: t)
    s2 = SimulatedSensor(noise=0.5, seed=42, clock=lambda: t)
    assert s1.read().power_w == s2.read().power_w


def test_simulated_sensor_invalid_config():
    with pytest.raises(ValueError):
        SimulatedSensor(peak_power_w=0)
    with pytest.raises(ValueError):
        SimulatedSensor(voltage_v=0)
    with pytest.raises(ValueError):
        SimulatedSensor(sunrise_hour=20, sunset_hour=18)


# ------------------------------------------------------------------ #
# INA219 hardware driver (guarded import on Windows)
# ------------------------------------------------------------------ #
@requires_ina219
def test_ina219_sensor_mode_hardware():
    sensor = INA219Sensor()
    assert sensor.mode == "hardware"
    assert isinstance(sensor.connected, bool)


@requires_ina219
def test_ina219_read_raises_when_unavailable():
    sensor = INA219Sensor()
    with pytest.raises(INA219SensorError):
        sensor.read()


@requires_ina219
def test_ina219_never_substitutes_simulated_data():
    sensor = INA219Sensor()
    try:
        sensor.read()
    except INA219SensorError:
        pass
    else:
        pytest.skip("INA219 hardware present; substitution check not applicable")
    # Confirm no simulated reading leaks through on error.
    assert sensor.last_error is not None


@no_ina219
def test_ina219_missing_library_clear_error():
    # On a machine without the ina219 library (e.g. Windows), constructing the
    # hardware driver must raise a clear INA219SensorError naming the library.
    with pytest.raises(INA219SensorError) as excinfo:
        INA219Sensor()
    assert "ina219" in str(excinfo.value).lower()


# ------------------------------------------------------------------ #
# Sensor service
# ------------------------------------------------------------------ #
def make_service(tmp_path):
    cfg = Config.from_dict(
        {
            "SENSOR_MODE": "simulation",
            "SAMPLING_INTERVAL_SECONDS": 1,
            "DATABASE_PATH": str(tmp_path / "test.db"),
        }
    )
    db = Database(cfg.database_path)
    return SensorService(cfg, db), cfg, db


def test_sensor_service_starts_and_stops(tmp_path):
    service, _, _ = make_service(tmp_path)
    assert service.is_running() is False
    service.start_sampling()
    assert service.is_running() is True
    service.stop_sampling()
    assert service.is_running() is False


def test_sensor_service_duplicate_start_raises(tmp_path):
    service, _, _ = make_service(tmp_path)
    service.start_sampling()
    with pytest.raises(SensorServiceError):
        service.start_sampling()
    service.stop_sampling()


def test_sensor_service_take_reading(tmp_path):
    service, _, _ = make_service(tmp_path)
    reading = service.take_reading()
    assert isinstance(reading, Measurement)
    assert reading.sensor_ok is True
    assert service.latest is reading


def test_sensor_service_status(tmp_path):
    service, _, _ = make_service(tmp_path)
    status = service.status()
    assert status.mode == "simulation"
    assert isinstance(status.connected, bool)


def test_sensor_service_persists_reading(tmp_path):
    service, _, db = make_service(tmp_path)
    service.take_reading()
    assert db.get_measurement_count() >= 1
    latest = db.get_latest()
    assert latest is not None
    assert latest.sensor_ok is True


def test_sensor_service_shutdown_stops_thread(tmp_path):
    service, _, _ = make_service(tmp_path)
    service.start_sampling()
    assert service.is_running()
    service.shutdown()
    assert service.is_running() is False
