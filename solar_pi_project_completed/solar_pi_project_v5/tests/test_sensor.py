"""Tests for the sensor layer."""

import math
import sys
from unittest.mock import MagicMock, patch

import pytest

import sensor


def test_validate_reading_ok():
    r = sensor.validate_reading(bus_voltage_v=5.4, shunt_voltage_v=0.02, current_ma=200.0)
    assert r.status == "ok"
    assert r.data_source == "hardware"
    assert r.voltage_v == pytest.approx(5.42)
    assert r.current_ma == 200.0
    assert r.power_w == pytest.approx(5.42 * 0.2)


def test_validate_reading_power_is_v_times_i():
    r = sensor.validate_reading(bus_voltage_v=5.0, shunt_voltage_v=0.0, current_ma=1000.0)
    assert r.power_w == pytest.approx(5.0 * 1.0)


def test_validate_reading_nan():
    with pytest.raises(sensor.ValidationError):
        sensor.validate_reading(bus_voltage_v=float("nan"), shunt_voltage_v=0.0, current_ma=100.0)
    with pytest.raises(sensor.ValidationError):
        sensor.validate_reading(bus_voltage_v=5.0, shunt_voltage_v=float("nan"), current_ma=100.0)
    with pytest.raises(sensor.ValidationError):
        sensor.validate_reading(bus_voltage_v=5.0, shunt_voltage_v=0.0, current_ma=float("nan"))


def test_validate_reading_inf():
    with pytest.raises(sensor.ValidationError):
        sensor.validate_reading(bus_voltage_v=float("inf"), shunt_voltage_v=0.0, current_ma=100.0)
    with pytest.raises(sensor.ValidationError):
        sensor.validate_reading(bus_voltage_v=5.0, shunt_voltage_v=0.0, current_ma=float("-inf"))


def test_validate_reading_overflow():
    with pytest.raises(sensor.OverflowError):
        sensor.validate_reading(
            bus_voltage_v=5.0, shunt_voltage_v=0.0, current_ma=100.0, overflow=True
        )


def test_validate_reading_out_of_range_bus():
    with pytest.raises(sensor.OutOfRangeError):
        sensor.validate_reading(
            bus_voltage_v=40.0, shunt_voltage_v=0.0, current_ma=100.0
        )


def test_validate_reading_out_of_range_current():
    with pytest.raises(sensor.OutOfRangeError):
        sensor.validate_reading(
            bus_voltage_v=5.0, shunt_voltage_v=0.5, current_ma=5000.0
        )


def test_invalid_readings_never_zero():
    # None of the invalid cases may silently become 0; they all raise.
    bad_inputs = [
        (float("nan"), 0.0, 100.0),
        (5.0, float("nan"), 100.0),
        (5.0, 0.0, float("nan")),
        (float("inf"), 0.0, 100.0),
        (40.0, 0.0, 100.0),
        (5.0, 0.0, 5000.0),
    ]
    for bus, shunt, cur in bad_inputs:
        with pytest.raises(sensor.ValidationError):
            sensor.validate_reading(bus_voltage_v=bus, shunt_voltage_v=shunt, current_ma=cur)


def test_simulated_sensor_plausible_and_labeled():
    sim = sensor.SimulatedSensor(seed=42)
    assert sim.detect()
    assert sim.data_source == "simulation"
    for _ in range(50):
        raw = sim.read_raw()
        assert 0.0 <= raw["bus_voltage_v"] <= 32.0
        assert 0.0 <= raw["current_ma"] <= 2000.0
        assert raw["overflow"] is False
        assert math.isfinite(raw["bus_voltage_v"])
        assert math.isfinite(raw["current_ma"])
    sim.close()


def test_simulated_sensor_label_propagates_through_validation():
    sim = sensor.SimulatedSensor(seed=1)
    raw = sim.read_raw()
    r = sensor.validate_reading(
        bus_voltage_v=raw["bus_voltage_v"],
        shunt_voltage_v=raw["shunt_voltage_v"],
        current_ma=raw["current_ma"],
        overflow=raw["overflow"],
    )
    assert r.status == "ok"
    assert r.data_source == "hardware"  # validate_reading itself doesn't set source
    sim.close()


def test_hardware_sensor_detect_success(monkeypatch):
    fake_ina = MagicMock()
    fake_ina.bus_voltage = 5.0
    fake_i2c = MagicMock()

    def fake_import(name, *args, **kwargs):
        if name == "adafruit_ina219":
            mod = MagicMock()
            mod.INA219.return_value = fake_ina
            return mod
        return MagicMock()

    with patch.dict(sys.modules, {"board": MagicMock(), "busio": MagicMock()}):
        with patch("builtins.__import__", side_effect=fake_import):
            s = sensor.INA219HardwareSensor(i2c_address=0x40)
            assert s.detect() is True
            assert s.data_source == "hardware"


def test_hardware_sensor_detect_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("I2C bus not available")

    with patch("builtins.__import__", side_effect=boom):
        s = sensor.INA219HardwareSensor(i2c_address=0x40)
        assert s.detect() is False
        assert s._ina is None


def test_make_sensor_unknown_mode():
    with pytest.raises(ValueError):
        sensor.make_sensor("nonsense")
