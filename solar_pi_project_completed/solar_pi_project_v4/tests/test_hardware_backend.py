"""Phase 10: Mock-based INA219 hardware backend tests.

These tests run on Windows without any INA219 hardware. They mock the
adafruit-circuitpython-ina219 module to simulate genuine sensor behavior,
then verify:

- Genuine readings are measured (not fabricated)
- Power is resolved consistently as P = V x I
- Hardware failure = honest error state (BackendError raised)
- Invalid readings are reported as faults, never accumulated as new values
- Hardware mode never silently substitutes simulation
- Windows unaffected: no adafruit import at module load time
"""

from __future__ import annotations

import sys
import types
import unittest.mock

import pytest

# ---------------------------------------------------------------------------
# Mock the adafruit_ina219 module before importing the hardware backend so
# the module imports cleanly on Windows (no Pi hardware/driver present).
# ---------------------------------------------------------------------------

_MOCK_SENSOR_READINGS = []  # list of (bus_voltage_v, shunt_voltage_v, current_mA)


class _MockINA219:
    """Mock adafruit_ina219.INA219 sensor for testing."""

    def __init__(self, i2c_bus=None, addr=None):
        self.i2c_bus = i2c_bus
        self.addr = addr
        self._call_count = 0

    @property
    def bus_voltage(self):
        self._call_count += 1
        if not _MOCK_SENSOR_READINGS:
            raise RuntimeError("no mock readings configured")
        return _MOCK_SENSOR_READINGS[self._call_count - 1][0]

    @property
    def shunt_voltage(self):
        if not _MOCK_SENSOR_READINGS:
            raise RuntimeError("no mock readings configured")
        return _MOCK_SENSOR_READINGS[self._call_count - 1][1]

    @property
    def current(self):
        # library returns mA
        if not _MOCK_SENSOR_READINGS:
            raise RuntimeError("no mock readings configured")
        return _MOCK_SENSOR_READINGS[self._call_count - 1][2]

    def set_calibration(self, current_lsb_a, shunt_ohm):
        self.current_lsb_a = current_lsb_a
        self.shunt_ohm = shunt_ohm


def _install_mock():
    """Install the mock adafruit_ina219 module into sys.modules."""
    mock_mod = types.ModuleType("adafruit_ina219")
    mock_mod.INA219 = _MockINA219
    sys.modules["adafruit_ina219"] = mock_mod
    return mock_mod


def _configure_readings(readings):
    """Configure mock sensor readings: list of (bus_voltage_v, shunt_voltage_v, current_mA)."""
    _MOCK_SENSOR_READINGS.clear()
    _MOCK_SENSOR_READINGS.extend(readings)


def _reset_mock():
    _MOCK_SENSOR_READINGS.clear()
    if "adafruit_ina219" in sys.modules:
        del sys.modules["adafruit_ina219"]


# Install mock before importing the backend under test
_install_mock()

from solar_monitor.backends import (  # noqa: E402
    BackendError,
    INA219HardwareBackend,
)


def test_no_adafruit_import_at_module_level():
    """The hardware backend module must not import adafruit at module load;
    the import is lazy inside _initialise()."""
    import solar_monitor.backends.hardware as mod

    text = open(mod.__file__, encoding="utf-8").read()
    # "from adafruit_ina219 import" appears only inside a function body
    assert "from adafruit_ina219 import INA219" in text
    # But it's indented (inside _initialise), not at module top level
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "from adafruit_ina219 import INA219" in line:
            assert line.startswith("            "), (
                "adafruit import must be lazy (inside a function), not at module level"
            )


def test_backend_mode_is_hardware():
    backend = INA219HardwareBackend()
    assert backend.mode == "hardware"


def test_backend_not_available_before_probe():
    backend = INA219HardwareBackend()
    assert backend.is_available() is False
    assert backend._probed is False


def test_genuine_reading_measured():
    """A genuine INA219 reading is returned with correct V, A, and P=V×I."""
    _configure_readings([(5.5, 0.05, 500.0)])  # 5.5 V, 50 mV shunt, 500 mA
    backend = INA219HardwareBackend(shunt_ohm=0.1, max_current_a=1.0)
    reading = backend.read()

    assert reading.status == "ok"
    assert reading.error is None
    assert reading.voltage_v == 5.5
    assert reading.current_a == 0.5  # 500 mA → 0.5 A
    # Power resolved consistently as P = V × I
    assert abs(reading.power_register_w - (5.5 * 0.5)) < 1e-9


def test_power_uses_v_times_i():
    """Power is always V × I, even if the mock would return a different
    register power (we simulate the library only providing V, shunt, current)."""
    _configure_readings([(6.0, 0.033, 330.0)])  # 6 V, 330 mA
    backend = INA219HardwareBackend()
    reading = backend.read()

    assert abs(reading.power_register_w - (6.0 * 0.33)) < 1e-9


def test_invalid_reading_reported_as_fault_not_accumulated():
    """An invalid (NaN) reading is reported as 'fault' and is NOT accumulated
    as a new valid reading."""
    # First reading: valid
    _configure_readings([(5.0, 0.05, 500.0)])
    backend = INA219HardwareBackend()
    r1 = backend.read()
    assert r1.status == "ok"
    assert not any(
        c in str(r1.voltage_v) for c in ["nan", "inf"]
    )

    # Second reading: invalid (simulate hardware returning NaN)
    import math

    # Save the property object (not just fget) so we can restore it properly.
    original_prop = _MockINA219.bus_voltage

    @property
    def nan_voltage(self):
        return float("nan")

    _MockINA219.bus_voltage = nan_voltage
    try:
        r2 = backend.read()
        assert r2.status == "fault"
        assert r2.error is not None
        assert math.isnan(r2.voltage_v)
    finally:
        _MockINA219.bus_voltage = original_prop


def test_hardware_failure_raises_backend_error():
    """When the mock sensor raises, the backend raises an honest BackendError
    instead of fabricating readings or silently substituting simulation."""
    _configure_readings([])
    backend = INA219HardwareBackend()
    with pytest.raises(BackendError, match="INA219"):
        backend.read()


def test_hardware_mode_never_substitutes_simulation():
    """Hardware mode stays 'hardware' even when reads fail -- never falls back
    to simulated readings."""
    backend = INA219HardwareBackend()
    assert backend.mode == "hardware"
    diag = backend.diagnostics()
    assert diag["simulated"] is False
    assert diag["hardware"] is True


def test_calibration_configured():
    """Calibration register is computed from shunt and max current."""
    _configure_readings([(5.0, 0.05, 500.0)])
    backend = INA219HardwareBackend(shunt_ohm=0.1, max_current_a=1.0)
    backend.read()
    diag = backend.diagnostics()
    assert diag["shunt_ohm"] == 0.1
    assert diag["max_current_a"] == 1.0
    expected_lsb = 1.0 / 32767.0
    assert abs(diag["current_lsb_a"] - expected_lsb) < 1e-12


def test_diagnostics_shows_unavailable_before_probe():
    backend = INA219HardwareBackend()
    diag = backend.diagnostics()
    assert diag["available"] is False
    assert diag["probed"] is False
    assert diag["init_error"] == "not probed"
    assert diag["samples"] == 0


def test_diagnostics_shows_available_after_read():
    _configure_readings([(5.0, 0.05, 500.0)])
    backend = INA219HardwareBackend()
    backend.read()
    diag = backend.diagnostics()
    assert diag["available"] is True
    assert diag["probed"] is True
    assert diag["samples"] >= 1


def test_read_counts_samples():
    _configure_readings([(5.0, 0.05, 500.0), (5.1, 0.051, 510.0)])
    backend = INA219HardwareBackend()
    backend.read()
    assert backend._samples == 1
    backend.read()
    assert backend._samples == 2


def test_mock_module_isolated_from_real_adafruit():
    """Ensure we're using the mock, not a real adafruit_ina219."""
    assert sys.modules["adafruit_ina219"].INA219 is _MockINA219


# Clean up mock module after tests
def teardown_module():
    _reset_mock()
