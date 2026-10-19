"""SQLite storage for solar readings.

Schema (all tables created automatically on first use):

readings
  id             INTEGER PRIMARY KEY AUTOINCREMENT
  timestamp      TEXT            ISO 8601 local time (YYYY-MM-DDTHH:MM:SS)
  bus_voltage_v  REAL           panel bus voltage (V); NULL on failed sample
  shunt_voltage_v REAL          shunt voltage (V); NULL on failed sample
  current_ma     REAL           current (mA, signed); NULL on failed sample
  power_mw       REAL           instantaneous power (mW, signed); NULL on failed
  energy_wh      REAL           cumulative energy (Wh) at this sample
  ok             INTEGER        1 = valid sample, 0 = sensor error
  error          TEXT           failure reason when ok = 0

daily_totals
  day            TEXT PRIMARY KEY  YYYY-MM-DD (local date)
  energy_wh      REAL              energy generated that day (Wh)
  updated_at     TEXT              last update timestamp

meta
  key            TEXT PRIMARY KEY
  value          TEXT              e.g. cumulative_wh_offset (restart-safe)

Design notes for a student project:
- Every sample is stored, including failed ones (ok=0), so gaps in the data
  are visible instead of silently fabricated.
- Cumulative energy is persisted in meta.cumulative_wh_offset. When the app
  restarts it loads that value and continues integrating from it, so energy
  is never reset to zero or double-counted after a restart.
- Daily totals are kept in a separate table and reset at local midnight by
  energy_tracker.py. Historical daily rows are never deleted.
- A threading lock serializes writes from the background sampling thread.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import threading
from datetime import datetime
from typing import Optional

from .config import DB_PATH
from .ina219_reader import Reading


class Database:
    def __init__(self, path: str = DB_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS readings (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TEXT NOT NULL,
                    bus_voltage_v   REAL,
                    shunt_voltage_v REAL,
                    current_ma      REAL,
                    power_mw        REAL,
                    energy_wh       REAL,
                    ok              INTEGER NOT NULL DEFAULT 1,
                    error           TEXT
                );
                CREATE TABLE IF NOT EXISTS daily_totals (
                    day        TEXT PRIMARY KEY,
                    energy_wh  REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_readings_ts
                    ON readings(timestamp);
                """
            )
            # Seed the restart-safe cumulative energy offset if missing.
            cur = conn.execute(
                "SELECT value FROM meta WHERE key = 'cumulative_wh_offset'"
            )
            if cur.fetchone() is None:
                conn.execute(
                    "INSERT INTO meta(key, value) VALUES ('cumulative_wh_offset', '0')"
                )

    # ------------------------------------------------------------------ writes

    def insert_reading(self, r: Reading, energy_wh: float) -> None:
        """Store one sample (valid or failed) together with cumulative energy."""
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO readings
                        (timestamp, bus_voltage_v, shunt_voltage_v, current_ma,
                         power_mw, energy_wh, ok, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.timestamp,
                        r.bus_voltage_v,
                        r.shunt_voltage_v,
                        r.current_ma,
                        r.power_mw,
                        energy_wh,
                        1 if r.ok else 0,
                        r.error or "",
                    ),
                )

    def upsert_daily(self, day: str, energy_wh: float) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_totals(day, energy_wh, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    energy_wh = excluded.energy_wh,
                    updated_at = excluded.updated_at
                """,
                (day, energy_wh, datetime.now().isoformat(timespec="seconds")),
            )

    def set_offset(self, value: float) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO meta(key, value) VALUES ('cumulative_wh_offset', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (f"{value:.6f}",),
            )

    # ------------------------------------------------------------------ reads

    def latest(self) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM readings ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def cumulative_offset(self) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'cumulative_wh_offset'"
            ).fetchone()
            return float(row["value"]) if row else 0.0

    def history(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 2000,
    ):
        """Return valid readings ordered newest first, optionally time-filtered."""
        with self._connect() as conn:
            q = "SELECT * FROM readings WHERE ok = 1"
            params: list = []
            if start:
                q += " AND timestamp >= ?"
                params.append(start)
            if end:
                q += " AND timestamp <= ?"
                params.append(end)
            q += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]

    def daily_totals(self, days: int = 30):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_totals ORDER BY day DESC LIMIT ?",
                (days,),
            ).fetchall()
            return [dict(r) for r in rows]

    def export_csv(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> str:
        """Return CSV text of valid readings (newest first)."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "timestamp",
                "bus_voltage_v",
                "shunt_voltage_v",
                "current_ma",
                "power_mw",
                "energy_wh",
                "ok",
                "error",
            ]
        )
        for row in self.history(start=start, end=end, limit=CSV_EXPORT_LIMIT):
            writer.writerow(
                [
                    row["timestamp"],
                    row["bus_voltage_v"],
                    row["shunt_voltage_v"],
                    row["current_ma"],
                    row["power_mw"],
                    row["energy_wh"],
                    row["ok"],
                    row["error"] or "",
                ]
            )
        return output.getvalue()
