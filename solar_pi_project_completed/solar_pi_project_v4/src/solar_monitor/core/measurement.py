"""Measurement model: a validated, storable snapshot of solar performance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Measurement:
    timestamp: str
    voltage_v: float
    current_ma: float
    current_a: float
    power_w: float
    sensor_mode: str
    sensor_status: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_display_row(m: Measurement) -> tuple:
    return (
        m.timestamp,
        m.voltage_v,
        m.current_ma,
        m.current_a,
        m.power_w,
        m.sensor_mode,
        m.sensor_status,
    )
