"""SQLite schema: measurements, sessions, integration state, settings.

Schema version is tracked via PRAGMA user_version so migrations can be
applied deterministically on top of an existing database.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

SCHEMA_VERSION = 1

DDL = [
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL DEFAULT 'default',
        started_at TEXT NOT NULL,
        ended_at TEXT,
        sensor_mode TEXT NOT NULL,
        sample_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        voltage_v REAL NOT NULL,
        current_ma REAL NOT NULL,
        current_a REAL NOT NULL,
        power_w REAL NOT NULL,
        energy_wh_increment REAL,
        daily_energy_wh REAL,
        total_energy_wh REAL,
        sensor_mode TEXT NOT NULL,
        sensor_status TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_measurements_timestamp ON measurements(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_measurements_session ON measurements(session_id)",
    """
    CREATE TABLE IF NOT EXISTS integration_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        total_energy_wh REAL NOT NULL DEFAULT 0.0,
        daily_energy_wh REAL NOT NULL DEFAULT 0.0,
        last_timestamp TEXT,
        last_power_w REAL,
        last_day TEXT,
        gaps_skipped INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
]

PRAGMA_STATEMENTS = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
]

# Future schema migrations keyed by target version. Each value is a list of
# SQL statements applied in order when upgrading to that version.
MIGRATIONS: dict[int, list[str]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables (if missing), set pragmas, and record the schema version."""
    with conn:
        for pragma in PRAGMA_STATEMENTS:
            conn.execute(pragma)
        for statement in DDL:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO settings(key, value, updated_at) VALUES(?, ?, ?)"
            " ON CONFLICT(key) DO NOTHING",
            ("schema_version", str(SCHEMA_VERSION), _now_iso()),
        )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Apply pending schema migrations up to SCHEMA_VERSION.

    No-op when the database is already at (or beyond) the current version.
    """
    current = schema_version(conn)
    if current >= SCHEMA_VERSION:
        return
    for version in range(current + 1, SCHEMA_VERSION + 1):
        for statement in MIGRATIONS.get(version, []):
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()
