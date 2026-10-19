"""Tests for the settings service validation and persistence."""
from __future__ import annotations

import os
import tempfile

import pytest

from database.connection import open_db
from database.settings import SettingsService, SettingsError


def test_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        conn = open_db(os.path.join(tmp, "s.db"))
        try:
            svc = SettingsService(conn)
            assert svc.get("sampling_interval_s") == 2.0
            assert svc.get("graph_history_seconds") == 300.0
            assert svc.get("sensor_mode") == "simulated"
        finally:
            conn.close()


def test_set_and_get():
    with tempfile.TemporaryDirectory() as tmp:
        conn = open_db(os.path.join(tmp, "s.db"))
        try:
            svc = SettingsService(conn)
            svc.set("sampling_interval_s", 5.0)
            assert svc.get("sampling_interval_s") == 5.0
        finally:
            conn.close()


def test_invalid_values_rejected_not_applied():
    with tempfile.TemporaryDirectory() as tmp:
        conn = open_db(os.path.join(tmp, "s.db"))
        try:
            svc = SettingsService(conn)
            with pytest.raises(SettingsError):
                svc.set("sampling_interval_s", -1.0)
            assert svc.get("sampling_interval_s") == 2.0
            with pytest.raises(SettingsError):
                svc.set("sensor_mode", "not-a-mode")
            assert svc.get("sensor_mode") == "simulated"
        finally:
            conn.close()


def test_unknown_setting_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        conn = open_db(os.path.join(tmp, "s.db"))
        try:
            svc = SettingsService(conn)
            with pytest.raises(SettingsError):
                svc.get("no_such_setting")
            with pytest.raises(SettingsError):
                svc.set("no_such_setting", 1)
        finally:
            conn.close()


def test_persistence_across_connections():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "persist.db")
        conn1 = open_db(path)
        try:
            svc1 = SettingsService(conn1)
            svc1.set("sampling_interval_s", 7.0)
        finally:
            conn1.close()
        conn2 = open_db(path)
        try:
            svc2 = SettingsService(conn2)
            assert svc2.get("sampling_interval_s") == 7.0
        finally:
            conn2.close()