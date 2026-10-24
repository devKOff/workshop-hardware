"""Application configuration defaults — re-exports from solar_monitor.core.config."""

from __future__ import annotations

from solar_monitor.core.config import (  # noqa: E402
    DB_DEFAULT_NAME,
    SCHEMA_VERSION,
    SAMPLING_INTERVAL_SECONDS,
    SENSOR_MODE_HARDWARE,
    SENSOR_MODE_SIMULATED,
)

__all__ = [
    "SAMPLING_INTERVAL_SECONDS",
    "SENSOR_MODE_SIMULATED",
    "SENSOR_MODE_HARDWARE",
    "DB_DEFAULT_NAME",
    "SCHEMA_VERSION",
]
