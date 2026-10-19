"""System Information page: versions, backend status, database health, sensor
diagnostics, recent logs, and missing-dependency diagnostics."""

from __future__ import annotations

import importlib
import logging
import platform
import sys

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...database.connection import open_db
from ...database.schema import SCHEMA_VERSION, schema_version
from ..theme import ERROR_TEXT, OK_TEXT, TEXT_SECONDARY, WARN_TEXT
from .base import PageBase


def _check_dependency(module_name: str) -> tuple[bool, str]:
    """Return (available, version_or_error) for a Python module."""
    try:
        mod = importlib.import_module(module_name)
        version = getattr(mod, "__version__", "installed")
        return True, str(version)
    except ImportError as exc:
        return False, str(exc)


def _check_i2c() -> tuple[bool, str]:
    """Best-effort I²C availability check (Linux only)."""
    if sys.platform != "linux":
        return True, "N/A (not Linux)"
    try:
        import smbus2  # noqa: F401

        return True, "smbus2 installed"
    except ImportError:
        return False, "smbus2 not installed"


class SystemInformationPage(PageBase):
    def __init__(self, context, main_window, parent=None):
        self._ctx = context
        super().__init__(
            "System Information",
            "Application and Python versions, operating system, backend status, "
            "database health, and sensor diagnostics.",
            parent,
        )
        self._build()

    def _build(self):
        super()._build()
        engine = self._ctx.engine
        backend = engine.backend
        diag = backend.diagnostics()

        lines = [
            f"Application: Solar Panel Performance Monitor",
            f"Application version: 1.0.0-dev",
            f"Python: {platform.python_version()} on {platform.system()} {platform.release()} ({platform.machine()})",
            f"Operating mode: {'simulation' if backend.mode == 'simulated' else 'hardware'}",
            f"Backend available: {'yes' if backend.is_available() else 'no'}",
            f"Backend library: {diag.get('library', 'simulation')}",
            f"Database path: {self._ctx.db_path}",
        ]
        for text in lines:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; padding: 3px 0;")
            lbl.setWordWrap(True)
            self.add_widget(lbl)

        # Database health section
        self.add_widget(QLabel("Database health:"))
        db_health = self._check_database_health()
        for line in db_health:
            color = OK_TEXT if "ok" in line.lower() or "healthy" in line.lower() else TEXT_SECONDARY
            if "error" in line.lower() or "fail" in line.lower():
                color = ERROR_TEXT
            lbl = QLabel(line)
            lbl.setStyleSheet(f"color: {color}; font-size: 12px; padding: 2px 0;")
            lbl.setWordWrap(True)
            self.add_widget(lbl)

        # Backend diagnostics section
        self.add_widget(QLabel("Backend diagnostics:"))
        detail = (
            f"  Hardware: {diag.get('hardware', False)}  "
            f"Simulated: {diag.get('simulated', False)}  "
            f"Available: {diag.get('available', False)}  "
            f"Samples: {diag.get('samples', 0)}"
        )
        if diag.get("init_error"):
            detail += f"  Init error: {diag['init_error']}"
        if diag.get("i2c_bus") is not None:
            detail += f"  I²C bus: {diag['i2c_bus']}  Address: {diag.get('i2c_address')}"
        dlbl = QLabel(detail)
        dlbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding: 3px 0;")
        dlbl.setWordWrap(True)
        self.add_widget(dlbl)

        # Dependency diagnostics
        self.add_widget(QLabel("Dependency diagnostics:"))
        deps = [
            ("PySide6", "PySide6"),
            ("pyqtgraph", "pyqtgraph"),
            ("sqlite3", "sqlite3"),
            ("adafruit-circuitpython-ina219", "adafruit_ina219"),
            ("smbus2", "smbus2"),
        ]
        for label, module in deps:
            ok, info = _check_dependency(module)
            color = OK_TEXT if ok else ERROR_TEXT
            lbl = QLabel(f"  {label}: {'installed (' + info + ')' if ok else 'MISSING — ' + info}")
            lbl.setStyleSheet(f"color: {color}; font-size: 12px; padding: 2px 0;")
            lbl.setWordWrap(True)
            self.add_widget(lbl)

        # I²C check
        i2c_ok, i2c_info = _check_i2c()
        i2c_color = OK_TEXT if i2c_ok else WARN_TEXT
        i2c_lbl = QLabel(f"  I²C support: {i2c_info}")
        i2c_lbl.setStyleSheet(f"color: {i2c_color}; font-size: 12px; padding: 2px 0;")
        i2c_lbl.setWordWrap(True)
        self.add_widget(i2c_lbl)

        # Recent logs section
        self.add_widget(QLabel("Recent application logs:"))
        logs = self._get_recent_logs()
        for line in logs:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; padding: 1px 0;")
            lbl.setWordWrap(True)
            self.add_widget(lbl)

        note = QLabel(
            "Hardware failure is shown as an honest error state. Simulated or "
            "stale readings are never substituted for genuine hardware readings."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding-top: 8px;")
        self.add_widget(note)

        self.add_stretch()

    def _check_database_health(self) -> list[str]:
        """Check SQLite database health: integrity, WAL mode, schema version,
        measurement and session counts."""
        lines = []
        try:
            conn = open_db(self._ctx.db_path)
            try:
                # Integrity check
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                lines.append(f"  Integrity check: {integrity}")

                # Journal mode
                journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
                lines.append(f"  Journal mode: {journal}")

                # Schema version
                sv = schema_version(conn)
                lines.append(f"  Schema version: {sv} (expected {SCHEMA_VERSION})")

                # Counts
                try:
                    mc = conn.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
                    lines.append(f"  Measurements: {mc}")
                except Exception:
                    lines.append("  Measurements: table not found")

                try:
                    sc = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
                    lines.append(f"  Sessions: {sc}")
                except Exception:
                    lines.append("  Sessions: table not found")

                lines.append("  Status: healthy")
            finally:
                conn.close()
        except Exception as exc:  # noqa: BLE001
            lines.append(f"  Status: error — {exc}")
        return lines

    def _get_recent_logs(self) -> list[str]:
        """Return recent application log lines from the logging subsystem."""
        lines = []
        handler = logging.getLogger().handlers
        if not handler:
            return ["  (no log handler configured)"]
        # Collect from any in-memory handlers
        records = []
        for h in handler:
            if hasattr(h, "records"):
                records.extend(h.records)
        if not records:
            return ["  (no recent log records)"]
        for rec in records[-10:]:
            lines.append(f"  [{rec.levelname}] {rec.getMessage()}")
        return lines
