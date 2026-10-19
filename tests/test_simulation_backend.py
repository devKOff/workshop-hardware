"""Tests for src/solar_monitor/backends simulation (deterministic scenarios)."""

from __future__ import annotations

import math

import pytest

from solar_monitor.backends import BackendError, INA219HardwareBackend, SimulatedSensor
from solar_monitor.backends.simulation import (
    DEFAULT_BASE_VOLTAGE_V,
    DEFAULT_LOAD_OHM,
    DEFAULT_NOISE_AMPLITUDE_V,
)


def test_simulation_mode_and_available():
    sim = SimulatedSensor()
    assert sim.mode == "simulated"
    assert sim.is_available() is True


def test_reading_physically_plausible():
    sim = SimulatedSensor(seed=1, noise_amplitude_v=0.0)
    for _ in range(200):
        r = sim.read()
        assert r.mode == "simulated"
        assert r.status == "ok"
        assert r.error is None
        assert r.voltage_v >= 0.0
        assert r.current_a >= 0.0
        assert r.power_register_w is not None
        assert r.power_register_w >= 0.0
        # Power consistent as P = V x I (no register inconsistency in sim).
        assert abs(r.power_register_w - r.voltage_v * r.current_a) < 1e-9
        # Voltage bounded by panel base voltage.
        assert r.voltage_v <= DEFAULT_BASE_VOLTAGE_V + 1e-9
        # Current bounded by panel into the load.
        assert r.current_a <= DEFAULT_BASE_VOLTAGE_V / DEFAULT_LOAD_OHM + 1e-9


def test_voltage_within_noise_band():
    sim = SimulatedSensor(seed=2, noise_amplitude_v=DEFAULT_NOISE_AMPLITUDE_V)
    readings = [sim.read() for _ in range(50)]
    # At least some readings should differ (noise active).
    voltages = [r.voltage_v for r in readings]
    assert max(voltages) - min(voltages) > 0 or len(set(voltages)) > 1


def test_night_approaches_zero():
    # SimulatedSensor irradiance envelope → far-future timestamps read near zero
    # is not directly controllable; instead verify low-irradiance construction
    # yields low values via a small base voltage / high load.
    sim = SimulatedSensor(seed=3, base_voltage_v=0.1, load_ohm=1000.0)
    for _ in range(50):
        r = sim.read()
        assert r.voltage_v < 1.0  # low-light → very low voltage


def test_fault_mode():
    sim = SimulatedSensor(seed=4, fault=True)
    r = sim.read()
    assert r.status == "fault"
    assert r.error is not None
    assert math.isnan(r.voltage_v)
    assert math.isnan(r.current_a)


def test_fault_after_seconds_transitions():
    import time

    sim = SimulatedSensor(seed=5, fault_after_seconds=0)
    # Force elapsed time past the threshold by monkeypatching started_at.
    from datetime import datetime, timezone

    sim._started_at = datetime.now(timezone.utc)  # noqa: SLF001
    r = sim.read()
    assert r.status == "fault"


def test_deterministic_with_seed():
    a = SimulatedSensor(seed=42)
    b = SimulatedSensor(seed=42)
    ra = [a.read() for _ in range(10)]
    rb = [b.read() for _ in range(10)]
    for x, y in zip(ra, rb):
        assert x.voltage_v == y.voltage_v
        assert x.current_a == y.current_a


def test_no_pi_imports_in_simulation():
    import solar_monitor.backends.simulation as mod

    text = open(mod.__file__, encoding="utf-8").read()
    for forbidden in ("board", "busio", "adafruit", "rpi", "gpiozero", "smbus"):
        assert forbidden not in text.lower(), f"forbidden {forbidden} in simulation backend"


def test_hardware_backend_unavailable_on_windows_without_pi():
    """On this Windows dev machine the INA219 hardware backend must report
    unavailable and raise an honest error instead of fabricating readings."""
    backend = INA219HardwareBackend()
    diag = backend.diagnostics()
    assert diag["mode"] == "hardware"
    assert diag["hardware"] is True
    assert diag["simulated"] is False
    assert diag["available"] is False
    assert diag["init_error"] is not None
    with pytest.raises(BackendError):
        backend.read()
