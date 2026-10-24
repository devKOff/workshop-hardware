"""Sensor layer for the Solar Panel Performance Monitor.

Provides:
- SensorReading: a single validated sample.
- ValidationError / OverflowError / OutOfRangeError: reasons a sample is invalid.
- validate_reading(): validate raw bus/shunt/current values and compute power.
- INA219HardwareSensor: talks to a real INA219 over I2C (lazy import, so
  Windows / test machines without the library can still import this module).
- SimulatedSensor: smooth, realistic panel values labeled "simulation".
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SensorReading:
    """One validated sample.

    timestamp  : timezone-aware ISO 8601 wall-clock time (seconds since epoch)
    elapsed_s  : seconds since session start (float)
    voltage_v  : panel voltage in V (bus + shunt for high-side wiring)
    current_ma : current in mA
    power_w    : power in W = voltage_v * (current_ma / 1000)
    status     : "ok", "read_error", "overflow", "out_of_range"
    data_source: "hardware" or "simulation"
    """

    timestamp: str
    elapsed_s: float
    voltage_v: float
    current_ma: float
    power_w: float
    status: str
    data_source: str


class ValidationError(Exception):
    """A reading failed validation and is not a valid sample."""


class OverflowError(ValidationError):
    """The INA219 overflow flag is set."""


class OutOfRangeError(ValidationError):
    """A value is outside the sensor's configured range."""


class SensorProtocol(Protocol):
    """Interface the recorder needs from any sensor."""

    name: str
    data_source: str

    def detect(self) -> bool:
        """Return True if the sensor is present and reachable."""

    def read_raw(self) -> dict:
        """Return a dict with raw sensor values (implementation-specific)."""

    def close(self) -> None:
        """Release resources (safe to call more than once)."""


# INA219 configuration constants (matching adafruit-circuitpython-ina219).
# Range: +/-32 V bus, +/-2 A shunt (0.1 ohm shunt resistor default).
BUS_VOLTAGE_RANGE_V = 32.0
SHUNT_VOLTAGE_RANGE_V = 0.32  # +/-320 mV
SHUNT_RESISTANCE_OHM = 0.1


def _is_finite(value: float) -> bool:
    return value is not None and math.isfinite(value)


def validate_reading(
    bus_voltage_v: float,
    shunt_voltage_v: float,
    current_ma: float,
    overflow: bool = False,
) -> SensorReading:
    """Validate raw values and return a SensorReading with computed fields.

    Raises ValidationError (or subclass) when the sample is not valid.
    The caller decides what to do with an invalid sample (store with a status,
    never turn it into 0).
    """
    if overflow:
        raise OverflowError("INA219 overflow flag set")

    if not _is_finite(bus_voltage_v):
        raise ValidationError("bus voltage is not finite")
    if not _is_finite(shunt_voltage_v):
        raise ValidationError("shunt voltage is not finite")
    if not _is_finite(current_ma):
        raise ValidationError("current is not finite")

    # Range checks against the configured sensor range.
    if abs(bus_voltage_v) > BUS_VOLTAGE_RANGE_V:
        raise OutOfRangeError(
            f"bus voltage {bus_voltage_v} V outside range "
            f"{BUS_VOLTAGE_RANGE_V} V"
        )
    if abs(shunt_voltage_v) > SHUNT_VOLTAGE_RANGE_V:
        raise OutOfRangeError(
            f"shunt voltage {shunt_voltage_v} V outside range "
            f"{SHUNT_VOLTAGE_RANGE_V} V"
        )
    # current_ma = shunt_voltage_v / SHUNT_RESISTANCE_OHM * 1000
    max_current_ma = (SHUNT_VOLTAGE_RANGE_V / SHUNT_RESISTANCE_OHM) * 1000.0
    if abs(current_ma) > max_current_ma:
        raise OutOfRangeError(
            f"current {current_ma} mA outside range {max_current_ma:.0f} mA"
        )

    # High-side wiring: panel voltage is measured after the shunt, so panel
    # voltage ≈ bus voltage + shunt voltage (VIN+ to GND).
    voltage_v = bus_voltage_v + shunt_voltage_v
    current_a = current_ma / 1000.0
    power_w = voltage_v * current_a

    return SensorReading(
        timestamp="",  # filled in by the caller/session
        elapsed_s=0.0,  # filled in by the caller/session
        voltage_v=round(voltage_v, 4),
        current_ma=round(current_ma, 4),
        power_w=round(power_w, 4),
        status="ok",
        data_source="hardware",
    )


class INA219HardwareSensor:
    """Real INA219 over I2C.

    The adafruit library is imported lazily inside methods so this module can
    be imported on machines that don't have it (Windows, test runners).
    """

    def __init__(self, i2c_address: int = 0x40) -> None:
        self.i2c_address = i2c_address
        self._ina = None
        self.name = f"INA219 @ 0x{i2c_address:02X}"
        self.data_source = "hardware"
        self._closed = False

    def detect(self) -> bool:
        if self._closed:
            return False
        try:
            import board  # type: ignore
            import busio  # type: ignore
            import adafruit_ina219  # type: ignore

            i2c = busio.I2C(board.SCL, board.SDA)
            self._ina = adafruit_ina219.INA219(i2c, addr=self.i2c_address)
            # Touch a real register to confirm the device responds.
            _ = self._ina.bus_voltage
            return True
        except Exception:
            self._ina = None
            return False

    def read_raw(self) -> dict:
        if self._closed or self._ina is None:
            raise RuntimeError("INA219 sensor not detected")
        import adafruit_ina219  # type: ignore  # noqa: F401

        bus_voltage = self._ina.bus_voltage
        shunt_voltage = self._ina.shunt_voltage
        current = self._ina.current  # in mA
        overflow = getattr(self._ina, "overflow", False)
        return {
            "bus_voltage_v": bus_voltage,
            "shunt_voltage_v": shunt_voltage,
            "current_ma": current,
            "overflow": overflow,
        }

    def close(self) -> None:
        self._closed = True
        self._ina = None


class SimulatedSensor:
    """Smooth, realistic simulator for development and testing.

    Produces about 5-6 V and tens of mA with small noise, never impossible
    values. Every record is labeled "simulation".
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.name = "Simulated INA219"
        self.data_source = "simulation"
        self._closed = False
        # Slowly drifting base values so the curve looks realistic.
        self._t = 0.0

    def detect(self) -> bool:
        return not self._closed

    def read_raw(self) -> dict:
        if self._closed:
            raise RuntimeError("simulated sensor is closed")
        self._t += 1.0
        # Base curve: voltage around 5.5 V with a slow sine drift.
        base_v = 5.5 + 0.3 * math.sin(self._t / 20.0)
        noise_v = self._rng.gauss(0.0, 0.02)
        bus_voltage_v = base_v + noise_v
        # Shunt voltage small (tens of mV), same sign as current.
        base_ma = 200.0 + 50.0 * math.sin(self._t / 15.0)
        noise_ma = self._rng.gauss(0.0, 5.0)
        current_ma = base_ma + noise_ma
        # Keep values physically plausible.
        bus_voltage_v = max(0.0, min(32.0, bus_voltage_v))
        current_ma = max(0.0, min(2000.0, current_ma))
        shunt_voltage_v = current_ma / 1000.0 * SHUNT_RESISTANCE_OHM
        return {
            "bus_voltage_v": bus_voltage_v,
            "shunt_voltage_v": shunt_voltage_v,
            "current_ma": current_ma,
            "overflow": False,
        }

    def close(self) -> None:
        self._closed = True


def make_sensor(mode: str, seed: int | None = None) -> SensorProtocol:
    """Factory: 'hardware' -> INA219HardwareSensor, 'simulation' -> SimulatedSensor."""
    if mode == "hardware":
        return INA219HardwareSensor()
    if mode == "simulation":
        return SimulatedSensor(seed=seed)
    raise ValueError(f"unknown sensor mode: {mode!r}")
