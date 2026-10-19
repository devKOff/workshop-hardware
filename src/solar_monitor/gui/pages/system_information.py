"""System Information page: versions, backend status, diagnostics."""

from __future__ import annotations

import platform
import sys

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..theme import TEXT_SECONDARY
from .base import PageBase


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
            f"Backend: {diag.get('library', 'simulation')}",
            f"Database: {self._ctx.db_path}",
        ]
        for text in lines:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; padding: 3px 0;")
            lbl.setWordWrap(True)
            self.add_widget(lbl)

        # Backend diagnostics detail
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

        note = QLabel(
            "Hardware failure is shown as an honest error state. Simulated or "
            "stale readings are never substituted for genuine hardware readings."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; padding-top: 8px;")
        self.add_widget(note)

        self.add_stretch()
