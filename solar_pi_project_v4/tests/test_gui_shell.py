"""GUI smoke tests for the Phase 1 main window and six-page navigation.

Uses a single QApplication and one MainWindow instance (created once, reused)
to avoid repeated widget construction/destruction that can trigger a
PySide6/shiboken garbage-collection crash on Windows. Inspects the widget
tree to confirm the six-page shell is wired correctly.
"""

from __future__ import annotations

import os
import sys

# Make the src/ layout importable.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtWidgets import QApplication

from src.solar_monitor.gui.main_window import MainWindow
from src.solar_monitor.gui.navigation import NAV_ITEMS


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_QAPP = _qapp()

# Single shared window, created once for the whole module.
_WINDOW = MainWindow()


def test_main_window_launches():
    assert _WINDOW.windowTitle() == "Solar Panel Performance Monitor"
    assert _WINDOW.minimumSize().width() >= 900
    assert _WINDOW.minimumSize().height() >= 600


def test_has_six_navigation_items():
    keys = [btn.property("navKey") for btn in _WINDOW.nav._buttons.values()]
    assert keys == [key for key, _ in NAV_ITEMS]
    assert len(keys) == 6


def test_nav_switch_changes_page():
    for key, _label in NAV_ITEMS:
        _WINDOW.nav.set_active(key)
        _WINDOW._on_nav(key)
        cls = _WINDOW.stack.currentWidget().__class__.__name__
        assert cls.endswith("Page"), f"page for {key} is {cls}"


def test_app_options_button_exists():
    labels = [b.text() for b in _WINDOW.nav.findChildren(object) if hasattr(b, "text")]
    assert "APP OPTIONS" in labels


def test_context_action_button_exists():
    _WINDOW.nav.set_active("live_monitoring")
    _WINDOW._on_nav("live_monitoring")
    assert _WINDOW.context_action is not None
    assert _WINDOW.context_action.text() == "Start monitoring"


def test_dashboard_shows_simulation_label():
    _WINDOW.nav.set_active("dashboard")
    _WINDOW._on_nav("dashboard")
    page = _WINDOW.stack.currentWidget()
    assert page.summary_label.text() == "No measurements yet."
