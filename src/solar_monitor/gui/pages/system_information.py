"""System Information page: versions, backend status, diagnostics."""

from __future__ import annotations

import platform
import sys

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .base import PageBase
from ..theme import TEXT_SECONDARY


class SystemInformationPage(PageBase):
    def __init__(self, parent=None):
        super().__init__(
            "System Information",
            "Application and Python versions, operating system, backend status, "
            "database health, and sensor diagnostics.",
            parent,
        )
        self._build()

    def _populate_content(self):
        lines = [
            f"Application: Solar Panel Performance Monitor",
            f"Python: {platform.python_version()} on {platform.system()} {platform.release()}",
            f"Backend: simulation (Windows) / hardware (Raspberry Pi INA219 over I²C)",
            "Database: SQLite (WAL mode) — health reported after first measurement.",
            "Sensor: INA219 — diagnostics appear here when hardware mode is active.",
        ]
        for text in lines:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; padding: 3px 0;")
            lbl.setWordWrap(True)
            self.add_widget(lbl)

        self.add_stretch()
