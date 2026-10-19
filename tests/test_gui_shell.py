"""GUI smoke tests for the Phase 1 main window and six-page navigation.

These tests do not require pytest-qt: they build a QApplication with the
offscreen platform (set by tests/conftest.py) and inspect the widget tree.
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


def test_main_window_launches():
    window = MainWindow()
    assert window.windowTitle() == "Solar Panel Performance Monitor"
    assert window.minimumSize().width() >= 900
    assert window.minimumSize().height() >= 600
    window.close()


def test_has_six_navigation_items():
    window = MainWindow()
    keys = [btn.property("navKey") for btn in window.nav._buttons.values()]
    assert keys == [key for key, _ in NAV_ITEMS]
    assert len(keys) == 6
    window.close()


def test_nav_switch_changes_page():
    window = MainWindow()
    for key, _label in NAV_ITEMS:
        window.nav.set_active(key)
        window._on_nav(key)
        cls = window.stack.currentWidget().__class__.__name__
        assert cls.endswith("Page"), f"page for {key} is {cls}"
    window.close()


def test_app_options_button_exists():
    window = MainWindow()
    labels = [b.text() for b in window.nav.findChildren(object) if hasattr(b, "text")]
    assert "APP OPTIONS" in labels
    window.close()


def test_context_action_button_exists():
    window = MainWindow()
    assert window.context_action is not None
    assert window.context_action.text() == "Start monitoring"
    window.close()


def test_dashboard_shows_simulation_label():
    window = MainWindow()
    window.nav.set_active("dashboard")
    window._on_nav("dashboard")
    page = window.stack.currentWidget()
    assert page.summary_label.text() == "No measurements yet."
    window.close()
