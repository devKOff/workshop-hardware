"""Simulation backend — re-exports from solar_monitor.backends.simulation."""

from __future__ import annotations

from solar_monitor.backends.simulation import (  # noqa: E402
    DEFAULT_BASE_VOLTAGE_V,
    DEFAULT_LOAD_OHM,
    DEFAULT_NOISE_AMPLITUDE_V,
    DEFAULT_SERIES_RESISTANCE_OHM,
    SimulatedSensor,
)

__all__ = [
    "DEFAULT_BASE_VOLTAGE_V",
    "DEFAULT_LOAD_OHM",
    "DEFAULT_NOISE_AMPLITUDE_V",
    "DEFAULT_SERIES_RESISTANCE_OHM",
    "SimulatedSensor",
]
