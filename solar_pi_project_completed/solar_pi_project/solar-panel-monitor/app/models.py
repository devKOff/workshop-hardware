"""Data models for the Solar Panel Performance Monitor."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Measurement:
    """A single instantaneous sensor reading."""

    timestamp: datetime
    voltage_v: float
    current_ma: float
    current_a: float
    power_w: float
    shunt_voltage_mv: Optional[float] = None
    bus_voltage_v: Optional[float] = None
    load_voltage_v: Optional[float] = None
    sensor_ok: bool = True
    error_message: Optional[str] = None

    @property
    def current_amps(self) -> float:
        """Alias for current_a."""
        return self.current_a

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "voltage_v": round(self.voltage_v, 4),
            "current_ma": round(self.current_ma, 2),
            "current_a": round(self.current_a, 4),
            "power_w": round(self.power_w, 4),
            "shunt_voltage_mv": (
                None if self.shunt_voltage_mv is None else round(self.shunt_voltage_mv, 3)
            ),
            "bus_voltage_v": (
                None if self.bus_voltage_v is None else round(self.bus_voltage_v, 4)
            ),
            "load_voltage_v": (
                None if self.load_voltage_v is None else round(self.load_voltage_v, 4)
            ),
            "sensor_ok": self.sensor_ok,
            "error_message": self.error_message,
        }


@dataclass
class EnergySummary:
    """Aggregated energy statistics over a period."""

    period_start: datetime
    period_end: datetime
    total_energy_wh: float
    avg_power_w: float
    min_power_w: float
    max_power_w: float
    sample_count: int
    duration_hours: float

    def to_dict(self) -> dict:
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_energy_wh": round(self.total_energy_wh, 4),
            "avg_power_w": round(self.avg_power_w, 4),
            "min_power_w": round(self.min_power_w, 4),
            "max_power_w": round(self.max_power_w, 4),
            "sample_count": self.sample_count,
            "duration_hours": round(self.duration_hours, 4),
        }


@dataclass
class DailyEnergy:
    """Energy generated on a single calendar day."""

    date: str  # ISO date YYYY-MM-DD
    energy_wh: float
    min_power_w: Optional[float] = None
    max_power_w: Optional[float] = None
    avg_power_w: Optional[float] = None
    sample_count: int = 0

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "energy_wh": round(self.energy_wh, 4),
            "min_power_w": None if self.min_power_w is None else round(self.min_power_w, 4),
            "max_power_w": None if self.max_power_w is None else round(self.max_power_w, 4),
            "avg_power_w": None if self.avg_power_w is None else round(self.avg_power_w, 4),
            "sample_count": self.sample_count,
        }


@dataclass
class SensorStatus:
    """Status of the underlying sensor."""

    connected: bool
    mode: str  # "simulation" or "hardware"
    error_message: Optional[str] = None
    last_reading_ts: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "connected": self.connected,
            "mode": self.mode,
            "error_message": self.error_message,
            "last_reading_ts": self.last_reading_ts,
        }
