"""Measurement backends: interface, simulation, and INA219 hardware."""

from __future__ import annotations

from solar_monitor.backends.hardware import INA219HardwareBackend
from solar_monitor.backends.interface import BackendError, SensorBackend, SensorReading
from solar_monitor.backends.simulation import SimulatedSensor

__all__ = [
    "BackendError",
    "SensorBackend",
    "SensorReading",
    "SimulatedSensor",
    "INA219HardwareBackend",
]
