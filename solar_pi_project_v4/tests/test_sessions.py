"""Tests for sessions and measurement persistence."""
from __future__ import annotations

import os
import tempfile

from measurement.model import Measurement
from database.connection import open_db
from database import dao


def _m() -> Measurement:
    return Measurement(
        timestamp="2026-01-01T00:00:00+00:00", voltage_v=5.0, current_ma=100.0,
        current_a=0.1, power_w=0.5, sensor_mode="simulated", sensor_status="ok",
    )


def test_create_and_end_session():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "s.db")
        conn = open_db(path)
        try:
            sid = dao.create_session(conn, "sess1", "simulated")
            assert sid > 0
            assert dao.session_exists(conn, sid) is True
            assert dao.session_exists(conn, 99999) is False
            dao.end_session(conn, sid)
            row = conn.execute("SELECT ended_at FROM sessions WHERE id = ?", (sid,)).fetchone()
            assert row["ended_at"] is not None
        finally:
            conn.close()


def test_insert_measurement_and_counts():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "m.db")
        conn = open_db(path)
        try:
            sid = dao.create_session(conn, "sess1", "simulated")
            dao.insert_measurement(conn, sid, _m())
            dao.insert_measurement(conn, sid, _m())
            row = conn.execute("SELECT sample_count FROM sessions WHERE id = ?", (sid,)).fetchone()
            assert row["sample_count"] == 2
            count = conn.execute(
                "SELECT COUNT(*) FROM measurements WHERE session_id = ?", (sid,)
            ).fetchone()[0]
            assert count == 2
        finally:
            conn.close()


def test_indexes_exist():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "idx.db")
        conn = open_db(path)
        try:
            names = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()}
            assert any("measurements_timestamp" in n for n in names)
            assert any("measurements_session" in n for n in names)
        finally:
            conn.close()