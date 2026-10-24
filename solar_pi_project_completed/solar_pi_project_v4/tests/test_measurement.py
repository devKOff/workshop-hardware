"""Tests for the measurement model, validation and power selection."""
from __future__ import annotations

import math
import pytest

from measurement.model import Measurement
from measurement.power import compute_power
from measurement.validation import validate_reading


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