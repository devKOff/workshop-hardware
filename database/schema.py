"""SQLite schema — re-exports from solar_monitor.database.schema."""

from __future__ import annotations

from solar_monitor.database.schema import (  # noqa: E402
    DDL,
    MIGRATIONS,
    PRAGMA_STATEMENTS,
    SCHEMA_VERSION,
    init_schema,
    migrate_schema,
    schema_version,
)

__all__ = [
    "DDL",
    "MIGRATIONS",
    "PRAGMA_STATEMENTS",
    "SCHEMA_VERSION",
    "init_schema",
    "migrate_schema",
    "schema_version",
]
