"""INA219 hardware driver for Raspberry Pi.

This module talks to the INA219 directly over I²C using ``smbus2`` so there is
no dependency on the third-party ``ina219`` package (which is not available for
all Python versions/architectures). It works on any Raspberry Pi with I²C
enabled and the sensor wired per ``docs/HARDWARE_WIRING.md``.

The module imports ``smbus2`` lazily so that importing this module on Windows
(where ``smbus2`` is unavailable) does not fail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models import Measurement


class INA219SensorError(RuntimeError):
    """Raised when the physical INA219 sensor cannot be read."""


class INA219Sensor:
    """Direct I²C driver for the Texas Instruments INA219 sensor.

    Register map (16-bit registers, big-endian):
        0x00 Config
        0x01 Shunt Voltage   (10 µV/LSB, signed)
        0x02 Bus Voltage     (4 mV/LSB, top 13 bits)
        0x03 Power           (Power_LSB per LSB)
        0x04 Current         (Current_LSB per LSB, signed)
        0x05 Calibration
    """

    REG_CONFIG = 0x00
    REG_SHUNT_VOLTAGE = 0x01
    REG_BUS_VOLTAGE = 0x02
    REG_POWER = 0x03
    REG_CURRENT = 0x04
    REG_CALIBRATION = 0x05

    # Configuration register bit masks
    CONFIG_RESET = 0x8000
    CONFIG_BRNG_32V = 0x2000
    CONFIG_PGA_320MV = 0x0000  # shunt full-scale ±320 mV
    CONFIG_BADC_12BIT = 0x0C00
    CONFIG_SADC_12BIT = 0x0300
    CONFIG_MODE_CONT_SHUNT_BUS = 0x0007

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
        self._bus = None
        self._current_lsb: Optional[float] = None
        self._power_lsb: Optional[float] = None
        self._calibration: Optional[int] = None
        self._initialize()

    # ------------------------------------------------------------------ #
    # I²C bus handling
    # ------------------------------------------------------------------ #
    def _bus_module(self):
        """Import and return the smbus2 module, raising a clear error if unavailable."""
        try:
            import smbus2  # type: ignore
        except ImportError as exc:
            raise INA219SensorError(
                "The 'smbus2' library is not installed. Install it on the Raspberry Pi "
                "with: pip install smbus2"
            ) from exc
        return smbus2

    def _initialize(self) -> None:
        """Open the I²C bus, reset and configure the INA219, compute calibration."""
        try:
            smbus2 = self._bus_module()
            self._bus = smbus2.SMBus(1)  # I²C bus 1 on Raspberry Pi

            # Reset the device
            self._write_register(self.REG_CONFIG, self.CONFIG_RESET)
            # Small delay after reset
            import time

            time.sleep(0.01)

            # Compute calibration
            current_lsb = self.max_expected_amps / 32767.0
            calibration = int(0.04096 / (current_lsb * self.shunt_ohms))
            calibration = max(1, min(calibration, 65535))

            self._current_lsb = current_lsb
            self._power_lsb = 20.0 * current_lsb
            self._calibration = calibration

            # Write calibration register
            self._write_register(self.REG_CALIBRATION, calibration)

            # Configure: BRNG=32V, PGA=±320mV, BADC=12-bit, SADC=12-bit,
            # mode=continuous shunt+bus
            config = (
                self.CONFIG_BRNG_32V
                | self.CONFIG_PGA_320MV
                | self.CONFIG_BADC_12BIT
                | self.CONFIG_SADC_12BIT
                | self.CONFIG_MODE_CONT_SHUNT_BUS
            )
            self._write_register(self.REG_CONFIG, config)

            self.connected = True
            self.last_error = None
        except INA219SensorError:
            raise
        except Exception as exc:  # noqa: BLE001 - hardware may be absent
            self.connected = False
            self._bus = None
            self.last_error = (
                f"Failed to initialise INA219 at address 0x{self.i2c_address:02X}: {exc}"
            )

    def _write_register(self, reg: int, value: int) -> None:
        """Write a 16-bit value to the given register (big-endian)."""
        if self._bus is None:
            raise INA219SensorError("I²C bus not open")
        high = (value >> 8) & 0xFF
        low = value & 0xFF
        self._bus.write_i2c_block_data(self.i2c_address, reg, [high, low])

    def _read_register(self, reg: int) -> int:
        """Read a 16-bit value from the given register (big-endian)."""
        if self._bus is None:
            raise INA219SensorError("I²C bus not open")
        result = self._bus.read_i2c_block_data(self.i2c_address, reg, 2)
        return (result[0] << 8) | result[1]

    def _read_signed_register(self, reg: int) -> int:
        """Read a signed 16-bit value from the given register."""
        raw = self._read_register(reg)
        if raw > 32767:
            raw -= 65536
        return raw

    # ------------------------------------------------------------------ #
    # Readings
    # ------------------------------------------------------------------ #
    def read(self) -> Measurement:
        """Return a :class:`Measurement` from the physical INA219 sensor.

        Never falls back to simulated data on failure; raises
        :class:`INA219SensorError` so the caller can surface the problem.
        """
        if self._bus is None or self._current_lsb is None:
            self.last_error = self.last_error or "INA219 device not initialised"
            raise INA219SensorError(self.last_error)

        try:
            # Bus voltage: register >> 3, 4 mV per LSB
            bus_raw = self._read_register(self.REG_BUS_VOLTAGE)
            bus_voltage_v = (bus_raw >> 3) * 0.004

            # Shunt voltage: signed, 10 µV per LSB
            shunt_raw = self._read_signed_register(self.REG_SHUNT_VOLTAGE)
            shunt_voltage_v = shunt_raw * 0.00001
            shunt_voltage_mv = shunt_voltage_v * 1000.0

            # Current: signed, Current_LSB per LSB
            current_raw = self._read_signed_register(self.REG_CURRENT)
            current_a = current_raw * self._current_lsb
            current_ma = current_a * 1000.0

            # Power: Power_LSB per LSB
            power_raw = self._read_register(self.REG_POWER)
            power_w = power_raw * self._power_lsb

            # Load voltage = bus voltage - shunt voltage drop
            load_voltage_v = bus_voltage_v - shunt_voltage_v

            self.connected = True
            self.last_error = None
            return Measurement(
                timestamp=datetime.now(),
                voltage_v=round(bus_voltage_v, 4),
                current_ma=round(current_ma, 2),
                current_a=round(current_a, 4),
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

    def close(self) -> None:
        """Close the I²C bus."""
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
            finally:
                self._bus = None
