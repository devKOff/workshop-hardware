"""Tests for monitor_gui sample model and validation (Phase 1)."""

from __future__ import annotations

import math
from datetime import datetime

from monitor_gui.config import (
    DATA_SOURCE_HARDWARE,
    DATA_SOURCE_SIMULATION,
    STATUS_OK,
    STATUS_READ_ERROR,
    STATUS_OVERFLOW,
    STATUS_OUT_OF_RANGE,
    STATUS_REVERSE_CURRENT,
)
from monitor_gui.sample import Sample, now_iso, validate_sample


def test_now_iso_is_timezone_aware_iso8601():
    s = now_iso()
    # Must parse back and carry UTC offset info.
    dt = datetime.fromisoformat(s)
    assert dt.tzinfo is not None


def test_power_is_voltage_times_current():
    s = validate_sample(
        timestamp="2026-01-01T00:00:00+00:00",
        elapsed_s=0.0,
        voltage_v=5.0,
        current_a=0.2,
        power_register_w=None,
        data_source=DATA_SOURCE_SIMULATION,
    )
    assert s.status == STATUS_OK
    assert s.is_valid
    assert s.current_ma == 200.0
    assert s.power_w == 5.0 * 0.2  # 1.0 W


def test_current_a_property_converts_ma():
    s = validate_sample(
        timestamp="2026-01-01T00:00:00+00:00",
        elapsed_s=0.0,
        voltage_v=5.0,
        current_a=0.2,
        power_register_w=None,
        data_source=DATA_SOURCE_SIMULATION,
    )
    assert s.current_a == 0.2


def test_nan_reading_becomes_read_error_not_zero():
    s = validate_sample(
        timestamp="2026-01-01T00:00:00+00:00",
        elapsed_s=0.0,
        voltage_v=float("nan"),
        current_a=float("nan"),
        power_register_w=None,
        data_source=DATA_SOURCE_HARDWARE,
    )
    assert s.status == STATUS_READ_ERROR
    assert not s.is_valid
    assert math.isnan(s.voltage_v)
    assert math.isnan(s.current_ma)
    assert math.isnan(s.power_w)
    assert s.error is not None


def test_reverse_current_beyond_tolerance_is_invalid_kept_not_zero():
    s = validate_sample(
        timestamp="2026-01-01T00:00:00+00:00",
        elapsed_s=0.0,
        voltage_v=5.0,
        current_a=-0.01,  # -10 mA beyond -5 mA tolerance
        power_register_w=None,
        data_source=DATA_SOURCE_SIMULATION,
    )
    assert s.status == STATUS_REVERSE_CURRENT
    assert not s.is_valid
    # Measured value kept, never replaced with 0.
    assert s.current_ma == -10.0


def test_small_reverse_current_within_tolerance_is_ok():
    s = validate_sample(
        timestamp="2026-01-01T00:00:00+00:00",
        elapsed_s=0.0,
        voltage_v=5.0,
        current_a=-0.002,  # -2 mA within -5 mA tolerance
        power_register_w=None,
        data_source=DATA_SOURCE_SIMULATION,
    )
    assert s.status == STATUS_OK
    assert s.is_valid


def test_overflow_flag_marks_invalid():
    s = validate_sample(
        timestamp="2026-01-01T00:00:00+00:00",
        elapsed_s=0.0,
        voltage_v=5.0,
        current_a=0.2,
        power_register_w=None,
        data_source=DATA_SOURCE_HARDWARE,
        overflow=True,
    )
    assert s.status == STATUS_OVERFLOW
    assert not s.is_valid


def test_out_of_range_voltage_marks_invalid_kept_not_zero():
    s = validate_sample(
        timestamp="2026-01-01T00:00:00+00:00",
        elapsed_s=0.0,
        voltage_v=50.0,
        current_a=0.2,
        power_register_w=None,
        data_source=DATA_SOURCE_SIMULATION,
    )
    assert s.status == STATUS_OUT_OF_RANGE
    assert not s.is_valid
    assert s.voltage_v == 50.0  # kept, not replaced with 0


def test_invalid_samples_excluded_by_is_valid():
    ok = validate_sample(
        timestamp="2026-01-01T00:00:00+00:00", elapsed_s=0.0,
        voltage_v=5.0, current_a=0.2, power_register_w=None,
        data_source=DATA_SOURCE_SIMULATION,
    )
    bad = validate_sample(
        timestamp="2026-01-01T00:00:00+00:00", elapsed_s=1.0,
        voltage_v=float("nan"), current_a=float("nan"),
        power_register_w=None, data_source=DATA_SOURCE_SIMULATION,
    )
    assert ok.is_valid and not bad.is_valid
