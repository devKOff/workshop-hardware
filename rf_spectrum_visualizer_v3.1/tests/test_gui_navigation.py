"""Tests for the main window: launch, navigation, clean shutdown."""

from __future__ import annotations

import tkinter as tk

from rf_spectrum_visualizer.constants import (
    PAGE_BLOCKER,
    PAGE_LIVE_SPECTRUM,
    PAGE_START_ANALYSIS,
)
from rf_spectrum_visualizer.config import AppConfig
from rf_spectrum_visualizer.gui.main_window import MainWindow


class TestMainWindow:
    def test_window_launches_and_has_three_pages(self):
        config = AppConfig.defaults()
        window = MainWindow(config=config)

        assert window.title() == "RF Spectrum Visualizer v3.1"
        assert window.sidebar.item_pages() == [
            PAGE_LIVE_SPECTRUM,
            PAGE_START_ANALYSIS,
            PAGE_BLOCKER,
        ]

        # All three pages exist.
        assert set(window._pages.keys()) == {
            PAGE_LIVE_SPECTRUM,
            PAGE_START_ANALYSIS,
            PAGE_BLOCKER,
        }

        # Initial page is Live Spectrum.
        assert window.sidebar.active_page() == PAGE_LIVE_SPECTRUM
        window.destroy()

    def test_navigation_switches_pages(self):
        config = AppConfig.defaults()
        window = MainWindow(config=config)

        # Direct navigation (bypasses sidebar signal to avoid double-callbacks).
        window._navigate_to(PAGE_LIVE_SPECTRUM)
        assert window.sidebar.active_page() == PAGE_LIVE_SPECTRUM

        window._navigate_to(PAGE_START_ANALYSIS)
        assert window.sidebar.active_page() == PAGE_START_ANALYSIS

        window._navigate_to(PAGE_BLOCKER)
        assert window.sidebar.active_page() == PAGE_BLOCKER

        window.destroy()

    def test_clean_shutdown(self):
        config = AppConfig.defaults()
        window = MainWindow(config=config)
        window.update_idletasks()
        window.destroy()
        assert True
