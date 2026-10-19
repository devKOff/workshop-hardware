"""INA219 hardware backend (Raspberry Pi).

Pi-specific imports (adafruit-circuitpython-ina219, board, busio) are
*lazy*: this module imports cleanly on Windows without the Pi stack. The
backend is *not* probed at construction time -- probing happens only when
explicitly requested (e.g. when the user selects hardware mode), so Windows
development is never affected by the absent driver. Genuine readings are
measured; power is resolved consistently as P = V x I. Never fabricates,
caches, or reuses stale values.
"""

from __future__ import annotations

from datetime import datetime, timezone

from solar_monitor.backends.interface import BackendError, SensorBackend, SensorReading

DEFAULT_I2C_BUS = 1
DEFAULT_I2C_ADDRESS = 0x40


class INA219HardwareBackend(SensorBackend):
    """Genuine INA219 voltage/current sensor over I2C on Raspberry Pi.

    Not probed at construction: call :meth:`probe` (or :meth:`read`) to
    attempt initialisation. Until probed, :meth:`is_available` returns False.
    """

    def __init__(self, *, i2c_bus=DEFAULT_I2C_BUS, i2c_address=DEFAULT_I2C_ADDRESS):
        self._i2c_bus = i2c_bus
        self._i2c_address = i2c_address
        self._sensor = None
        self._init_error = "not probed"
        self._probed = False
        self._samples = 0

    # -- backend interface -------------------------------------------------
    @property
    def mode(self):
        return "hardware"

    def is_available(self):
        return self._probed and self._sensor is not None

    def diagnostics(self):
        return {
            "mode": self.mode,
            "available": self.is_available(),
            "hardware": True,
            "simulated": False,
            "probed": self._probed,
            "i2c_bus": self._i2c_bus,
            "i2c_address": hex(self._i2c_address),
            "init_error": self._init_error,
            "samples": self._samples,
            "library": "adafruit-circuitpython-ina219",
        }

    def probe(self):
        """Attempt to initialise the INA219. Safe to call on any platform;
        on Windows without the driver it records an error and stays
        unavailable -- it never fabricates readings."""
        if self._probed:
            return
        self._probed = True
        self._initialise()

    def read(self):
        self.probe()
        if not self.is_available():
            self._samples += 1
            raise BackendError(
                "INA219 hardware unavailable: " + (self._init_error or "not initialised")
            )

        try:
            reading = self._read_once()
        except Exception as exc:  # noqa: BLE001 - honest hardware diagnostics
            self._samples += 1
            raise BackendError(f"INA219 read failed: {exc}") from exc

        # Never fabricate: invalid readings are reported as faults, not reused.
        if not _is_valid(reading):
            self._samples += 1
            return SensorReading(
                timestamp=datetime.now(timezone.utc),
                voltage_v=float("nan"),
                current_a=float("nan"),
                power_register_w=None,
                mode=self.mode,
                status="fault",
                error="invalid INA219 reading",
            )

        self._samples += 1
        return reading

    # -- hardware ----------------------------------------------------------
    def _initialise(self):
        try:
            # Lazy import: only the Pi has board/busio/adafruit. Windows
            # development must not fail at import time.
            from adafruit_ina219 import INA219  # noqa: PLC0415

            self._sensor = INA219(i2c_bus=self._i2c_bus, addr=self._i2c_address)
        except Exception as exc:  # noqa: BLE001 - hardware may be absent
            self._sensor = None
            self._init_error = f"{type(exc).__name__}: {exc}"

    def _read_once(self):
        sensor = self._sensor
        bus_voltage_v = float(sensor.bus_voltage)
        shunt_voltage_v = float(sensor.shunt_voltage)
        current_a = float(sensor.current) / 1000.0  # library returns mA

        # Genuine measurement: power resolved consistently as P = V x I.
        power_w = bus_voltage_v * current_a

        return SensorReading(
            timestamp=datetime.now(timezone.utc),
            voltage_v=bus_voltage_v,
            current_a=current_a,
            power_register_w=power_w,
            mode=self.mode,
            status="ok",
            error=None,
        )


def _is_valid(reading: SensorReading) -> bool:
    import math

    return (
        reading is not None
        and math.isfinite(reading.voltage_v)
        and math.isfinite(reading.current_a)
        and reading.voltage_v >= 0
    )
