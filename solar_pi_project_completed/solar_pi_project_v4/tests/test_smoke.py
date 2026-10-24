"""Smoke tests: package imports and --version work without hardware."""
from __future__ import annotations

import subprocess
import sys

import pytest


def test_version_flag():
    result = subprocess.run(
        [sys.executable, "main.py", "--version"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Solar Panel Performance Monitor" in result.stdout


def test_config_defaults_importable():
    from config import SAMPLING_INTERVAL_SECONDS, SCHEMA_VERSION, DB_DEFAULT_NAME
    assert SAMPLING_INTERVAL_SECONDS == 2.0
    assert SCHEMA_VERSION == 1
    assert DB_DEFAULT_NAME == "solar_measurements.db"