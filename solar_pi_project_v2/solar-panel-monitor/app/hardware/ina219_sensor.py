"""INA219 hardware driver for Raspberry Pi.

This module imports the third-party ``ina219`` library lazily so that the
application package can still be imported and tested on Windows (where the
library and its ``smbus`` dependency are unavailable). Instantiate
:class:`INA219Sensor` only on a Raspberry Pi with I²C enabled and the sensor
wired per ``docs/HARDWARE_WIRING.md``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models import Measurement


class INA219SensorError(RuntimeError):
    """Raised when the physical INA219 sensor cannot be read."""


class INA219Sensor:
    """Wrapper around the ``ina219`` Python library for the physical sensor.

    The library is imported lazily inside methods so importing this module on a
    machine without ``ina219``/``smbus`` (e.g. Windows) does not fail.
    """

    def __init__(
        self,
        *,
        i2c_address: int = 0x40,
        shunt_ohms: float = 0.1,
        max_expected_amps: float = 0.5,
    ) -> None:
        self.i2c_address = i2c_address
        self.shunt_ohms = shunt_ohms
        self.max_expected_amps = max_expected_amps
        self.connected = False
        self.mode = "hardware"
        self.last_error: Optional[str] = None
        self._ina = None
        self._initialize()

    # ------------------------------------------------------------------ #
    # Library handling
    # ------------------------------------------------------------------ #
    def _library(self):
        """Import and return the ina219 library, raising a clear error if unavailable."""
        try:
            import ina219  # type: ignore
        except ImportError as exc:
            raise INA219SensorError(
                "The 'ina219' library is not installed. Install it on the Raspberry Pi "
                "or run in simulation mode (SENSOR_MODE=simulation)."
            ) from exc
        return ina219

    def _initialize(self) -> None:
        """Create and configure the INA219 device object."""
        try:
            ina219 = self._library()
            self._ina = ina219.INA219(
                self.shunt_ohms,
                max_expected_amps=self.max_expected_amps,
                address=self.i2c_address,
            )
            self._ina.configure()
            self.connected = True
            self.last_error = None
        except INA219SensorError:
            raise
        except Exception as exc:  # noqa: BLE001 - hardware may be absent
            self.connected = False
            self._ina = None
            self.last_error = (
                f"Failed to initialise INA219 at address 0x{self.i2c_address:02X}: {exc}"
            )

    # ------------------------------------------------------------------ #
    # Readings
    # ------------------------------------------------------------------ #
    def read(self) -> Measurement:
        """Return a :class:`Measurement` from the physical INA219 sensor.

        Never falls back to simulated data on failure; raises
        :class:`INA219SensorError` so the caller can surface the problem.
        """
        if self._ina is None:
            self.last_error = self.last_error or "INA219 device not initialised"
            raise INA219SensorError(self.last_error)

        try:
            import ina219  # type: ignore  # noqa: F401

            bus_voltage_v = self._ina.bus_voltage
            shunt_voltage_mv = self._ina.shunt_voltage  # millivolts
            current_ma = self._ina.current  # milliamps
            power_w = self._ina.power  # watts

            # The load voltage is bus voltage minus shunt voltage drop.
            load_voltage_v = bus_voltage_v - (shunt_voltage_mv / 1000.0)

            self.connected = True
            self.last_error = None
            return Measurement(
                timestamp=datetime.now(),
                voltage_v=round(bus_voltage_v, 4),
                current_ma=round(current_ma, 2),
                current_a=round(current_ma / 1000.0, 4),
                power_w=round(power_w, 4),
                shunt_voltage_mv=round(shunt_voltage_mv, 3),
                bus_voltage_v=round(bus_voltage_v, 4),
                load_voltage_v=round(load_voltage_v, 4),
                sensor_ok=True,
            )
        except INA219SensorError:
            raise
        except Exception as exc:  # noqa: BLE001 - transient I2C errors
            self.connected = False
            self.last_error = f"INA219 read failed: {exc}"
            raise INA219SensorError(self.last_error) from exc

    def status(self) -> dict:
        return {
            "connected": self.connected,
            "mode": self.mode,
            "error_message": self.last_error,
            "last_reading_ts": None,
        }
