"""Backup and restore that never overwrite silently."""

from __future__ import annotations

import os
import shutil

from solar_monitor.database.connection import open_db


class BackupError(RuntimeError):
    pass


def backup(db_path, backup_path):
    if os.path.abspath(db_path) == os.path.abspath(backup_path):
        raise BackupError("backup path is the same as the source database")
    if os.path.exists(backup_path):
        raise BackupError(f"backup already exists, refusing to overwrite: {backup_path}")
    os.makedirs(os.path.dirname(os.path.abspath(backup_path)) or ".", exist_ok=True)
    try:
        shutil.copy2(db_path, backup_path)
    except OSError as exc:
        raise BackupError(f"backup failed: {exc}") from exc
    return backup_path


def restore(backup_path, db_path):
    if not os.path.exists(backup_path):
        raise BackupError(f"backup not found: {backup_path}")
    if os.path.abspath(backup_path) == os.path.abspath(db_path):
        raise BackupError("backup path is the same as the target database")
    if os.path.exists(db_path):
        raise BackupError(f"target database already exists, refusing to overwrite: {db_path}")
    os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
    try:
        shutil.copy2(backup_path, db_path)
    except OSError as exc:
        raise BackupError(f"restore failed: {exc}") from exc
    try:
        conn = open_db(db_path)
        conn.close()
    except Exception as exc:
        raise BackupError(f"restored file is not a valid database: {exc}") from exc
    return db_path
