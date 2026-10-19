"""Database connection handling — re-exports from solar_monitor.database.connection."""

from __future__ import annotations

from solar_monitor.database.connection import (  # noqa: E402
    DatabaseError,
    default_db_path,
    open_db,
    transaction,
)

__all__ = ["DatabaseError", "default_db_path", "open_db", "transaction"]
