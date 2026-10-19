"""INA219 sensor reader for the Solar Panel Performance Monitor.

Wraps the ``ina219`` PyPI package (built on ``smbus2``) and adds:
- error handling for I²C bus faults and range errors
- units normalized to V / mA / mW
- signed current so bidirectional flow is reported correctly
- a clear "ok / error" flag so the caller never mistakes a failure for 0 W

Hardware assumptions (verify before use):
- Shunt resistor = SHUNT_OHMS (config). Commonly 0.1 Ω; not universal.
- I²C address = INA219_ADDRESS (config). Default 0x40 (A0=A1=GND).
- Bus voltage within the breakout's rated range (typically 0–26 V ADC input).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

try:
    from ina219 import INA219, DeviceRangeError  # type: ignore

    _INA219_AVAILABLE = True
except Exception:  # pragma: no cover - only missing on non-Pi dev machines
    INA219 = None  # type: ignore
    DeviceRangeError = Exception  # type: ignore
    _INA219_AVAILABLE = False


@dataclass
class Reading:
    """A single sensor sample."""

    timestamp: str                      # ISO 8601 local time, seconds
    bus_voltage_v: Optional[float]      # panel-side bus voltage (V)
    shunt_voltage_v: Optional[float]    # voltage across the shunt (V)
    current_ma: Optional[float]         # current through the shunt (mA); signed
    power_mw: Optional[float]           # bus_voltage * current (mW); signed
    ok: bool                            # True if the sample is valid
    error: Optional[str] = None         # human-readable failure reason


class SolarSensor:
    """Thin, fault-tolerant wrapper around the ina219 library."""

    def __init__(
        self,
        address: int = 0x40,
        shunt_ohms: float = 0.1,
        max_amps: float = 2.0,
        busnum: int = 1,
    ) -> None:
        self.address = address
        self.shunt_ohms = shunt_ohms
        self.max_amps = max_amps
        self.busnum = busnum
        self._sensor = None
        self._initialized = False
        self._init_error: Optional[str] = None

    def initialize(self) -> None:
        """Create and configure the INA219 device. Call once before read()."""
        if not _INA219_AVAILABLE:
            self._init_error = (
                "ina219 Python package is not installed. "
                "Install it: pip install ina219 smbus2"
            )
            return
        try:
            self._sensor = INA219(
                shunt_ohms=self.shunt_ohms,
                max_amps=self.max_amps,
                address=self.address,
                busnum=self.busnum,
            )
            self._sensor.configure()
            self._initialized = True
        except Exception as exc:  # noqa: BLE001 - report any init failure cleanly
            self._initialized = False
            self._init_error = f"INA219 initialization failed: {exc}"

    def read(self) -> Reading:
        """Return one Reading. Never raises; failures are reported via ok/error."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")

        if not self._initialized or self._sensor is None:
            return Reading(
                ts, None, None, None, None, False,
                self._init_error or "sensor not initialized",
            )

        try:
            # The ina219 library returns signed values:
            #   current > 0 mA  : current flows VIN+ -> VIN- (panel discharging)
            #   current < 0 mA  : reverse direction
            bus_v = float(self._sensor.voltage())          # V
            shunt_mv = float(self._sensor.shunt_voltage()) # mV
            current_ma = float(self._sensor.current())     # mA (signed)
            power_mw = float(self._sensor.power())         # mW (signed)

            return Reading(
                timestamp=ts,
                bus_voltage_v=bus_v,
                shunt_voltage_v=shunt_mv / 1000.0,
                current_ma=current_ma,
                power_mw=power_mw,
                ok=True,
                error=None,
            )
        except DeviceRangeError as exc:
            return Reading(
                ts, None, None, None, None, False,
                f"INA219 range error: {exc}. "
                "Reduce load current or increase MAX_AMPS in src/config.py.",
            )
        except Exception as exc:  # noqa: BLE001 - I²C bus faults etc.
            return Reading(
                ts, None, None, None, None, False,
                f"I2C read failed: {exc}. Check wiring and i2cdetect.",
            )
