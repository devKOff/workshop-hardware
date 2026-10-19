"""Data access: measurements, sessions, integration state, settings."""

from __future__ import annotations

from datetime import datetime, timezone

from solar_monitor.core.energy import IntegrationState

SQL_INSERT_MEASUREMENT = """
    INSERT INTO measurements
    (session_id, timestamp, voltage_v, current_ma, current_a, power_w,
     energy_wh_increment, daily_energy_wh, total_energy_wh,
     sensor_mode, sensor_status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(conn, name="default", sensor_mode="simulated"):
    cur = conn.execute(
        "INSERT INTO sessions(name, started_at, sensor_mode) VALUES (?, ?, ?)",
        (name, now_iso(), sensor_mode),
    )
    return int(cur.lastrowid)


def end_session(conn, session_id):
    conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (now_iso(), session_id))


def insert_measurement(conn, session_id, m, energy_increment_wh=None,
                       daily_energy_wh=None, total_energy_wh=None):
    cur = conn.execute(SQL_INSERT_MEASUREMENT, (
        session_id, m.timestamp, m.voltage_v, m.current_ma, m.current_a, m.power_w,
        energy_increment_wh, daily_energy_wh, total_energy_wh,
        m.sensor_mode, m.sensor_status,
    ))
    conn.execute("UPDATE sessions SET sample_count = sample_count + 1 WHERE id = ?", (session_id,))
    return int(cur.lastrowid)


def update_integration_state(conn, state):
    conn.execute(
        """
        INSERT INTO integration_state
        (id, total_energy_wh, daily_energy_wh, last_timestamp, last_power_w,
         last_day, gaps_skipped, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            total_energy_wh = excluded.total_energy_wh,
            daily_energy_wh = excluded.daily_energy_wh,
            last_timestamp = excluded.last_timestamp,
            last_power_w = excluded.last_power_w,
            last_day = excluded.last_day,
            gaps_skipped = excluded.gaps_skipped,
            updated_at = excluded.updated_at
        """,
        (state.total_energy_wh, state.daily_energy_wh, state.last_timestamp,
         state.last_power_w, state.last_day, state.gaps_skipped, now_iso()),
    )


def get_integration_state(conn):
    row = conn.execute(
        "SELECT total_energy_wh, daily_energy_wh, last_timestamp, last_power_w, "
        "last_day, gaps_skipped FROM integration_state WHERE id = 1"
    ).fetchone()
    if row is None:
        return IntegrationState()
    return IntegrationState(
        total_energy_wh=row["total_energy_wh"],
        daily_energy_wh=row["daily_energy_wh"],
        last_timestamp=row["last_timestamp"],
        last_power_w=row["last_power_w"],
        last_day=row["last_day"],
        gaps_skipped=row["gaps_skipped"],
    )


def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row is not None else default


def set_setting(conn, key, value):
    conn.execute(
        """
        INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, str(value), now_iso()),
    )


def list_sessions(conn, limit=50):
    return conn.execute(
        "SELECT id, name, started_at, ended_at, sensor_mode, sample_count "
        "FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
    ).fetchall()


def session_exists(conn, session_id):
    return conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone() is not None


def list_measurements(conn, session_id=None, start=None, end=None, limit=1000):
    """Return measurement rows, newest first, optionally filtered by session
    and/or timestamp range (inclusive ISO-8601 strings)."""
    sql = """
        SELECT m.id, m.session_id, m.timestamp, m.voltage_v, m.current_ma,
               m.current_a, m.power_w, m.energy_wh_increment, m.daily_energy_wh,
               m.total_energy_wh, m.sensor_mode, m.sensor_status
        FROM measurements m
    """
    params = []
    clauses = []
    if session_id is not None:
        clauses.append("m.session_id = ?")
        params.append(session_id)
    if start is not None:
        clauses.append("m.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("m.timestamp <= ?")
        params.append(end)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY m.timestamp DESC LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def list_sessions_with_counts(conn, limit=50):
    return list_sessions(conn, limit=limit)

