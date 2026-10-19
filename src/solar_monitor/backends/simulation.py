"""Realistic solar simulation backend (Windows-safe, no Pi imports).

Models a 6 V, 3 W panel on a 33 ohm resistive load:
- time-of-day sunlight envelope (day/night cycle)
- gradual irradiance drift (random walk)
- stochastic cloud events (sudden irradiance drops and recoveries)
- low-light conditions (dawn/dusk/night approach zero)
- Gaussian measurement noise
- configurable sensor errors / faults

All output is physically plausible: panel voltage tracks irradiance and
current is bounded by V / (load_ohm + series_resistance), so power never
exceeds what the load permits (well below the 3 W panel rating).
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from solar_monitor.backends.interface import BackendError, SensorBackend, SensorReading

# Physical constants for the reference hardware.
DEFAULT_BASE_VOLTAGE_V = 5.5          # panel operating voltage at full sun
DEFAULT_LOAD_OHM = 33.0               # resistive load
DEFAULT_SERIES_RESISTANCE_OHM = 0.1   # wiring + sense resistance
DEFAULT_NOISE_AMPLITUDE_V = 0.05      # measurement noise (±V)
SECONDS_PER_DAY = 86400.0


class SimulatedSensor(SensorBackend):
    """Deterministic-seedable realistic solar simulator."""

    def __init__(
        self,
        *,
        base_voltage_v=DEFAULT_BASE_VOLTAGE_V,
        load_ohm=DEFAULT_LOAD_OHM,
        series_resistance_ohm=DEFAULT_SERIES_RESISTANCE_OHM,
        noise_amplitude_v=DEFAULT_NOISE_AMPLITUDE_V,
        seed=None,
        fault=False,
        fault_after_seconds=None,
        irradiance_variation=0.25,
        cloud_probability_per_sample=0.02,
        cloud_depth_min=0.35,
        cloud_depth_max=0.85,
    ):
        self._base_voltage_v = float(base_voltage_v)
        self._load_ohm = float(load_ohm)
        self._series_resistance_ohm = float(series_resistance_ohm)
        self._noise_amplitude_v = float(noise_amplitude_v)
        self._fault = bool(fault)
        self._fault_after_seconds = fault_after_seconds
        self._irradiance_variation = float(irradiance_variation)
        self._cloud_probability_per_sample = float(cloud_probability_per_sample)
        self._cloud_depth_min = float(cloud_depth_min)
        self._cloud_depth_max = float(cloud_depth_max)
        self._started_at = datetime.now(timezone.utc)
        self._rng = random.Random(seed)
        self._irradiance = 1.0          # normalized 0..1
        self._cloud_until = None        # datetime until which cloud persists
        self._samples = 0

    # -- backend interface -------------------------------------------------
    @property
    def mode(self):
        return "simulated"

    def is_available(self):
        return True

    def diagnostics(self):
        return {
            "mode": self.mode,
            "available": self.is_available(),
            "hardware": False,
            "simulated": True,
            "samples": self._samples,
            "base_voltage_v": self._base_voltage_v,
            "load_ohm": self._load_ohm,
            "fault": self._fault,
        }

    # -- simulation internals ---------------------------------------------
    def _sunlight_envelope(self, elapsed):
        """Time-of-day solar elevation envelope, 0 (night) to 1 (noon)."""
        phase = 2.0 * math.pi * (elapsed / SECONDS_PER_DAY) - math.pi / 2.0
        return max(0.0, math.sin(phase))

    def _update_irradiance(self, now):
        elapsed = (now - self._started_at).total_seconds()
        base = self._sunlight_envelope(elapsed)

        # Gradual random-walk drift around the envelope.
        drift = self._rng.uniform(-self._irradiance_variation, self._irradiance_variation) * 0.1
        self._irradiance = min(1.0, max(0.0, self._irradiance + drift))

        # Blend toward the envelope slowly so irradiance never jumps arbitrarily.
        self._irradiance = 0.95 * self._irradiance + 0.05 * base

        # Low-light floor near dawn/dusk/night is implicit via the envelope.

        # Cloud events.
        if self._cloud_until is not None and now < self._cloud_until:
            depth = self._cloud_depth  # persists for the cloud duration
        else:
            self._cloud_until = None
            self._cloud_depth = 1.0
            if self._rng.random() < self._cloud_probability_per_sample:
                duration_s = self._rng.uniform(3.0, 20.0)
                self._cloud_until = now + timedelta(seconds=duration_s)
                self._cloud_depth = self._rng.uniform(
                    self._cloud_depth_min, self._cloud_depth_max
                )
                depth = self._cloud_depth
            else:
                depth = 1.0

        if self._cloud_until is not None:
            self._irradiance *= depth

        return max(0.0, min(1.0, self._irradiance))

    def read(self):
        if self._fault:
            self._samples += 1
            return SensorReading(
                timestamp=datetime.now(timezone.utc),
                voltage_v=float("nan"),
                current_a=float("nan"),
                power_register_w=None,
                mode=self.mode,
                status="fault",
                error="simulated sensor fault",
            )

        now = datetime.now(timezone.utc)
        if self._fault_after_seconds is not None:
            elapsed = (now - self._started_at).total_seconds()
            if elapsed >= self._fault_after_seconds:
                self._samples += 1
                return SensorReading(
                    timestamp=now,
                    voltage_v=float("nan"),
                    current_a=float("nan"),
                    power_register_w=None,
                    mode=self.mode,
                    status="fault",
                    error="simulated sensor fault after configured duration",
                )

        irradiance = self._update_irradiance(now)

        # Panel voltage tracks irradiance; clamped below base voltage.
        panel_v = self._base_voltage_v * irradiance

        # Current limited by load (+ series resistance). Physically plausible.
        total_r = self._load_ohm + self._series_resistance_ohm
        current_a = panel_v / total_r

        # Terminal voltage after series drop.
        voltage_v = current_a * self._load_ohm
        voltage_v = min(max(voltage_v, 0.0), self._base_voltage_v)

        # Measurement noise on voltage.
        voltage_v += self._rng.uniform(-self._noise_amplitude_v, self._noise_amplitude_v)
        voltage_v = min(max(voltage_v, 0.0), self._base_voltage_v)
        current_a = voltage_v / self._load_ohm

        power_register_w = voltage_v * current_a

        # Clamp to physical limits for this panel+load.
        max_current_a = self._base_voltage_v / self._load_ohm
        current_a = min(max(current_a, 0.0), max_current_a)

        self._samples += 1
        return SensorReading(
            timestamp=now,
            voltage_v=voltage_v,
            current_a=current_a,
            power_register_w=power_register_w,
            mode=self.mode,
            status="ok",
            error=None,
        )
