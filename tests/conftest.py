"""Pytest configuration — headless-safe Qt platform."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_configure(config):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")