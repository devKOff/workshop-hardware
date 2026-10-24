"""Power source selection: INA219 register only if consistent with V x I."""

from __future__ import annotations

from solar_monitor.core.measurement import Measurement

REGISTER_TOLERANCE = 0.10


def compute_power(voltage_v, current_a, power_register_w):
    """Return the register power when consistent with V x I, else V x I.

    Power is always calculated consistently as P = V x I. The INA219 power
    register is used only when it agrees with V x I within tolerance.
    """
    v_times_i = voltage_v * current_a
    if power_register_w is not None and _register_consistent(v_times_i, power_register_w):
        return power_register_w
    return v_times_i


def _register_consistent(v_times_i, register_w):
    if register_w < 0:
        return False
    if v_times_i == 0:
        return register_w == 0
    return abs(register_w - v_times_i) <= REGISTER_TOLERANCE * abs(v_times_i)


def attach_power(m, power_register_w):
    """Return a copy of m with power_w resolved via compute_power."""
    power_w = compute_power(m.voltage_v, m.current_a, power_register_w)
    return Measurement(
        timestamp=m.timestamp,
        voltage_v=m.voltage_v,
        current_ma=m.current_ma,
        current_a=m.current_a,
        power_w=power_w,
        sensor_mode=m.sensor_mode,
        sensor_status=m.sensor_status,
    )
