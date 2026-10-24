"""Abstract measurement backend shared by simulation and INA219 hardware."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class SensorReading:
    """A single raw sensor reading.

    ``power_register_w`` is the raw power register (if any); the backend is
    responsible for resolving final power consistently as P = V x I.
    """

    timestamp: datetime
    voltage_v: float
    current_a: float
    power_register_w: float | None
    mode: str
    status: str
    error: str | None = None


class BackendError(RuntimeError):
    """Raised when a backend cannot operate (missing hardware, bad reading)."""


class SensorBackend(ABC):
    """A measurement backend: simulation or genuine INA219 hardware."""

    @property
    @abstractmethod
    def mode(self) -> str:
        """'simulated' or 'hardware'."""

    @abstractmethod
    def read(self) -> SensorReading:
        """Return one validated raw reading."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the backend can produce readings right now."""

    @abstractmethod
    def diagnostics(self) -> dict:
        """Human-readable diagnostic information for the backend."""
