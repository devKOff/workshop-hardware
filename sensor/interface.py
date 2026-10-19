"""Abstract sensor interface shared by simulation and INA219 backends."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SensorReading:
    timestamp: datetime
    voltage_v: float
    current_a: float
    power_register_w: float | None
    mode: str
    status: str
    error: str | None = None


class Sensor(ABC):
    @property
    @abstractmethod
    def mode(self):
        raise NotImplementedError

    @abstractmethod
    def read(self):
        raise NotImplementedError

    @abstractmethod
    def is_available(self):
        raise NotImplementedError