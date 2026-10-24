"""Tests for backup and restore that never overwrite silently."""
from __future__ import annotations

import os
import tempfile

import pytest

from database.backup import backup, restore, BackupError
from database.connection import open_db


def _close(conn):
    try:
        conn.close()
    except Exception:
        pass


def test_backup_creates_copy():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.db")
        _close(open_db(src))
        dest = os.path.join(tmp, "dest.db")
        out = backup(src, dest)
        assert out == dest
        assert os.path.exists(dest)


def test_backup_refuses_existing_dest():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.db")
        _close(open_db(src))
        dest = os.path.join(tmp, "dest.db")
        _close(open_db(dest))
        with pytest.raises(BackupError):
            backup(src, dest)


def test_backup_refuses_same_path():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "same.db")
        _close(open_db(src))
        with pytest.raises(BackupError):
            backup(src, src)


def test_restore_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.db")
        conn = open_db(src)
        try:
            from database import dao
            sid = dao.create_session(conn, "sess1", "simulated")
        finally:
            conn.close()
        backup_path = os.path.join(tmp, "bak.db")
        backup(src, backup_path)
        target = os.path.join(tmp, "target.db")
        restore(backup_path, target)
        conn2 = open_db(target)
        try:
            from database import dao
            assert dao.session_exists(conn2, sid)
        finally:
            conn2.close()


def test_restore_refuses_existing_target():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.db")
        _close(open_db(src))
        backup_path = os.path.join(tmp, "bak.db")
        backup(src, backup_path)
        target = os.path.join(tmp, "target.db")
        _close(open_db(target))
        with pytest.raises(BackupError):
            restore(backup_path, target)


def test_restore_missing_backup_raises():
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "target.db")
        with pytest.raises(BackupError):
            restore(os.path.join(tmp, "missing.db"), target)