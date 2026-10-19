"""Tests for src/solar_monitor/core/measurement_engine.

Runs under the offscreen Qt platform (conftest). The engine drives a QThread
worker; signals are pumped with QTest.qWait (processes events while waiting
on real time).
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from solar_monitor.backends.interface import SensorBackend, SensorReading
from solar_monitor.core.measurement_engine import EngineState, MeasurementEngine
from solar_monitor.core.validation import validate_reading


def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_QAPP = _qapp()


class _FakeBackend(SensorBackend):
    """Deterministic fake backend emitting a fixed list of SensorReadings."""

    def __init__(self, readings, mode="simulated"):
        self._readings = list(readings)
        self._index = 0
        self._mode = mode

    @property
    def mode(self):
        return self._mode

    def is_available(self):
        return True

    def read(self):
        r = self._readings[self._index % len(self._readings)]
        self._index += 1
        return r

    def diagnostics(self):
        return {"mode": self.mode}


def _reading(voltage_v, current_a, power_register_w=None, status="ok", error=None):
    from datetime import datetime, timezone
    return SensorReading(
        timestamp=datetime.now(timezone.utc),
        voltage_v=voltage_v,
        current_a=current_a,
        power_register_w=power_register_w,
        mode="simulated",
        status=status,
        error=error,
    )


def _wait_for(cond, timeout_ms=3000):
    """Pump the event loop until cond() is True or timeout_ms elapses."""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        QTest.qWait(50)
        if cond():
            return True
    return cond()


def test_engine_start_stop_lifecycle(tmp_path):
    backend = _FakeBackend([_reading(5.0, 0.1, 0.5)])
    db = str(tmp_path / "engine.db")
    engine = MeasurementEngine(backend, db_path=db)
    assert engine.state == EngineState.IDLE
    assert engine.backend_mode == "simulated"

    started = []
    stopped = []
    engine.started.connect(lambda sid: started.append(sid))
    engine.stopped.connect(lambda: stopped.append(True))

    engine.start()
    assert _wait_for(lambda: len(started) == 1)
    assert engine.state == EngineState.RUNNING

    # Repeated start must not duplicate the worker.
    engine.start()
    QTest.qWait(100)
    assert engine.state == EngineState.RUNNING
    assert len(started) == 1

    engine.stop()
    assert _wait_for(lambda: len(stopped) == 1)
    assert engine.state == EngineState.IDLE


def test_engine_stop_when_idle_is_noop():
    backend = _FakeBackend([_reading(5.0, 0.1, 0.5)])
    engine = MeasurementEngine(backend)
    engine.stop()  # should not raise
    assert engine.state == EngineState.IDLE


def test_engine_pause_resume(tmp_path):
    backend = _FakeBackend([_reading(5.0, 0.1, 0.5)])
    db = str(tmp_path / "engine.db")
    engine = MeasurementEngine(backend, db_path=db)
    engine.start()
    assert _wait_for(lambda: engine.state == EngineState.RUNNING)

    paused = []
    resumed = []
    engine.paused.connect(lambda: paused.append(True))
    engine.resumed.connect(lambda: resumed.append(True))

    engine.pause()
    assert _wait_for(lambda: engine.state == EngineState.PAUSED)
    assert len(paused) == 1

    engine.pause()  # pause while paused is a no-op
    QTest.qWait(100)
    assert len(paused) == 1

    engine.resume()
    assert _wait_for(lambda: engine.state == EngineState.RUNNING)
    assert len(resumed) == 1

    engine.resume()  # resume while running is a no-op
    QTest.qWait(100)
    assert len(resumed) == 1

    engine.stop()
    assert _wait_for(lambda: engine.state == EngineState.IDLE)


def test_engine_measurement_and_energy_known_sequence(tmp_path):
    # Power 0.5 W then 1.0 W -> trapezoid increment = avg_power * delta_s / 3600.
    readings = [
        _reading(5.0, 0.1, 0.5),
        _reading(5.0, 0.2, 1.0),
    ]
    backend = _FakeBackend(readings)
    db = str(tmp_path / "energy.db")
    engine = MeasurementEngine(backend, db_path=db)
    engine.set_sampling_interval(0.05)

    taken = []
    engine.measurement_taken.connect(lambda m, inc, tot: taken.append((m, inc, tot)))
    engine.start()

    assert _wait_for(lambda: len(taken) >= 2, timeout_ms=3000)
    # Trapezoid uses ACTUAL elapsed time between samples (not interval_s).
    from datetime import datetime
    t0 = datetime.fromisoformat(taken[0][0].timestamp)
    t1 = datetime.fromisoformat(taken[1][0].timestamp)
    delta_s = (t1 - t0).total_seconds()
    expected = 0.75 * delta_s / 3600.0  # (0.5+1.0)/2 * delta/3600

    inc = taken[1][1]
    assert inc is not None
    assert abs(inc - expected) < 1e-9, f"expected {expected}, got {inc}"

    engine.stop()
    QTest.qWait(200)
    assert engine.state == EngineState.IDLE


def test_engine_invalid_reading_never_accumulates_energy(tmp_path):
    # Valid, valid, fault, valid: NaN sample must not add energy and breaks
    # the chain so the next valid sample restarts (no increment).
    readings = [
        _reading(5.0, 0.1, 0.5),    # valid -> first, no increment
        _reading(5.0, 0.1, 0.5),    # valid -> increment
        _reading(float("nan"), float("nan"), None, status="fault", error="bad"),  # invalid
        _reading(5.0, 0.1, 0.5),    # valid again -> chain broken, no increment
    ]
    backend = _FakeBackend(readings)
    db = str(tmp_path / "invalid.db")
    engine = MeasurementEngine(backend, db_path=db)
    engine.set_sampling_interval(0.05)

    taken = []
    errors = []
    engine.measurement_taken.connect(lambda m, inc, tot: taken.append((m, inc, tot)))
    engine.error_occurred.connect(lambda c, msg: errors.append((c, msg)))
    engine.start()

    assert _wait_for(lambda: len(taken) >= 3 and len(errors) >= 1, timeout_ms=4000)

    # First valid: no increment. Second valid: increment = 0.5 * actual_delta / 3600.
    assert taken[0][1] is None
    from datetime import datetime
    t0 = datetime.fromisoformat(taken[0][0].timestamp)
    t1 = datetime.fromisoformat(taken[1][0].timestamp)
    delta_s = (t1 - t0).total_seconds()
    assert abs(taken[1][1] - (0.5 * delta_s / 3600.0)) < 1e-9
    # Fault sample is NOT in taken (routed to error signal + DB); surfaced via error signal.
    fault_errors = [e for e in errors if e[0] == "sensor"]
    assert len(fault_errors) >= 1
    # After fault, chain broken: next valid treated as first (no increment).
    assert taken[2][1] is None
    assert taken[2][0].sensor_status == "ok"

    engine.stop()
    QTest.qWait(200)
    assert engine.state == EngineState.IDLE


def test_engine_hardware_backend_unavailable_no_crash(tmp_path):
    """Hardware backend on Windows reports unavailable and raises an honest
    BackendError instead of fabricating readings or silently simulating."""
    from solar_monitor.backends import INA219HardwareBackend

    backend = INA219HardwareBackend()
    assert backend.mode == "hardware"
    assert backend.is_available() is False
    diag = backend.diagnostics()
    assert diag["hardware"] is True
    assert diag["available"] is False
    assert diag["init_error"] is not None

    db = str(tmp_path / "hw.db")
    engine = MeasurementEngine(backend, db_path=db)
    engine.set_sampling_interval(0.05)

    backend_errs = []
    engine.backend_error.connect(lambda msg: backend_errs.append(msg))

    engine.start()
    assert _wait_for(lambda: len(backend_errs) >= 1, timeout_ms=3000)
    assert engine.state == EngineState.RUNNING
    # Engine stays running on hardware mode even though reads fail -- it never
    # silently switches to simulation.
    assert engine.backend_mode == "hardware"
    msg = backend_errs[0].lower()
    assert "ina219" in msg or "unavailable" in msg

    engine.stop()
    QTest.qWait(200)
    assert engine.state == EngineState.IDLE


def test_engine_sampling_interval_validation():
    backend = _FakeBackend([_reading(5.0, 0.1, 0.5)])
    engine = MeasurementEngine(backend)
    with pytest.raises(ValueError):
        engine.set_sampling_interval(0.0)
    with pytest.raises(ValueError):
        engine.set_sampling_interval(-1.0)
    engine.set_sampling_interval(5.0)
    assert engine.sampling_interval_s == 5.0


def test_engine_shutdown_prevents_restart(tmp_path):
    backend = _FakeBackend([_reading(5.0, 0.1, 0.5)])
    db = str(tmp_path / "shutdown.db")
    engine = MeasurementEngine(backend, db_path=db)
    engine.start()
    assert _wait_for(lambda: engine.state == EngineState.RUNNING)
    engine.shutdown()
    assert _wait_for(lambda: engine.state == EngineState.IDLE)
    assert engine._shutting_down is True
    engine.start()  # must be no-op after shutdown
    QTest.qWait(100)
    assert engine.state == EngineState.IDLE
