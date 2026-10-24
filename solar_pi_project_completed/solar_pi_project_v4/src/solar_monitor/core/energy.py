"""Energy integration: trapezoidal rule with gap handling."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

SECONDS_PER_HOUR = 3600.0


@dataclass
class IntegrationState:
    total_energy_wh: float = 0.0
    daily_energy_wh: float = 0.0
    last_timestamp: str | None = None
    last_power_w: float | None = None
    last_day: str | None = None
    gaps_skipped: int = 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            total_energy_wh=float(data.get("total_energy_wh", 0.0)),
            daily_energy_wh=float(data.get("daily_energy_wh", 0.0)),
            last_timestamp=data.get("last_timestamp"),
            last_power_w=data.get("last_power_w"),
            last_day=data.get("last_day"),
            gaps_skipped=int(data.get("gaps_skipped", 0)),
        )


class EnergyIntegrator:
    def __init__(self, *, sampling_interval_s, max_gap_multiplier=5.0, state=None):
        self._sampling_interval_s = sampling_interval_s
        self._max_gap_s = max_gap_multiplier * sampling_interval_s
        self._state = state or IntegrationState()

    @property
    def max_gap_s(self):
        return self._max_gap_s

    @property
    def state(self):
        return self._state

    def add(self, timestamp_iso, power_w):
        now = self._parse(timestamp_iso)
        if now is None:
            return None
        if not _is_finite_power(power_w):
            self._state.last_timestamp = None
            self._state.last_power_w = None
            return None
        day = now.strftime("%Y-%m-%d")
        if self._state.last_day is not None and day != self._state.last_day:
            self._state.daily_energy_wh = 0.0
        self._state.last_day = day
        if self._state.last_timestamp is None or self._state.last_power_w is None:
            self._state.last_timestamp = timestamp_iso
            self._state.last_power_w = power_w
            return None
        prev = self._parse(self._state.last_timestamp)
        if prev is None:
            self._state.last_timestamp = timestamp_iso
            self._state.last_power_w = power_w
            return None
        delta_s = (now - prev).total_seconds()
        if delta_s < 0:
            self._state.last_timestamp = timestamp_iso
            self._state.last_power_w = power_w
            return None
        if delta_s > self._max_gap_s:
            self._state.gaps_skipped += 1
            self._state.last_timestamp = timestamp_iso
            self._state.last_power_w = power_w
            return None
        avg_power_w = (self._state.last_power_w + power_w) / 2.0
        increment_wh = avg_power_w * (delta_s / SECONDS_PER_HOUR)
        if increment_wh < 0:
            increment_wh = 0.0
        self._state.total_energy_wh += increment_wh
        self._state.daily_energy_wh += increment_wh
        self._state.last_timestamp = timestamp_iso
        self._state.last_power_w = power_w
        return increment_wh

    def reset(self):
        self._state = IntegrationState()

    def set_state(self, state):
        self._state = state

    @staticmethod
    def _parse(iso):
        if not iso:
            return None
        try:
            return datetime.fromisoformat(iso)
        except ValueError:
            return None


def _is_finite_power(power_w):
    return power_w is not None and power_w == power_w and abs(power_w) != float("inf")
