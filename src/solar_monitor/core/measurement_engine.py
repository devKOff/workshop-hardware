"""Measurement engine: safe background acquisition, validation, power, energy.

The acquisition loop runs on a Python ``threading.Thread`` (never the GUI
thread) using a blocking ``time.sleep`` loop; the GUI thread runs a QTimer
that polls a thread-safe queue and emits Qt signals. Power is always resolved
consistently as P = V x I. Energy uses trapezoidal integration and never
accumulates from invalid readings. The backend is fixed at construction time
-- hardware mode never silently substitutes simulation.

All database access happens on the worker thread. The GUI thread only
receives signals and polls the queue. Stop/pause/resume are thread-safe
flags checked by the worker loop, so shutdown is deterministic.
"""

from __future__ import annotations

import math
import queue
import sqlite3
import threading
import time
from enum import Enum
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from solar_monitor.backends.interface import BackendError, SensorBackend, SensorReading
from solar_monitor.core.config import SAMPLING_INTERVAL_SECONDS
from solar_monitor.core.energy import EnergyIntegrator
from solar_monitor.core.measurement import Measurement
from solar_monitor.core.power import attach_power
from solar_monitor.core.validation import validate_reading
from solar_monitor.database.connection import open_db
from solar_monitor.database.dao import (
    create_session,
    end_session,
    get_integration_state,
    insert_measurement,
    update_integration_state,
)


class EngineState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class _MeasurementWorker(threading.Thread):
    """Blocking acquisition loop on a background threading.Thread.

    All database access and backend reads happen on this thread; the GUI
    thread only receives signals via the queue poller.
    """

    def __init__(self, backend: SensorBackend, db_path: str, interval_s: float):
        super().__init__(daemon=True)
        self.name = "solar-monitor-acquisition"
        self._backend = backend
        self._db_path = db_path
        self._interval_s = interval_s
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._conn = None
        self._session_id: Optional[int] = None
        self._integrator: Optional[EnergyIntegrator] = None
        self._paused = False
        self._stop_requested = False
        self._lock = threading.Lock()

    # -- thread-safe controls ----------------------------------------------
    def set_interval(self, seconds: float):
        with self._lock:
            self._interval_s = seconds

    def request_pause(self):
        with self._lock:
            self._paused = True

    def request_resume(self):
        with self._lock:
            self._paused = False

    def request_stop(self):
        with self._lock:
            self._stop_requested = True

    def _state(self):
        with self._lock:
            return self._paused, self._stop_requested, self._interval_s

    def queue(self) -> "queue.Queue":
        return self._queue

    def run(self):
        """Blocking acquisition loop."""
        try:
            self._conn = open_db(self._db_path)
            self._session_id = create_session(
                self._conn, name="live", sensor_mode=self._backend.mode
            )
            state = get_integration_state(self._conn)
            self._integrator = EnergyIntegrator(
                sampling_interval_s=self._interval_s, state=state
            )
            self._queue.put(("started", self._session_id))

            while True:
                paused, stop_requested, interval_s = self._state()
                if stop_requested:
                    break
                if not paused:
                    self._tick()
                time.sleep(max(0.05, interval_s))
        finally:
            if self._session_id is not None and self._conn is not None:
                try:
                    end_session(self._conn, self._session_id)
                except Exception:  # noqa: BLE001
                    pass
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:  # noqa: BLE001
                    pass
            self._queue.put(("stopped",))

    def _tick(self):
        try:
            reading = self._backend.read()
        except BackendError as exc:
            self._queue.put(("backend_error", str(exc)))
            self._record_fault(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self._queue.put(("backend_error", f"unexpected read error: {exc}"))
            self._record_fault(f"unexpected: {exc}")
            return

        if reading.status == "fault" or not _is_valid_reading(reading):
            self._queue.put(("error", "sensor", reading.error or "invalid reading"))
            self._record_fault(reading.error or "invalid reading")
            return

        try:
            m = validate_reading(
                reading.voltage_v,
                reading.current_a,
                reading.power_register_w,
                mode=reading.mode,
                status=reading.status,
            )
        except ValueError as exc:
            self._queue.put(("error", "validation", f"validation failed: {exc}"))
            return

        # Resolve power consistently as P = V x I
        m = attach_power(m, reading.power_register_w)

        # Energy integration (trapezoidal) -- never from invalid readings.
        increment_wh = None
        total_energy_wh = 0.0
        daily_energy_wh = None
        if self._integrator is not None:
            increment_wh = self._integrator.add(m.timestamp, m.power_w)
            total_energy_wh = self._integrator.state.total_energy_wh
            daily_energy_wh = self._integrator.state.daily_energy_wh

        try:
            insert_measurement(
                self._conn,
                self._session_id,
                m,
                energy_increment_wh=increment_wh,
                daily_energy_wh=daily_energy_wh,
                total_energy_wh=total_energy_wh,
            )
            if self._integrator is not None:
                update_integration_state(self._conn, self._integrator.state)
        except sqlite3.DatabaseError as exc:
            self._queue.put(("error", "database", f"Database write failed: {exc}"))
            return

        self._queue.put(("measurement", m, increment_wh, total_energy_wh))

    def _record_fault(self, reason: str):
        """Record a fault reading without accumulating energy.

        Also breaks the energy integration chain so a later valid reading
        restarts from zero instead of accumulating across the fault gap.
        """
        try:
            m = validate_reading(
                float("nan"), float("nan"), None,
                mode=self._backend.mode, status="fault",
            )
            insert_measurement(self._conn, self._session_id, m)
            if self._integrator is not None:
                # Non-finite power resets the chain (EnergyIntegrator.add).
                self._integrator.add(m.timestamp, float("nan"))
                update_integration_state(self._conn, self._integrator.state)
        except Exception:  # noqa: BLE001 - best effort fault record
            pass


def _is_valid_reading(reading: SensorReading) -> bool:
    return (
        reading is not None
        and math.isfinite(reading.voltage_v)
        and math.isfinite(reading.current_a)
        and reading.voltage_v >= 0
    )


class MeasurementEngine(QObject):
    """Controls acquisition lifecycle; runs the worker off the GUI thread.

    A GUI-thread QTimer polls the worker queue and emits Qt signals, so the
    GUI thread never touches the sqlite connection or the backend.
    """

    started = Signal(str)  # session id
    stopped = Signal()
    paused = Signal()
    resumed = Signal()
    measurement_taken = Signal(object, object, object)  # Measurement, increment_wh|None, total_energy_wh
    error_occurred = Signal(str, str)  # context, message
    status_changed = Signal(str)
    backend_error = Signal(str)  # diagnostic message (hardware unavailable, etc.)

    def __init__(self, backend: SensorBackend, db_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._db_path = db_path
        self._worker: Optional[_MeasurementWorker] = None
        self._state = EngineState.IDLE
        self._interval_s = SAMPLING_INTERVAL_SECONDS
        self._shutting_down = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(50)  # poll the queue every 50 ms
        self._poll_timer.setSingleShot(False)
        self._poll_timer.timeout.connect(self._poll_queue)
        self._poll_timer.start()

    # -- read-only properties ------------------------------------------------
    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def backend_mode(self) -> str:
        return self._backend.mode

    @property
    def sampling_interval_s(self) -> float:
        return self._interval_s

    # -- lifecycle -----------------------------------------------------------
    def set_sampling_interval(self, seconds: float):
        if seconds <= 0:
            raise ValueError("sampling interval must be > 0")
        self._interval_s = seconds
        if self._worker is not None:
            self._worker.set_interval(seconds)

    def start(self):
        """Start acquisition. No-op if already running or paused (no duplicate worker)."""
        if self._state in (EngineState.RUNNING, EngineState.PAUSED):
            return
        if self._shutting_down:
            return
        self._state = EngineState.RUNNING
        self._worker = _MeasurementWorker(self._backend, self._db_path, self._interval_s)
        self._worker.start()

    def _poll_queue(self):
        """Runs on the GUI thread: drain the worker queue and emit signals."""
        if self._worker is None:
            return
        q = self._worker.queue()
        drained = 0
        while drained < 200:
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            drained += 1
            kind = item[0]
            if kind == "started":
                self._session_id = item[1]
                self.started.emit(str(item[1]))
                self.status_changed.emit(f"Acquisition started ({self._backend.mode})")
            elif kind == "stopped":
                self._state = EngineState.IDLE
                self._worker = None
                self.stopped.emit()
                self.status_changed.emit("Acquisition stopped")
            elif kind == "measurement":
                _, m, increment_wh, total_energy_wh = item
                self.measurement_taken.emit(m, increment_wh, total_energy_wh)
            elif kind == "error":
                _, context, message = item
                self.error_occurred.emit(context, message)
            elif kind == "backend_error":
                _, message = item
                self.backend_error.emit(message)

    def _on_measurement(self, m, increment_wh, total_energy_wh):
        self.measurement_taken.emit(m, increment_wh, total_energy_wh)

    def stop(self):
        """Stop acquisition and end the session. Safe to call when idle."""
        if self._worker is None:
            self._state = EngineState.IDLE
            return
        self._state = EngineState.STOPPED
        self._worker.request_stop()
        self._worker.join(timeout=10.0)

    def pause(self):
        """Pause sampling (recording state preserved, loop skips readings)."""
        if self._state != EngineState.RUNNING or self._worker is None:
            return
        self._state = EngineState.PAUSED
        self._worker.request_pause()
        self.paused.emit()
        self.status_changed.emit("Acquisition paused")

    def resume(self):
        """Resume sampling after a pause."""
        if self._state != EngineState.PAUSED or self._worker is None:
            return
        self._state = EngineState.RUNNING
        self._worker.request_resume()
        self.resumed.emit()
        self.status_changed.emit("Acquisition resumed")

    def shutdown(self):
        """Unsafe-shutdown guard: stop acquisition and refuse further starts."""
        self._shutting_down = True
        self.stop()
