"""Validation: reject NaN, inf and impossible values."""

from __future__ import annotations

import math

from solar_monitor.core.measurement import Measurement, now_iso

MAX_VOLTAGE_V = 30.0
MAX_CURRENT_A = 10.0
MAX_POWER_W = 60.0


def validate_reading(voltage_v, current_a, power_w, *, mode, status="ok"):
    """Validate a raw sensor reading and return a Measurement.

    Fault-mode readings bypass the finite/impossible checks so an offline
    sensor can still be recorded (labeled 'fault'), never fabricated as 'ok'.
    """
    if status == "fault":
        return _build(voltage_v, current_a, power_w, mode, status)
    _reject_non_finite(voltage_v, current_a, power_w)
    _reject_impossible(voltage_v, current_a, power_w)
    return _build(voltage_v, current_a, power_w, mode, status)


def _reject_non_finite(voltage_v, current_a, power_w):
    for name, value in (("voltage", voltage_v), ("current", current_a), ("power", power_w)):
        if not math.isfinite(value):
            raise ValueError(f"{name} is not finite: {value!r}")


def _reject_impossible(voltage_v, current_a, power_w):
    if voltage_v < 0 or voltage_v > MAX_VOLTAGE_V:
        raise ValueError(f"voltage {voltage_v} V outside [0, {MAX_VOLTAGE_V}]")
    if abs(current_a) > MAX_CURRENT_A:
        raise ValueError(f"current {current_a} A outside [-{MAX_CURRENT_A}, {MAX_CURRENT_A}]")
    if power_w < 0 or power_w > MAX_POWER_W:
        raise ValueError(f"power {power_w} W outside [0, {MAX_POWER_W}]")


def _build(voltage_v, current_a, power_w, mode, status):
    return Measurement(
        timestamp=now_iso(),
        voltage_v=voltage_v,
        current_ma=current_a * 1000.0,
        current_a=current_a,
        power_w=power_w,
        sensor_mode=mode,
        sensor_status=status,
    )
