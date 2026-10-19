"""SQLite storage: schema, migrations, connection, DAOs, settings, backup."""

from __future__ import annotations

from solar_monitor.database.backup import BackupError, backup, restore
from solar_monitor.database.connection import DatabaseError, open_db, transaction
from solar_monitor.database.dao import (
    SQL_INSERT_MEASUREMENT,
    create_session,
    end_session,
    get_integration_state,
    get_setting,
    insert_measurement,
    list_sessions,
    session_exists,
    set_setting,
    update_integration_state,
)
from solar_monitor.database.paths import app_data_dir, default_db_path, ensure_data_dir
from solar_monitor.database.schema import SCHEMA_VERSION, init_schema, migrate_schema, schema_version
from solar_monitor.database.settings import SettingsError, SettingsService

__all__ = [
    "DatabaseError",
    "SettingsError",
    "SettingsService",
    "BackupError",
    "SCHEMA_VERSION",
    "SQL_INSERT_MEASUREMENT",
    "app_data_dir",
    "default_db_path",
    "ensure_data_dir",
    "init_schema",
    "migrate_schema",
    "schema_version",
    "open_db",
    "transaction",
    "create_session",
    "end_session",
    "insert_measurement",
    "update_integration_state",
    "get_integration_state",
    "get_setting",
    "set_setting",
    "list_sessions",
    "session_exists",
    "backup",
    "restore",
]
