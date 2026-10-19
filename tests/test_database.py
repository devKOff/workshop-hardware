"""Tests for the database connection, schema and DAO."""
from __future__ import annotations

import os
import tempfile

import pytest

from database.connection import open_db, DatabaseError, transaction
from database.schema import init_schema, schema_version, SCHEMA_VERSION
from database import dao
from measurement.model import Measurement


def test_open_creates_and_initializes():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.db")
        conn = open_db(path)
        try:
            assert schema_version(conn) == SCHEMA_VERSION
            names = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            for t in ("sessions", "measurements", "integration_state", "settings"):
                assert t in names
        finally:
            conn.close()


def test_wal_mode():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "wal.db")
        conn = open_db(path)
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode.lower() == "wal"
        finally:
            conn.close()


def test_foreign_keys_on():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "fk.db")
        conn = open_db(path)
        try:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()


def test_rollback_on_error():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "tx.db")
        conn = open_db(path)
        try:
            session_id = dao.create_session(conn, "s1", "simulated")
            m = Measurement(
                timestamp="2026-01-01T00:00:00+00:00", voltage_v=5.0, current_ma=100.0,
                current_a=0.1, power_w=0.5, sensor_mode="simulated", sensor_status="ok",
            )
            try:
                with transaction(conn):
                    dao.insert_measurement(conn, session_id, m)
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
            count = conn.execute(
                "SELECT COUNT(*) FROM measurements WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
            assert count == 0
        finally:
            conn.close()


def test_open_corrupt_db_raises():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "corrupt.db")
        with open(path, "wb") as f:
            f.write(b"not a sqlite database")
        with pytest.raises(DatabaseError):
            open_db(path)