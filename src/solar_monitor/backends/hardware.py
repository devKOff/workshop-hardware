"""INA219 hardware backend (Raspberry Pi).

Pi-specific imports (adafruit-circuitpython-ina219, board, busio) are
*lazy*: this module imports cleanly on Windows without the Pi stack. The
backend is *not* probed at construction time -- probing happens only when
explicitly requested (e.g. when the user selects hardware mode), so Windows
development is never affected by the absent driver. Genuine readings are
measured; power is resolved consistently as P = V x I. Never fabricates,
caches, or reuses stale values.

Calibration
-----------
The INA219 calibration register is computed from the shunt resistance and
maximum expected current:

    Cal = 4096 / (Max_Current × R_shunt)
    Current_LSB = Max_Current / 32767
    Power_LSB   = 20 × Current_LSB

For the reference hardware (6 V, 3 W panel, 33 Ω load):
    Max current ≈ 3 W / 6 V = 0.5 A (use 1.0 A headroom)
    Shunt       = 0.1 Ω  → at 0.5 A, shunt voltage = 50 mV (within ±81.92 mV)
"""

from __future__ import annotations

from datetime import datetime, timezone

from solar_monitor.backends.interface import BackendError, SensorBackend, SensorReading

DEFAULT_I2C_BUS = 1
DEFAULT_I2C_ADDRESS = 0x40
DEFAULT_SHUNT_OHM = 0.1
DEFAULT_MAX_CURRENT_A = 1.0


class INA219HardwareBackend(SensorBackend):
    """Genuine INA219 voltage/current sensor over I2C on Raspberry Pi.

    Not probed at construction: call :meth:`probe` (or :meth:`read`) to
    attempt initialisation. Until probed, :meth:`is_available` returns False.
    """

    def __init__(
        self,
        *,
        i2c_bus=DEFAULT_I2C_BUS,
        i2c_address=DEFAULT_I2C_ADDRESS,
        shunt_ohm=DEFAULT_SHUNT_OHM,
        max_current_a=DEFAULT_MAX_CURRENT_A,
    ):
        self._i2c_bus = i2c_bus
        self._i2c_address = i2c_address
        self._shunt_ohm = float(shunt_ohm)
        self._max_current_a = float(max_current_a)
        self._sensor = None
        self._init_error = "not probed"
        self._probed = False
        self._samples = 0
        self._current_lsb_a = None

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
            "shunt_ohm": self._shunt_ohm,
            "max_current_a": self._max_current_a,
            "current_lsb_a": self._current_lsb_a,
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
                "INA219 hardware unavailable: "
                + (self._init_error or "not initialised")
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

            # Configure calibration for the shunt and max current.
            # Current_LSB = Max_Current / 32767 gives full-scale resolution.
            current_lsb_a = self._max_current_a / 32767.0
            try:
                self._sensor.set_calibration(current_lsb_a, self._shunt_ohm)
            except AttributeError:
                # Older library versions may not expose set_calibration;
                # the library uses factory defaults. Continue with a note.
                self._init_error = (
                    self._init_error
                    + "; set_calibration not available, using factory defaults"
                )
            self._current_lsb_a = current_lsb_a
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
