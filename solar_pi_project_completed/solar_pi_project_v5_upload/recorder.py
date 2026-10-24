"""Session recorder for the Solar Panel Performance Monitor.

Runs ONE background worker thread that samples a sensor, validates each
reading, and stores it in memory. Handles auto-stop at the duration limit,
early stop (partial data kept), and atomic CSV export.

The worker never touches Tk widgets. It enqueues samples on a
``queue.Queue`` for the GUI to drain with ``after()``. Stop is signaled with
a ``threading.Event``.
"""

from __future__ import annotations

import csv
import math
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Queue
from typing import Optional

from sensor import (
    OverflowError,
    OutOfRangeError,
    SensorProtocol,
    ValidationError,
    validate_reading,
)

# Fixed CSV column order.
CSV_COLUMNS = [
    "timestamp",
    "elapsed_s",
    "voltage_v",
    "current_ma",
    "power_w",
    "status",
    "data_source",
]

# Status values.
STATUS_READY = "Ready"
STATUS_MONITORING = "Monitoring"
STATUS_STOPPED = "Stopped"
STATUS_COMPLETED = "Completed"
STATUS_ERROR = "Error"


@dataclass
class SessionConfig:
    duration_s: float = 600.0
    interval_s: float = 1.0


class Recorder:
    """Owns the in-memory session data and the single worker thread."""

    def __init__(self, config: SessionConfig | None = None) -> None:
        self.config = config or SessionConfig()
        self._sensor: Optional[SensorProtocol] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._queue: Queue = Queue()
        self._lock = threading.Lock()

        # Session state (touched by worker under lock; GUI reads it).
        self.status = STATUS_READY
        self.error_message: Optional[str] = None
        self._samples: list = []
        self._start_monotonic: Optional[float] = None
        self._deadline: Optional[float] = None
        self._duration_s: float = 0.0
        self._interval_s: float = 0.0

    # ------------------------------------------------------------------ #
    # Session lifecycle
    # ------------------------------------------------------------------ #
    def has_unexported_data(self) -> bool:
        with self._lock:
            return len(self._samples) > 0

    def sample_count(self) -> int:
        with self._lock:
            return len(self._samples)

    def is_monitoring(self) -> bool:
        return self.status == STATUS_MONITORING and self._thread is not None

    def start(self, sensor: SensorProtocol) -> None:
        """Begin a session. Raises RuntimeError if already running or sensor
        cannot be detected. Never falls back to simulated data on failure."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("A session is already running")
            if not sensor.detect():
                self._sensor = None
                raise RuntimeError(
                    "Sensor not detected. Check wiring and I2C, or choose Simulation."
                )
            self._sensor = sensor
            self._stop_event.clear()
            self._samples = []
            self._start_monotonic = None
            self._deadline = None
            self._duration_s = float(self.config.duration_s)
            self._interval_s = float(self.config.interval_s)
            self.status = STATUS_READY
            self.error_message = None

        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="recorder-worker"
        )
        self._thread.start()

    def stop(self) -> None:
        """Request an early stop. The worker finishes cleanly; partial data
        is kept and remains exportable."""
        self._stop_event.set()

    def _set_status(self, status: str, error: Optional[str] = None) -> None:
        self.status = status
        self.error_message = error

    # ------------------------------------------------------------------ #
    # Worker (runs in the single background thread)
    # ------------------------------------------------------------------ #
    def _worker(self) -> None:
        sensor = self._sensor
        if sensor is None:
            self._set_status(STATUS_ERROR, "No sensor available")
            self._queue.put(None)
            return

        interval = self._interval_s
        duration = self._duration_s
        start = time.monotonic()
        deadline = start + duration
        with self._lock:
            self._start_monotonic = start
            self._deadline = deadline

        self._set_status(STATUS_MONITORING)

        final_status = STATUS_COMPLETED
        try:
            next_sample = start
            while True:
                # Honor an early stop request before anything else.
                if self._stop_event.is_set():
                    final_status = STATUS_STOPPED
                    break

                now = time.monotonic()

                # Auto-stop when the duration deadline is reached.
                if now >= deadline:
                    final_status = STATUS_COMPLETED
                    break

                # Sleep until the next sample time (interruptible by stop).
                sleep_for = next_sample - now
                if sleep_for > 0:
                    woke = self._stop_event.wait(sleep_for)
                    if woke:
                        final_status = STATUS_STOPPED
                        break
                    continue

                # Take a sample (may run slightly late if we drifted behind).
                elapsed = time.monotonic() - start
                sample = self._read_one_sample(sensor, elapsed)
                with self._lock:
                    self._samples.append(sample)
                self._queue.put(sample)

                next_sample += interval
                # Clamp so we never schedule a sample in the distant past.
                if next_sample < time.monotonic():
                    next_sample = time.monotonic() + interval

        except Exception as exc:  # pragma: no cover - defensive
            final_status = STATUS_ERROR
            self._set_status(STATUS_ERROR, f"Sensor read failed: {exc}")
        finally:
            self._set_status(final_status)
            self._queue.put(None)  # sentinel: session ended

    def _read_one_sample(
        self, sensor: SensorProtocol, elapsed: float
    ) -> dict:
        """Read and validate one sample. Never substitutes 0 for a bad
        reading; invalid readings are stored with a status and empty values."""
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            raw = sensor.read_raw()
            reading = validate_reading(
                bus_voltage_v=raw["bus_voltage_v"],
                shunt_voltage_v=raw["shunt_voltage_v"],
                current_ma=raw["current_ma"],
                overflow=bool(raw.get("overflow", False)),
            )
            return {
                "timestamp": timestamp,
                "elapsed_s": round(elapsed, 4),
                "voltage_v": reading.voltage_v,
                "current_ma": reading.current_ma,
                "power_w": reading.power_w,
                "status": "ok",
                "data_source": sensor.data_source,
            }
        except OverflowError:
            return self._invalid_sample(timestamp, elapsed, "overflow", sensor)
        except OutOfRangeError:
            return self._invalid_sample(timestamp, elapsed, "out_of_range", sensor)
        except ValidationError:
            return self._invalid_sample(timestamp, elapsed, "read_error", sensor)
        except Exception:  # pragma: no cover - defensive
            return self._invalid_sample(timestamp, elapsed, "read_error", sensor)

    @staticmethod
    def _invalid_sample(timestamp, elapsed, status, sensor) -> dict:
        return {
            "timestamp": timestamp,
            "elapsed_s": round(elapsed, 4),
            "voltage_v": None,
            "current_ma": None,
            "power_w": None,
            "status": status,
            "data_source": sensor.data_source,
        }

    # ------------------------------------------------------------------ #
    # Queue draining (called by the GUI on the main thread)
    # ------------------------------------------------------------------ #
    def drain_queue(self) -> list:
        """Return all samples currently on the queue (main thread only)."""
        out = []
        while True:
            try:
                item = self._queue.get_nowait()
            except Exception:
                break
            if item is None:
                continue  # session-end sentinel
            out.append(item)
        return out

    # ------------------------------------------------------------------ #
    # Session summary (GUI reads this on the main thread)
    # ------------------------------------------------------------------ #
    def summary(self) -> dict:
        with self._lock:
            count = len(self._samples)
            start = self._start_monotonic
            duration = self._duration_s
        elapsed = 0.0
        remaining = duration
        if start is not None:
            elapsed = time.monotonic() - start
            remaining = max(0.0, duration - elapsed)
        return {
            "status": self.status,
            "error_message": self.error_message,
            "samples_recorded": count,
            "elapsed_s": round(elapsed, 2),
            "time_remaining_s": round(remaining, 2),
        }

    # ------------------------------------------------------------------ #
    # CSV export (atomic: temp file + rename)
    # ------------------------------------------------------------------ #
    def export_csv(self, path: str) -> int:
        """Write the session to ``path`` atomically. Returns the row count.
        Raises on any error (bad path, permission, etc.). Never leaves a
        half-written file behind."""
        with self._lock:
            samples = list(self._samples)
        if not samples:
            raise ValueError("No data to export")

        directory = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp_path = tempfile.mkstemp(
            dir=directory, prefix=".solar_export_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_COLUMNS)
                for s in samples:
                    writer.writerow(
                        [
                            s["timestamp"],
                            s["elapsed_s"],
                            self._fmt(s["voltage_v"]),
                            self._fmt(s["current_ma"]),
                            self._fmt(s["power_w"]),
                            s["status"],
                            s["data_source"],
                        ]
                    )
            os.replace(tmp_path, path)
            return len(samples)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _fmt(value) -> str:
        """Format a float for CSV: ``None``/non-finite -> empty, otherwise a
        plain decimal string with ``.`` separator (never scientific notation)."""
        if value is None:
            return ""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return ""
        if not math.isfinite(v):
            return ""
        return f"{v:.4f}".rstrip("0").rstrip(".")

    def close(self) -> None:
        """Stop the worker and drop the sensor reference. Safe to repeat."""
        self.stop()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None
        if self._sensor is not None:
            try:
                self._sensor.close()
            except Exception:
                pass
            self._sensor = None
