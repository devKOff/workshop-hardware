"""Sensor layer: INA219 hardware and simulation backends, detection, sampling.

Reuses the existing project's backends under ``solar_monitor.backends`` without
modifying them. The hardware backend imports ``adafruit-circuitpython-ina219``
lazily, so this module imports cleanly on Windows without the Pi stack.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Optional

# Make ``src/solar_monitor`` importable when monitor_gui is run directly
# (``python -m monitor_gui`` from the project root).
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from solar_monitor.backends.hardware import (  # noqa: E402
    DEFAULT_I2C_BUS,
    DEFAULT_I2C_ADDRESS,
    DEFAULT_MAX_CURRENT_A,
    DEFAULT_SHUNT_OHM,
    INA219HardwareBackend,
)
from solar_monitor.backends.interface import BackendError  # noqa: E402
from solar_monitor.backends.simulation import (  # noqa: E402
    SimulatedSensor as _BackendSimulatedSensor,
)

from .config import (  # noqa: E402
    DATA_SOURCE_HARDWARE,
    DATA_SOURCE_SIMULATION,
    I2C_ADDRESS,
    I2C_BUS,
    MAX_CURRENT_A_HARDWARE,
    SHUNT_OHM,
)
from .sample import Sample, validate_sample  # noqa: E402


class HardwareSensor:
    """Genuine INA219 over I2C on the Raspberry Pi.

    Not probed at construction. Call :meth:`detect()` (or :meth:`read_sample`)
    to attempt initialisation. Until probed, :meth:`is_available` is False.
    """

    def __init__(
        self,
        *,
        i2c_bus: int = I2C_BUS,
        i2c_address: int = I2C_ADDRESS,
        shunt_ohm: float = SHUNT_OHM,
        max_current_a: float = MAX_CURRENT_A_HARDWARE,
    ):
        self._backend = INA219HardwareBackend(
            i2c_bus=i2c_bus,
            i2c_address=i2c_address,
            shunt_ohm=shunt_ohm,
            max_current_a=max_current_a,
        )
        self._probed = False

    # -- backend interface -------------------------------------------------
    @property
    def mode(self) -> str:
        return "hardware"

    def detect(self) -> bool:
        """Probe the I2C bus. Returns True if the INA219 responds.

        Safe to call on any platform: on Windows without the driver it records
        an error and returns False -- it never fabricates readings.
        """
        if not self._probed:
            self._backend.probe()
            self._probed = True
        return self._backend.is_available()

    def is_available(self) -> bool:
        return self._backend.is_available()

    def diagnostics(self) -> dict:
        return self._backend.diagnostics()

    def read_sample(self, elapsed_s: float) -> Sample:
        """Read one validated :class:`Sample`, stamped with wall-clock time."""
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            reading = self._backend.read()
        except BackendError as exc:  # missing sensor / I2C failure mid-run
            return Sample(
                timestamp=timestamp,
                elapsed_s=elapsed_s,
                voltage_v=float("nan"),
                current_ma=float("nan"),
                power_w=float("nan"),
                status="read_error",
                data_source=DATA_SOURCE_HARDWARE,
                error=str(exc),
            )

        overflow = self._read_overflow()
        return validate_sample(
            timestamp=timestamp,
            elapsed_s=elapsed_s,
            voltage_v=reading.voltage_v,
            current_a=reading.current_a,
            power_register_w=reading.power_register_w,
            data_source=DATA_SOURCE_HARDWARE,
            overflow=overflow,
        )

    # -- internals ---------------------------------------------------------
    def _read_overflow(self) -> bool:
        """Best-effort INA219 overflow flag from the underlying library sensor.

        The existing backend holds the library sensor privately; we read the
        public ``overflow`` attribute if it exists without modifying the backend.
        """
        try:
            sensor = getattr(self._backend, "_sensor", None)
            if sensor is not None:
                return bool(getattr(sensor, "overflow", False))
        except Exception:  # pragma: no cover - defensive
            pass
        return False


class SimulatedSensor:
    """Realistic solar simulator reused from the existing project.

    Always available; every sample is labelled ``data_source="simulation"``.
    """

    def __init__(self, *, seed=None, **kwargs):
        self._sim = _BackendSimulatedSensor(seed=seed, **kwargs)

    @property
    def mode(self) -> str:
        return "simulation"

    def detect(self) -> bool:
        return True

    def is_available(self) -> bool:
        return True

    def diagnostics(self) -> dict:
        return self._sim.diagnostics()

    def read_sample(self, elapsed_s: float) -> Sample:
        reading = self._sim.read()
        timestamp = reading.timestamp.isoformat()
        return validate_sample(
            timestamp=timestamp,
            elapsed_s=elapsed_s,
            voltage_v=reading.voltage_v,
            current_a=reading.current_a,
            power_register_w=reading.power_register_w,
            data_source=DATA_SOURCE_SIMULATION,
        )


def create_sensor(*, use_hardware: bool, **kwargs):
    """Factory returning a sensor object with the monitor's sample interface."""
    if use_hardware:
        return HardwareSensor(**kwargs)
    return SimulatedSensor(**kwargs)
