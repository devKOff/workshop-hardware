"""Tests for monitor_gui sensor layer (Phase 1)."""

from __future__ import annotations

import math

from monitor_gui.config import DATA_SOURCE_HARDWARE, DATA_SOURCE_SIMULATION
from monitor_gui.sensor import SimulatedSensor, create_sensor, HardwareSensor


def test_simulation_labeled():
    sim = SimulatedSensor(seed=1)
    assert sim.mode == "simulation"
    assert sim.detect() is True
    assert sim.is_available() is True


def test_simulation_sample_fields():
    sim = SimulatedSensor(seed=1)
    s = sim.read_sample(elapsed_s=0.0)
    assert s.data_source == DATA_SOURCE_SIMULATION
    assert s.status == "ok"
    assert s.is_valid
    assert s.voltage_v >= 0
    assert s.current_ma >= 0
    assert s.power_w == s.voltage_v * (s.current_ma / 1000.0)
    # Wall-clock timestamp is ISO 8601.
    from datetime import datetime

    datetime.fromisoformat(s.timestamp)


def test_simulation_power_register_compared_not_primary():
    sim = SimulatedSensor(seed=1)
    s = sim.read_sample(elapsed_s=0.0)
    assert s.power_register_w is not None
    assert s.power_w == s.voltage_v * s.current_a


def test_create_sensor_simulation():
    s = create_sensor(use_hardware=False)
    assert s.mode == "simulation"


def test_create_sensor_hardware():
    s = create_sensor(use_hardware=True)
    assert isinstance(s, HardwareSensor)
    assert s.mode == "hardware"


def test_hardware_sensor_unavailable_without_probe():
    hw = HardwareSensor()
    assert hw.is_available() is False


def test_hardware_detect_returns_false_on_windows_no_ina219():
    hw = HardwareSensor()
    assert hw.detect() is False
    assert hw.is_available() is False


def test_hardware_read_when_unavailable_is_read_error_never_fabricates():
    hw = HardwareSensor()
    s = hw.read_sample(elapsed_s=0.0)
    assert s.data_source == DATA_SOURCE_HARDWARE
    assert s.status == "read_error"
    assert not s.is_valid
    assert s.error is not None
    assert math.isnan(s.voltage_v) and math.isnan(s.current_ma)
