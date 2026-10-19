"""Tests for src/solar_monitor/core measurement models, power, validation, energy."""

from __future__ import annotations

import math

import pytest

from solar_monitor.core.energy import EnergyIntegrator, IntegrationState
from solar_monitor.core.measurement import Measurement, now_iso, to_display_row
from solar_monitor.core.power import REGISTER_TOLERANCE, attach_power, compute_power
from solar_monitor.core.validation import validate_reading


def test_valid_measurement():
    m = validate_reading(5.0, 0.1, 0.5, mode="simulated", status="ok")
    assert m.current_ma == 100.0
    assert m.sensor_mode == "simulated"
    assert m.sensor_status == "ok"


def test_rejects_nan():
    with pytest.raises(ValueError):
        validate_reading(float("nan"), 0.1, 0.5, mode="simulated")


def test_rejects_inf():
    with pytest.raises(ValueError):
        validate_reading(5.0, float("inf"), 0.5, mode="simulated")


def test_rejects_negative_voltage():
    with pytest.raises(ValueError):
        validate_reading(-1.0, 0.1, 0.0, mode="simulated")


def test_rejects_over_range_power():
    with pytest.raises(ValueError):
        validate_reading(5.0, 0.1, 999.0, mode="simulated")


def test_fault_mode_allowed():
    m = validate_reading(float("nan"), float("nan"), float("nan"), mode="simulated", status="fault")
    assert m.sensor_status == "fault"
    assert m.sensor_mode == "simulated"


def test_power_uses_register_when_consistent():
    assert compute_power(5.0, 0.1, 0.5) == 0.5


def test_power_falls_back_when_register_inconsistent():
    assert compute_power(5.0, 0.1, 50.0) == 0.5


def test_power_none_falls_back_to_v_times_i():
    assert compute_power(5.0, 0.2, None) == 1.0


def test_power_negative_register_falls_back():
    assert compute_power(5.0, 0.1, -1.0) == 0.5


def test_register_tolerance_constant():
    assert REGISTER_TOLERANCE == 0.10


def test_attach_power_returns_measurement():
    m = Measurement("t", 5.0, 100.0, 0.1, 0.5, "simulated", "ok")
    out = attach_power(m, 0.5)
    assert isinstance(out, Measurement)
    assert out.power_w == 0.5


def test_now_iso_returns_string():
    s = now_iso()
    assert isinstance(s, str)
    assert "+00:00" in s or s.endswith("Z")


def test_to_display_row():
    m = Measurement("2026-01-01T00:00:00+00:00", 5.0, 100.0, 0.1, 0.5, "simulated", "ok")
    assert to_display_row(m) == (
        "2026-01-01T00:00:00+00:00",
        5.0,
        100.0,
        0.1,
        0.5,
        "simulated",
        "ok",
    )


def test_energy_integrator_known_sequence():
    integrator = EnergyIntegrator(sampling_interval_s=1.0)
    assert integrator.add("2026-01-01T00:00:00+00:00", 1.0) is None
    inc = integrator.add("2026-01-01T00:00:01+00:00", 3.0)
    assert inc is not None
    assert abs(inc - (2.0 / 3600.0)) < 1e-9


def test_invalid_power_never_accumulates():
    integrator = EnergyIntegrator(sampling_interval_s=1.0)
    integrator.add("2026-01-01T00:00:00+00:00", 10.0)
    assert integrator.add("2026-01-01T00:00:01+00:00", float("nan")) is None
    assert integrator.state.total_energy_wh == 0.0
    # chain broken; next valid sample restarts without accumulating
    inc = integrator.add("2026-01-01T00:00:02+00:00", 10.0)
    assert inc is None


def test_core_imports_without_pi():
    """src/solar_monitor/core must not import Pi-specific modules."""
    import solar_monitor.core.measurement as m
    import solar_monitor.core.power as p
    import solar_monitor.core.validation as v
    import solar_monitor.core.energy as e

    for mod in (m, p, v, e):
        text = open(mod.__file__, encoding="utf-8").read()
        for forbidden in ("board", "busio", "adafruit", "rpi", "gpiozero", "smbus"):
            assert forbidden not in text.lower(), f"forbidden {forbidden} in {mod.__file__}"
