"""Simulated INA219 sensor for development and testing on Windows.

Produces a realistic solar-panel curve (daytime bell-shaped power, zero at
night) with optional noise. Fully deterministic when a fixed ``clock`` or
``seed`` is supplied, which makes it suitable for automated tests.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from app.models import Measurement


class SimulatedSensorError(RuntimeError):
    """Raised when the simulated sensor cannot produce a reading."""


class SimulatedSensor:
    """Software-only stand-in for the INA219 sensor.

    Parameters
    ----------
    peak_power_w:
        Maximum instantaneous power around solar noon (watts).
    voltage_v:
        Nominal panel/bus voltage (volts). Current is derived as power/voltage.
    sunrise_hour / sunset_hour:
        Hours of the day (0-24) between which the panel produces power.
    noise:
        Standard deviation of Gaussian noise applied to power (watts). Set to
        0 for deterministic readings.
    clock:
        Callable returning the current ``datetime``. Defaults to local now.
        Pass a fixed function for deterministic tests.
    seed:
        Optional RNG seed for reproducible noise.
    min_power_w:
        Floor below which power is clamped to 0 (night / cloud cover).
    """

    def __init__(
        self,
        *,
        peak_power_w: float = 3.0,
        voltage_v: float = 6.0,
        sunrise_hour: float = 6.0,
        sunset_hour: float = 18.0,
        noise: float = 0.05,
        clock: Optional[Callable[[], datetime]] = None,
        seed: Optional[int] = None,
        min_power_w: float = 0.0,
    ) -> None:
        if peak_power_w <= 0:
            raise ValueError("peak_power_w must be positive")
        if voltage_v <= 0:
            raise ValueError("voltage_v must be positive")
        if not (0 <= sunrise_hour < sunset_hour <= 24):
            raise ValueError("require 0 <= sunrise_hour < sunset_hour <= 24")

        self.peak_power_w = peak_power_w
        self.voltage_v = voltage_v
        self.sunrise_hour = sunrise_hour
        self.sunset_hour = sunset_hour
        self.noise = noise
        self.clock = clock or (lambda: datetime.now())
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self.min_power_w = min_power_w
        self.connected = True
        self.mode = "simulation"
        self.last_error: Optional[str] = None

    def _daylight_factor(self, when: datetime) -> float:
        """Return a 0..1 factor for the solar curve at the given time."""
        hour = when.hour + when.minute / 60.0 + when.second / 3600.0
        if hour < self.sunrise_hour or hour >= self.sunset_hour:
            return 0.0
        day_length = self.sunset_hour - self.sunrise_hour
        # Bell curve centered at solar noon, zero at sunrise/sunset.
        progress = (hour - self.sunrise_hour) / day_length
        return math.sin(math.pi * progress)

    def read(self) -> Measurement:
        """Return a simulated :class:`Measurement` for the current time."""
        try:
            when = self.clock()
            factor = self._daylight_factor(when)
            power_w = self.peak_power_w * factor
            if self.noise > 0:
                power_w += self._rng.gauss(0, self.noise)
            power_w = max(self.min_power_w, power_w)

            current_a = power_w / self.voltage_v
            current_ma = current_a * 1000.0

            # Shunt voltage: V = I * R_shunt. Use a nominal 0.1 ohm shunt.
            shunt_ohms = 0.1
            shunt_voltage_mv = current_a * shunt_ohms * 1000.0

            # Small variations around the nominal voltage.
            bus_voltage_v = self.voltage_v + self._rng.uniform(-0.05, 0.05)
            load_voltage_v = bus_voltage_v - (shunt_voltage_mv / 1000.0)

            self.last_error = None
            return Measurement(
                timestamp=when,
                voltage_v=round(bus_voltage_v, 4),
                current_ma=round(current_ma, 2),
                current_a=round(current_a, 4),
                power_w=round(power_w, 4),
                shunt_voltage_mv=round(shunt_voltage_mv, 3),
                bus_voltage_v=round(bus_voltage_v, 4),
                load_voltage_v=round(load_voltage_v, 4),
                sensor_ok=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.last_error = str(exc)
            raise SimulatedSensorError(f"Simulated sensor read failed: {exc}") from exc

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "mode": self.mode,
            "error_message": self.last_error,
            "last_reading_ts": None,
        }
