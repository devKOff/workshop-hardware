"""Main window: dark charcoal title bar, navy-and-green accents, white workspace,
left sidebar navigation, six stacked pages, bottom APP OPTIONS and context action."""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .navigation import (
    NAV_CSV_REPORTS,
    NAV_DASHBOARD,
    NAV_HISTORICAL_DATA,
    NAV_LIVE_MONITORING,
    NAV_SETTINGS,
    NAV_SYSTEM_INFORMATION,
    Navigation,
)
from .pages.csv_reports import CSVReportsPage
from .pages.dashboard import DashboardPage
from .pages.historical_data import HistoricalDataPage
from .pages.live_monitoring import LiveMonitoringPage
from .pages.settings import SettingsPage
from .pages.system_information import SystemInformationPage
from .theme import ACCENT_GREEN, ACCENT_NAVY, TITLE_BAR, TITLE_BAR_TEXT, stylesheet


PAGE_CLASSES = {
    NAV_DASHBOARD: DashboardPage,
    NAV_LIVE_MONITORING: LiveMonitoringPage,
    NAV_HISTORICAL_DATA: HistoricalDataPage,
    NAV_CSV_REPORTS: CSVReportsPage,
    NAV_SETTINGS: SettingsPage,
    NAV_SYSTEM_INFORMATION: SystemInformationPage,
}


def enable_dark_title_bar(window) -> None:
    """Enable the native dark title bar on Windows 10/11 (best effort)."""
    if sys.platform != "win32":
        return
    try:
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        hwnd = int(window.winId())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:  # pragma: no cover - platform best effort
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Solar Panel Performance Monitor")
        self.setMinimumSize(980, 640)
        self.resize(1200, 760)

        self._pages = {}
        self._context_action = None
        self._build_ui()

        # Apply stylesheet after widgets are created so object names resolve.
        self.setStyleSheet(stylesheet())
        enable_dark_title_bar(self)

        # Show dashboard by default
        self._on_nav(NAV_DASHBOARD)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Body: sidebar + stacked pages ----------------------------------
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.nav = Navigation()
        self.nav.navRequested.connect(self._on_nav)
        self.nav.appOptionsRequested.connect(self._on_app_options)
        body.addWidget(self.nav)

        self.stack = QStackedWidget()
        body.addWidget(self.stack, stretch=1)

        root.addLayout(body, stretch=1)

        # --- Footer: APP OPTIONS (bottom-left) + context action (bottom-right)
        footer = QFrame()
        footer.setObjectName("statusBar")
        footer.setFixedHeight(40)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        footer_layout.setSpacing(0)

        app_options = QPushButton("APP OPTIONS")
        app_options.setObjectName("appOptions")
        app_options.clicked.connect(self._on_app_options)
        footer_layout.addWidget(app_options)

        footer_layout.addStretch()

        self.context_action = QPushButton("Start monitoring")
        self.context_action.setObjectName("contextAction")
        self.context_action.setFixedHeight(30)
        self.context_action.setMinimumWidth(150)
        self.context_action.clicked.connect(self._on_context_action)
        footer_layout.addWidget(self.context_action)

        root.addWidget(footer)

    # --- Navigation ---------------------------------------------------------
    def _on_nav(self, key: str) -> None:
        if key not in PAGE_CLASSES:
            return
        if key not in self._pages:
            self._pages[key] = PAGE_CLASSES[key](self)
            self.stack.addWidget(self._pages[key])
        self.stack.setCurrentWidget(self._pages[key])
        self._update_context_action(key)

    def _update_context_action(self, key: str) -> None:
        if key == NAV_LIVE_MONITORING:
            self.context_action.setText("Start monitoring")
            self.context_action.setObjectName("contextAction")
            self.context_action.setVisible(True)
        elif key == NAV_CSV_REPORTS:
            self.context_action.setText("Export CSV…")
            self.context_action.setVisible(True)
        else:
            self.context_action.setVisible(False)
        self.context_action.style().unpolish(self.context_action)
        self.context_action.style().polish(self.context_action)

    # --- Actions ------------------------------------------------------------
    def _on_app_options(self) -> None:
        self.nav.appOptionsRequested.emit()
        self._set_context("App options opened.")

    def _on_context_action(self) -> None:
        key = self._current_key()
        if key == NAV_LIVE_MONITORING:
            self._set_context("Monitoring started (simulation).")
        elif key == NAV_CSV_REPORTS:
            self._set_context("CSV export opened.")
        else:
            self._set_context("Action performed.")

    def _current_key(self) -> str:
        for key, page in self._pages.items():
            if self.stack.currentWidget() is page:
                return key
        return NAV_DASHBOARD

    def _set_context(self, message: str) -> None:
        self.statusBar().showMessage(message, 4000)


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Solar Panel Performance Monitor")
    app.setApplicationVersion("1.0.0-dev")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gui())
