"""Sample model and per-sample validation.

A :class:`Sample` is one validated measurement. Invalid samples are kept in the
dataset with an error status and are **never** replaced with 0 and **never**
enter statistics or energy. Power is always calculated by us as
``power_w = voltage_v * current_a`` (current in amps).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .config import (
    STATUS_OK,
    STATUS_READ_ERROR,
    STATUS_OVERFLOW,
    STATUS_OUT_OF_RANGE,
    STATUS_REVERSE_CURRENT,
    REVERSE_CURRENT_TOLERANCE_MA,
    MAX_VOLTAGE_V,
    MAX_CURRENT_A,
    MAX_POWER_W,
    DATA_SOURCE_HARDWARE,
    DATA_SOURCE_SIMULATION,
)


@dataclass(frozen=True)
class Sample:
    """A single validated measurement.

    Attributes:
        timestamp: wall-clock ISO 8601, timezone-aware (labels the sample).
        elapsed_s: monotonic seconds since session start (schedules/durations).
        voltage_v: bus/panel voltage in volts.
        current_ma: current in milliamperes.
        power_w: ``voltage_v * (current_ma / 1000)`` — calculated by us.
        status: ``ok`` | ``read_error`` | ``overflow`` | ``out_of_range`` |
            ``reverse_current``. Only ``ok`` counts as valid.
        data_source: ``hardware`` | ``simulation``.
        error: human-readable reason when status != ``ok``.
        power_register_w: library's own power register value, if available
            (compared, not used as primary).
    """

    timestamp: str
    elapsed_s: float
    voltage_v: float
    current_ma: float
    power_w: float
    status: str
    data_source: str
    error: Optional[str] = None
    power_register_w: Optional[float] = None

    @property
    def current_a(self) -> float:
        return self.current_ma / 1000.0

    @property
    def is_valid(self) -> bool:
        return self.status == STATUS_OK


def now_iso() -> str:
    """Current wall-clock time as a timezone-aware ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def validate_sample(
    *,
    timestamp: str,
    elapsed_s: float,
    voltage_v: float,
    current_a: float,
    power_register_w: Optional[float],
    data_source: str,
    overflow: bool = False,
) -> Sample:
    """Turn a raw backend reading into a validated :class:`Sample`.

    Never fabricates: invalid readings keep their measured values (never 0) and
    an error status. Consumers exclude them via :attr:`Sample.is_valid`.
    """
    current_ma = current_a * 1000.0
    power_w = voltage_v * current_a

    # Non-finite / unreadable reading.
    if not (
        math.isfinite(voltage_v)
        and math.isfinite(current_a)
        and math.isfinite(power_w)
    ):
        return Sample(
            timestamp=timestamp,
            elapsed_s=elapsed_s,
            voltage_v=float("nan"),
            current_ma=float("nan"),
            power_w=float("nan"),
            status=STATUS_READ_ERROR,
            data_source=data_source,
            error="non-finite INA219 reading",
            power_register_w=power_register_w,
        )

    # INA219 overflow flag.
    if overflow:
        return Sample(
            timestamp=timestamp,
            elapsed_s=elapsed_s,
            voltage_v=voltage_v,
            current_ma=current_ma,
            power_w=power_w,
            status=STATUS_OVERFLOW,
            data_source=data_source,
            error="INA219 overflow flag",
            power_register_w=power_register_w,
        )

    # Out of configured sensor range.
    if not (0.0 <= voltage_v <= MAX_VOLTAGE_V):
        return Sample(
            timestamp=timestamp,
            elapsed_s=elapsed_s,
            voltage_v=voltage_v,
            current_ma=current_ma,
            power_w=power_w,
            status=STATUS_OUT_OF_RANGE,
            data_source=data_source,
            error=f"voltage {voltage_v} V outside [0, {MAX_VOLTAGE_V}]",
            power_register_w=power_register_w,
        )
    if not (-MAX_CURRENT_A <= current_a <= MAX_CURRENT_A):
        return Sample(
            timestamp=timestamp,
            elapsed_s=elapsed_s,
            voltage_v=voltage_v,
            current_ma=current_ma,
            power_w=power_w,
            status=STATUS_OUT_OF_RANGE,
            data_source=data_source,
            error=f"current {current_a} A outside [{-MAX_CURRENT_A}, {MAX_CURRENT_A}]",
            power_register_w=power_register_w,
        )

    # Reverse current beyond the configurable tolerance (default -5 mA).
    # Checked before the power magnitude bound so a small reverse current
    # (which makes V x I slightly negative) is classified correctly.
    if current_ma < REVERSE_CURRENT_TOLERANCE_MA:
        return Sample(
            timestamp=timestamp,
            elapsed_s=elapsed_s,
            voltage_v=voltage_v,
            current_ma=current_ma,
            power_w=power_w,
            status=STATUS_REVERSE_CURRENT,
            data_source=data_source,
            error=f"reverse current {current_ma:.3f} mA",
            power_register_w=power_register_w,
        )

    # Power magnitude bound (allows small negative power from reverse current
    # within tolerance, rejects physically impossible power).
    if abs(power_w) > MAX_POWER_W:
        return Sample(
            timestamp=timestamp,
            elapsed_s=elapsed_s,
            voltage_v=voltage_v,
            current_ma=current_ma,
            power_w=power_w,
            status=STATUS_OUT_OF_RANGE,
            data_source=data_source,
            error=f"power {power_w} W outside [{-MAX_POWER_W}, {MAX_POWER_W}]",
            power_register_w=power_register_w,
        )

    return Sample(
        timestamp=timestamp,
        elapsed_s=elapsed_s,
        voltage_v=voltage_v,
        current_ma=current_ma,
        power_w=power_w,
        status=STATUS_OK,
        data_source=data_source,
        error=None,
        power_register_w=power_register_w,
    )
