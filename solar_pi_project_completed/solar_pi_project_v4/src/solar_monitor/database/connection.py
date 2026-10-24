"""Database connection handling: open, init, graceful error handling."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from solar_monitor.database.schema import init_schema
from solar_monitor.database.paths import default_db_path


class DatabaseError(RuntimeError):
    pass


def open_db(db_path: str | None = None):
    """Open (and initialize) the SQLite database.

    When db_path is None, the default production path inside the user
    application-data directory is used.
    """
    if db_path is None:
        db_path = default_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        init_schema(conn)
        return conn
    except sqlite3.DatabaseError as exc:
        if conn is not None:
            conn.close()
        raise DatabaseError(f"Cannot open database {db_path!r}: {exc}") from exc


@contextmanager
def transaction(conn):
    conn.execute("BEGIN")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
