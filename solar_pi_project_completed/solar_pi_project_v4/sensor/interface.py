"""Abstract sensor interface — re-exports from solar_monitor.backends.interface."""

from __future__ import annotations

from solar_monitor.backends.interface import (  # noqa: E402
    BackendError,
    SensorBackend,
    SensorReading,
)

__all__ = ["BackendError", "SensorBackend", "SensorReading"]
