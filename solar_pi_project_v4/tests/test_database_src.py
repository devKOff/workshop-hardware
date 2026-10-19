"""Tests for src/solar_monitor/database: app-data path, schema, DAOs, settings, backup."""

from __future__ import annotations

import os
import tempfile

import pytest

from measurement.model import Measurement
from solar_monitor.core.energy import IntegrationState
from solar_monitor.database.backup import BackupError
from solar_monitor.database.connection import DatabaseError, open_db, transaction
from solar_monitor.database.dao import (
    create_session,
    end_session,
    get_integration_state,
    insert_measurement,
    list_sessions,
    session_exists,
    update_integration_state,
)
from solar_monitor.database.paths import app_data_dir, default_db_path, ensure_data_dir
from solar_monitor.database.schema import SCHEMA_VERSION, init_schema, migrate_schema, schema_version
from solar_monitor.database.settings import SettingsError, SettingsService


def test_default_db_path_is_in_app_data_not_cwd():
    path = default_db_path()
    assert os.path.isabs(path)
    assert os.path.basename(path) == "solar_measurements.db"
    # Must not be the current working directory.
    assert os.path.dirname(path) != os.getcwd()
    assert app_data_dir() in path


def test_app_data_dir_creates_directory():
    directory = ensure_data_dir()
    assert os.path.isdir(directory)
    assert directory == app_data_dir()


def test_schema_init_and_version(tmp_path):
    db = os.path.join(str(tmp_path), "test.db")
    conn = open_db(db)
    try:
        assert schema_version(conn) == SCHEMA_VERSION
        # idempotent
        init_schema(conn)
        assert schema_version(conn) == SCHEMA_VERSION
    finally:
        conn.close()


def test_migrate_schema_noop_when_current(tmp_path):
    db = os.path.join(str(tmp_path), "test.db")
    conn = open_db(db)
    try:
        migrate_schema(conn)  # should not raise
        assert schema_version(conn) == SCHEMA_VERSION
    finally:
        conn.close()


def test_open_db_default_path_creates_file():
    conn = open_db()  # default app-data path
    try:
        assert schema_version(conn) == SCHEMA_VERSION
        assert os.path.exists(default_db_path())
    finally:
        conn.close()


def test_dao_round_trip(tmp_path):
    db = os.path.join(str(tmp_path), "test.db")
    conn = open_db(db)
    try:
        session_id = create_session(conn, name="phase3", sensor_mode="simulated")
        assert session_exists(conn, session_id)

        m = Measurement(
            "2026-01-01T00:00:00+00:00", 5.5, 166.7, 0.1667, 0.916, "simulated", "ok"
        )
        row_id = insert_measurement(
            conn, session_id, m,
            energy_increment_wh=0.0025, daily_energy_wh=0.0025, total_energy_wh=0.0025,
        )
        assert row_id > 0

        state = IntegrationState(
            total_energy_wh=0.0025, daily_energy_wh=0.0025,
            last_timestamp=m.timestamp, last_power_w=0.916,
            last_day="2026-01-01", gaps_skipped=0,
        )
        update_integration_state(conn, state)
        state2 = get_integration_state(conn)
        assert state2.total_energy_wh == 0.0025
        assert state2.gaps_skipped == 0

        end_session(conn, session_id)
    finally:
        conn.close()


def test_settings_persist(tmp_path):
    db = os.path.join(str(tmp_path), "test.db")
    conn = open_db(db)
    try:
        svc = SettingsService(conn)
        svc.set("sampling_interval_s", 5.0)
        assert svc.get("sampling_interval_s") == 5.0
        svc.set("sensor_mode", "hardware")
        assert svc.get("sensor_mode") == "hardware"

        # invalid value rejected, falls back to default
        with pytest.raises(SettingsError):
            svc.set("sampling_interval_s", -1.0)
        assert svc.get("sampling_interval_s") == 5.0  # unchanged (set failed)
    finally:
        conn.close()


def test_settings_unknown_key_rejected(tmp_path):
    db = os.path.join(str(tmp_path), "test.db")
    conn = open_db(db)
    try:
        svc = SettingsService(conn)
        with pytest.raises(SettingsError):
            svc.set("does_not_exist", "x")
        with pytest.raises(SettingsError):
            svc.get("does_not_exist")
    finally:
        conn.close()


def test_backup_refuses_same_path(tmp_path):
    db = os.path.join(str(tmp_path), "test.db")
    conn = open_db(db)
    conn.close()
    with pytest.raises(BackupError):
        from solar_monitor.database.backup import backup
        backup(db, db)


def test_backup_restore_round_trip(tmp_path):
    db = os.path.join(str(tmp_path), "test.db")
    backup_path = os.path.join(str(tmp_path), "test_backup.db")
    conn = open_db(db)
    create_session(conn, name="backup-test")
    conn.close()

    from solar_monitor.database.backup import backup, restore
    backup(db, backup_path)
    assert os.path.exists(backup_path)

    restored = restore(backup_path, os.path.join(str(tmp_path), "restored.db"))
    conn2 = open_db(restored)
    try:
        assert schema_version(conn2) == SCHEMA_VERSION
    finally:
        conn2.close()


def test_transaction_commits_and_rolls_back(tmp_path):
    db = os.path.join(str(tmp_path), "test.db")
    conn = open_db(db)
    try:
        with transaction(conn):
            create_session(conn, name="tx-commit")
        assert session_exists(conn, 1)

        with pytest.raises(RuntimeError):
            with transaction(conn):
                create_session(conn, name="tx-rollback")
                raise RuntimeError("boom")
        # The rolled-back transaction should not have added a second session
        sessions = list(list_sessions(conn))
        assert len(sessions) == 1
    finally:
        conn.close()


def test_open_invalid_path_raises_database_error():
    with pytest.raises(DatabaseError):
        open_db("/nonexistent-dir-that-cannot-be-created/x/y/test.db")
