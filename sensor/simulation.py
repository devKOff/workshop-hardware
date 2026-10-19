"""Simulation backend: sunlight trend + noise, no Pi imports."""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone

from sensor.interface import Sensor, SensorReading

DEFAULT_BASE_VOLTAGE_V = 5.5
DEFAULT_LOAD_OHM = 33.0
DEFAULT_NOISE_AMPLITUDE_V = 0.05


class SimulatedSensor(Sensor):
    def __init__(self, *, base_voltage_v=DEFAULT_BASE_VOLTAGE_V, load_ohm=DEFAULT_LOAD_OHM,
                 noise_amplitude_v=DEFAULT_NOISE_AMPLITUDE_V, fault=False):
        self._base_voltage_v = base_voltage_v
        self._load_ohm = load_ohm
        self._noise_amplitude_v = noise_amplitude_v
        self._fault = fault
        self._started_at = datetime.now(timezone.utc)
        self._rng = random.Random()

    @property
    def mode(self):
        return "simulated"

    def is_available(self):
        return True

    def read(self):
        now = datetime.now(timezone.utc)
        elapsed = (now - self._started_at).total_seconds()
        sunlight = max(0.0, math.sin(2.0 * math.pi * (elapsed / 86400.0) - math.pi / 2.0))
        if self._fault:
            return SensorReading(
                timestamp=now, voltage_v=float("nan"), current_a=float("nan"),
                power_register_w=None, mode=self.mode, status="fault",
                error="simulated sensor fault",
            )
        panel_v = self._base_voltage_v * sunlight
        current_a = panel_v / (self._load_ohm + 0.1)
        voltage_v = min(max(current_a * self._load_ohm, 0.0), self._base_voltage_v)
        current_a = min(max(current_a, 0.0), self._base_voltage_v / self._load_ohm)
        voltage_v += self._rng.uniform(-self._noise_amplitude_v, self._noise_amplitude_v)
        voltage_v = min(max(voltage_v, 0.0), self._base_voltage_v)
        return SensorReading(
            timestamp=now, voltage_v=voltage_v, current_a=current_a,
            power_register_w=voltage_v * current_a, mode=self.mode, status="ok", error=None,
        )