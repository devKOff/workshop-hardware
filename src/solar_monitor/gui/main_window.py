"""Main window: dark charcoal title bar, navy-and-green accents, white workspace,
left sidebar navigation, six stacked pages, bottom APP OPTIONS and context action.

Wires the measurement engine, database, settings, and backends into the six
functional pages. Owns the GUI-thread poll timer that drains the engine queue.
"""

from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from solar_monitor.backends import INA219HardwareBackend, SimulatedSensor
from solar_monitor.database.connection import open_db
from solar_monitor.database.paths import default_db_path, ensure_data_dir
from solar_monitor.database.settings import SettingsService
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


class AppContext:
    """Shared application resources handed to each page."""

    def __init__(self):
        ensure_data_dir()
        self.db_path = default_db_path()
        self.conn = open_db(self.db_path)
        self.settings = SettingsService(self.conn)
        self.sim_backend = SimulatedSensor()
        self.hw_backend = INA219HardwareBackend()  # probed lazily, never at import
        # Default to the simulation backend on Windows (safe without hardware).
        self.backend = self.sim_backend
        from solar_monitor.core.measurement_engine import MeasurementEngine

        self.engine = MeasurementEngine(self.backend, db_path=self.db_path)

    def close(self):
        try:
            self.engine.shutdown()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.conn.close()
        except Exception:  # noqa: BLE001
            pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Solar Panel Performance Monitor")
        self.setMinimumSize(980, 640)
        self.resize(1200, 760)

        self.ctx = AppContext()
        self._pages = {}
        self._context_action = None

        # GUI-thread poll timer owned by the main window (lives with the app,
        # never garbage-collected per page), drains the engine queue.
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(50)
        self._poll_timer.setSingleShot(False)
        self._poll_timer.timeout.connect(self._poll_engine)
        self._poll_timer.start()

        self._build_ui()

        self.setStyleSheet(stylesheet())
        enable_dark_title_bar(self)

        # Wire engine callbacks (invoked on the GUI thread by the poll timer).
        engine = self.ctx.engine
        engine.on_measurement = self._on_measurement_taken
        engine.on_backend_error = self._on_backend_error
        engine.on_status_changed = self.statusBar().showMessage

        self.nav.set_active(NAV_DASHBOARD)
        self._on_nav(NAV_DASHBOARD)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

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
            self._pages[key] = PAGE_CLASSES[key](self.ctx, self)
            self.stack.addWidget(self._pages[key])
        self.stack.setCurrentWidget(self._pages[key])
        self._update_context_action(key)

    def _update_context_action(self, key: str) -> None:
        ca = self.context_action
        if key == NAV_LIVE_MONITORING:
            ca.setText("Start monitoring")
            ca.setVisible(True)
        elif key == NAV_CSV_REPORTS:
            ca.setText("Export CSV…")
            ca.setVisible(True)
        else:
            ca.setVisible(False)
        ca.style().unpolish(ca)
        ca.style().polish(ca)

    # --- Poll ---------------------------------------------------------------
    def _poll_engine(self):
        self.ctx.engine.poll()

    # --- Actions ------------------------------------------------------------
    def _on_app_options(self) -> None:
        self.nav.appOptionsRequested.emit()
        self.statusBar().showMessage("App options opened.", 4000)

    def _on_context_action(self) -> None:
        key = self._current_key()
        if key == NAV_LIVE_MONITORING:
            page = self._pages.get(key)
            if page:
                page.toggle_monitoring()
        elif key == NAV_CSV_REPORTS:
            page = self._pages.get(key)
            if page:
                page.do_export()
        self.statusBar().showMessage("Action performed.", 3000)

    def _current_key(self) -> str:
        for key, page in self._pages.items():
            if self.stack.currentWidget() is page:
                return key
        return NAV_DASHBOARD

    # --- Engine callback handlers ------------------------------------------
    def _on_measurement_taken(self, m, increment_wh, total_energy_wh):
        page = self._pages.get(NAV_DASHBOARD)
        if page is not None:
            page.on_measurement(m, increment_wh, total_energy_wh)

    def _on_backend_error(self, message: str):
        page = self._pages.get(NAV_DASHBOARD)
        if page is not None:
            page.on_backend_error(message)

    def closeEvent(self, event):
        self.ctx.close()
        super().closeEvent(event)


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Solar Panel Performance Monitor")
    app.setApplicationVersion("1.0.0-dev")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gui())
