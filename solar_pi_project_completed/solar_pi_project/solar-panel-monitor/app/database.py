"""SQLite persistence for measurements and energy summaries.

All public operations are serialized with a threading lock so the background
sampler thread and Flask request threads can share a single SQLite connection
safely (SQLite connections are not thread-safe for concurrent execution).
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from typing import List, Optional

from app.models import DailyEnergy, EnergySummary, Measurement


class DatabaseError(RuntimeError):
    """Raised on database access failures."""


class Database:
    """Thin wrapper around SQLite for the solar monitor."""

    def __init__(self, path: str = "solar_monitor.db") -> None:
        self.path = path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self.init_db()

    # ------------------------------------------------------------------ #
    # Connection handling
    # ------------------------------------------------------------------ #
    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            try:
                self._conn = sqlite3.connect(self.path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA foreign_keys=ON")
            except sqlite3.Error as exc:
                raise DatabaseError(f"Cannot open database '{self.path}': {exc}") from exc
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                finally:
                    self._conn = None

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #
    def init_db(self) -> None:
        """Create tables if they do not already exist."""
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS measurements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        voltage_v REAL NOT NULL,
                        current_ma REAL NOT NULL,
                        power_w REAL NOT NULL,
                        shunt_voltage_mv REAL,
                        bus_voltage_v REAL,
                        load_voltage_v REAL,
                        sensor_ok INTEGER NOT NULL DEFAULT 1,
                        error_message TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );

                    CREATE TABLE IF NOT EXISTS daily_summaries (
                        date TEXT NOT NULL,
                        energy_wh REAL NOT NULL DEFAULT 0,
                        min_power_w REAL,
                        max_power_w REAL,
                        avg_power_w REAL,
                        sample_count INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                        PRIMARY KEY (date)
                    );

                    CREATE INDEX IF NOT EXISTS idx_measurements_timestamp
                        ON measurements(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_measurements_sensor_ok
                        ON measurements(sensor_ok);
                    """
                )
                conn.commit()
            except sqlite3.Error as exc:
                raise DatabaseError(f"Failed to initialise database: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #
    def insert_measurement(self, measurement: Measurement) -> int:
        """Insert a measurement and return its new row id."""
        with self._lock:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO measurements
                        (timestamp, voltage_v, current_ma, power_w, shunt_voltage_mv,
                         bus_voltage_v, load_voltage_v, sensor_ok, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        measurement.timestamp.isoformat(),
                        measurement.voltage_v,
                        measurement.current_ma,
                        measurement.power_w,
                        measurement.shunt_voltage_mv,
                        measurement.bus_voltage_v,
                        measurement.load_voltage_v,
                        1 if measurement.sensor_ok else 0,
                        measurement.error_message,
                    ),
                )
                conn.commit()
                return int(cursor.lastrowid)
            except sqlite3.Error as exc:
                raise DatabaseError(f"Failed to insert measurement: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    def get_latest(self) -> Optional[Measurement]:
        """Return the most recent measurement, or None."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    """
                    SELECT timestamp, voltage_v, current_ma, power_w, shunt_voltage_mv,
                           bus_voltage_v, load_voltage_v, sensor_ok, error_message
                    FROM measurements
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ).fetchone()
                return self._row_to_measurement(row) if row else None
            except sqlite3.Error as exc:
                raise DatabaseError(f"Failed to read latest measurement: {exc}") from exc

    def get_measurements(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Measurement]:
        """Return measurements within [start, end], oldest first."""
        with self._lock:
            conn = self._connect()
            query = (
                "SELECT timestamp, voltage_v, current_ma, power_w, shunt_voltage_mv, "
                "bus_voltage_v, load_voltage_v, sensor_ok, error_message "
                "FROM measurements WHERE 1=1"
            )
            params: List = []
            if start is not None:
                query += " AND timestamp >= ?"
                params.append(start.isoformat())
            if end is not None:
                query += " AND timestamp <= ?"
                params.append(end.isoformat())
            query += " ORDER BY id ASC"
            if limit is not None:
                query += " LIMIT ?"
                params.append(int(limit))

            try:
                rows = conn.execute(query, params).fetchall()
                return [self._row_to_measurement(row) for row in rows]
            except sqlite3.Error as exc:
                raise DatabaseError(f"Failed to read measurements: {exc}") from exc

    def get_measurement_count(self) -> int:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute("SELECT COUNT(*) AS c FROM measurements").fetchone()
                return int(row["c"]) if row else 0
            except sqlite3.Error as exc:
                raise DatabaseError(f"Failed to count measurements: {exc}") from exc

    def upsert_daily_summary(self, summary: DailyEnergy) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO daily_summaries
                        (date, energy_wh, min_power_w, max_power_w, avg_power_w,
                         sample_count, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(date) DO UPDATE SET
                        energy_wh = excluded.energy_wh,
                        min_power_w = excluded.min_power_w,
                        max_power_w = excluded.max_power_w,
                        avg_power_w = excluded.avg_power_w,
                        sample_count = excluded.sample_count,
                        updated_at = datetime('now')
                    """,
                    (
                        summary.date,
                        summary.energy_wh,
                        summary.min_power_w,
                        summary.max_power_w,
                        summary.avg_power_w,
                        summary.sample_count,
                    ),
                )
                conn.commit()
            except sqlite3.Error as exc:
                raise DatabaseError(f"Failed to upsert daily summary: {exc}") from exc

    def get_daily_summaries(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[DailyEnergy]:
        with self._lock:
            conn = self._connect()
            query = (
                "SELECT date, energy_wh, min_power_w, max_power_w, avg_power_w, "
                "sample_count FROM daily_summaries WHERE 1=1"
            )
            params: List = []
            if start_date is not None:
                query += " AND date >= ?"
                params.append(start_date)
            if end_date is not None:
                query += " AND date <= ?"
                params.append(end_date)
            query += " ORDER BY date ASC"

            try:
                rows = conn.execute(query, params).fetchall()
                return [
                    DailyEnergy(
                        date=row["date"],
                        energy_wh=row["energy_wh"],
                        min_power_w=row["min_power_w"],
                        max_power_w=row["max_power_w"],
                        avg_power_w=row["avg_power_w"],
                        sample_count=row["sample_count"],
                    )
                    for row in rows
                ]
            except sqlite3.Error as exc:
                raise DatabaseError(f"Failed to read daily summaries: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _row_to_measurement(row: sqlite3.Row) -> Measurement:
        from datetime import datetime as _dt

        return Measurement(
            timestamp=_dt.fromisoformat(row["timestamp"]),
            voltage_v=row["voltage_v"],
            current_ma=row["current_ma"],
            current_a=row["current_ma"] / 1000.0,
            power_w=row["power_w"],
            shunt_voltage_mv=row["shunt_voltage_mv"],
            bus_voltage_v=row["bus_voltage_v"],
            load_voltage_v=row["load_voltage_v"],
            sensor_ok=bool(row["sensor_ok"]),
            error_message=row["error_message"],
        )

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
