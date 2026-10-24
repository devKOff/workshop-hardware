"""Left sidebar navigation: vertically arranged navigation items."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import APP_NAME, SIDEBAR_BG

# Navigation item identifiers
NAV_DASHBOARD = "dashboard"
NAV_LIVE_MONITORING = "live_monitoring"
NAV_HISTORICAL_DATA = "historical_data"
NAV_CSV_REPORTS = "csv_reports"
NAV_SETTINGS = "settings"
NAV_SYSTEM_INFORMATION = "system_information"

NAV_ITEMS = [
    (NAV_DASHBOARD, "Dashboard"),
    (NAV_LIVE_MONITORING, "Live Monitoring"),
    (NAV_HISTORICAL_DATA, "Historical Data"),
    (NAV_CSV_REPORTS, "CSV Reports"),
    (NAV_SETTINGS, "Settings"),
    (NAV_SYSTEM_INFORMATION, "System Information"),
]


class Navigation(QWidget):
    """Left sidebar with vertically arranged navigation items.

    Emits navRequested(str) when a section is selected.
    """

    navRequested = Signal(str)
    appOptionsRequested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(230)
        self._buttons = {}
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(6)

        title = QLabel(APP_NAME)
        title.setStyleSheet(
            "font-size: 15px; font-weight: 800; color: #111827; "
            "letter-spacing: 0.3px; padding-bottom: 14px;"
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("sidebarButton")
            btn.setCheckable(True)
            btn.setProperty("navKey", key)
            btn.clicked.connect(self._emit_nav)
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()

        app_options = QPushButton("APP OPTIONS")
        app_options.setObjectName("appOptions")
        app_options.clicked.connect(self.appOptionsRequested.emit)
        layout.addWidget(app_options)

    def _emit_nav(self) -> None:
        btn = self.sender()
        if not isinstance(btn, QPushButton):
            return
        key = btn.property("navKey")
        if key:
            self.navRequested.emit(key)
            self.set_active(key)

    def set_active(self, key: str) -> None:
        for k, btn in self._buttons.items():
            btn.setChecked(k == key)
