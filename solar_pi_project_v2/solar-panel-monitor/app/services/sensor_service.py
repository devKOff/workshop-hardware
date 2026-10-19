"""Sensor service: hardware abstraction, background sampling, and status."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from app.config import Config
from app.database import Database
from app.hardware.ina219_sensor import INA219Sensor
from app.hardware.simulated_sensor import SimulatedSensor
from app.models import Measurement, SensorStatus

logger = logging.getLogger("solar_monitor")


class SensorServiceError(RuntimeError):
    """Raised for sensor service operational errors."""


class SensorService:
    """Coordinates a single sensor, a background sampling thread, and persistence.

    Responsibilities:
      * Instantiate the configured sensor (simulation or hardware).
      * Run one background sampling thread at a time (duplicate-start protected).
      * Persist every successful reading to SQLite.
      * Track the latest reading and sensor connection status.
      * Never substitute a failed physical reading with simulated data.
    """

    def __init__(
        self,
        config: Config,
        database: Database,
        sensor: Optional[object] = None,
    ) -> None:
        self.config = config
        self.db = database
        self._sensor = sensor
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._started = False
        self.latest: Optional[Measurement] = None
        self._connected: bool = False
        self._last_error: Optional[str] = None
        self._last_reading_ts: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Sensor construction
    # ------------------------------------------------------------------ #
    def _create_sensor(self) -> object:
        mode = self.config.sensor_mode
        if mode == "simulation":
            return SimulatedSensor()
        if mode == "hardware":
            return INA219Sensor(
                i2c_address=self.config.ina219_i2c_address,
                shunt_ohms=self.config.ina219_shunt_ohms,
                max_expected_amps=self.config.ina219_max_expected_amps,
            )
        raise SensorServiceError(
            f"Unknown sensor mode '{mode}'; use 'simulation' or 'hardware'"
        )

    @property
    def sensor(self) -> object:
        if self._sensor is None:
            self._sensor = self._create_sensor()
        return self._sensor

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start_sampling(self) -> None:
        """Start the background sampling thread.

        Raises SensorServiceError if a thread is already running, protecting
        against accidentally starting multiple sampling threads.
        """
        with self._lock:
            if self.is_running():
                raise SensorServiceError("Sampling thread is already running")
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, name="solar-sampler", daemon=True
            )
            self._thread.start()
            self._started = True
        logger.info("Sampling started (mode=%s, interval=%ss)",
                    self.config.sensor_mode,
                    self.config.sampling_interval_seconds)

    def stop_sampling(self, timeout: float = 5.0) -> None:
        """Request the sampling thread to stop and wait for it to finish."""
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning("Sampling thread did not stop within %ss", timeout)
        logger.info("Sampling stopped")

    def take_reading(self) -> Measurement:
        """Take a single on-demand reading without the background thread."""
        try:
            reading = self.sensor.read()
        except Exception as exc:
            self._record_failure(str(exc))
            raise SensorServiceError(f"Sensor read failed: {exc}") from exc
        self._record_success(reading)
        try:
            self.db.insert_measurement(reading)
        except Exception as exc:
            logger.error("Failed to persist reading: %s", exc)
        return reading

    # ------------------------------------------------------------------ #
    # Background loop
    # ------------------------------------------------------------------ #
    def _run(self) -> None:
        interval = max(float(self.config.sampling_interval_seconds), 0.5)
        while not self._stop_event.is_set():
            try:
                reading = self.sensor.read()
            except Exception as exc:
                # Log but keep running so the sensor can recover. Never
                # substitute simulated data for a failed physical reading.
                self._record_failure(str(exc))
                logger.warning("Sampling read failed: %s", exc)
            else:
                self._record_success(reading)
                try:
                    self.db.insert_measurement(reading)
                except Exception as exc:
                    logger.error("Failed to persist reading: %s", exc)
            # Interruptible sleep so shutdown is prompt.
            self._stop_event.wait(interval)

    # ------------------------------------------------------------------ #
    # Status / helpers
    # ------------------------------------------------------------------ #
    def _record_success(self, reading: Measurement) -> None:
        self.latest = reading
        self._connected = True
        self._last_error = None
        self._last_reading_ts = reading.timestamp.isoformat()

    def _record_failure(self, error_message: str) -> None:
        self._connected = False
        self._last_error = error_message

    def status(self) -> SensorStatus:
        # Recompute connected from the underlying sensor too, so transient
        # hardware disconnections surface even between samples.
        sensor_connected = getattr(self.sensor, "connected", self._connected)
        return SensorStatus(
            connected=self._connected and sensor_connected,
            mode=getattr(self.sensor, "mode", self.config.sensor_mode),
            error_message=self._last_error,
            last_reading_ts=self._last_reading_ts,
        )

    def current_measurement(self) -> Optional[Measurement]:
        return self.latest

    def shutdown(self) -> None:
        self.stop_sampling()
