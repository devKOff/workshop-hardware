"""Main application window: Tkinter sidebar + page switching.

Keeps the existing design (dark navy sidebar, light workspace, crimson accents)
and three sidebar pages. Manages the Live Spectrum scanner lifecycle (V3
ScannerThread in a background thread) with thread-safe GUI updates via Tk
after() polling. Holds the shared SpectrumData for future Analysis page.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Set

from .sidebar import Sidebar
from .live_spectrum_page import LiveSpectrumPage
from .start_analysis_page import StartAnalysisPage
from .blocker_page import BlockerPage
from .theme import (
    get_sidebar_style,
    get_workspace_style,
    COLOR_NAVY_SIDEBAR,
    COLOR_WORKSPACE_BG,
)
from ..constants import (
    DEFAULT_WINDOW_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
    PAGE_LIVE_SPECTRUM,
    PAGE_START_ANALYSIS,
    PAGE_BLOCKER,
    PAGE_TITLES,
)
from ..config import AppConfig
from ..v3_bridge import SpectrumData, ScannerThread, hardware_available

logger = logging.getLogger("rf_visualizer.gui.main_window")


class MainWindow(tk.Tk):
    """Shell window with a dark navy sidebar and three page modules."""

    def __init__(self, config: AppConfig | None = None):
        super().__init__()

        self.config = config or AppConfig.defaults()

        self.title("RF Spectrum Visualizer v3.1")
        self.geometry(f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}")
        self.configure(bg=COLOR_WORKSPACE_BG)

        # Shared spectrum data (accessible by all pages; Analysis page later).
        self.spectrum_data = SpectrumData(self.config)
        self.spectrum_data.set_backend(self.config.default_backend)

        # Scanner worker (V3 ScannerThread running in a background thread).
        self._scanner: Optional[ScannerThread] = None
        self._scanning = False
        self._backend = self.config.default_backend
        self._refresh_job: Optional[str] = None

        self._build_ui()
        self._update_ui_state()

        # Clean shutdown on window close.
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        logger.info("MainWindow initialized (backend=%s)", self._backend)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # Sidebar (dark navy).
        self.sidebar = Sidebar(
            self,
            navigation_callback=self._navigate_to,
            selected_page=PAGE_LIVE_SPECTRUM,
            **get_sidebar_style(),
        )
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)
        self.sidebar.pack_propagate(False)
        self.sidebar.page_selected.connect(self._navigate_to)

        # Content workspace (light).
        self.content = tk.Frame(self, **get_workspace_style())
        self.content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # Three pages stacked in the same cell.
        self._pages: dict[str, tk.Frame] = {}
        self._pages[PAGE_LIVE_SPECTRUM] = LiveSpectrumPage(
            self.content, self, self.spectrum_data
        )
        self._pages[PAGE_START_ANALYSIS] = StartAnalysisPage(
            self.content, self, self.spectrum_data
        )
        self._pages[PAGE_BLOCKER] = BlockerPage(
            self.content, self, self.spectrum_data
        )

        for page in self._pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        # Status bar (create before navigation so _sb() works).
        self.__dict__["_sb_var"] = tk.StringVar(value="Ready — RF Spectrum Visualizer v3.1")
        status_bar = tk.Label(
            self,
            textvariable=self.__dict__["_sb_var"],
            relief=tk.SUNKEN,
            anchor=tk.W,
            bg="#e5e5e5",
            fg="#333333",
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._navigate_to(PAGE_LIVE_SPECTRUM)

    def _sb(self):
        return self.__dict__["_sb_var"]

    # ----------------------------------------------------------------- navigation
    def _navigate_to(self, page_id: str) -> None:
        page = self._pages.get(page_id)
        if page is None:
            return
        for p in self._pages.values():
            p.grid_remove()
        page.grid(row=0, column=0, sticky="nsew")
        self.sidebar.select_page(page_id)
        title = PAGE_TITLES.get(page_id, page_id)
        self._sb().set(f"Page: {title}")
        logger.info("Navigated to %s", title)

        if page_id == PAGE_LIVE_SPECTRUM and self._scanning:
            self._start_refresh_timer()
        else:
            self._stop_refresh_timer()

    # ----------------------------------------------------------------- scanner lifecycle
    def start_scan(self, start_ch: int, end_ch: int, window_s: float,
                   interval_ms: float) -> None:
        """Start the V3 scanner thread (no duplicate workers)."""
        if self._scanning:
            return
        try:
            if not (0 <= start_ch <= 125):
                raise ValueError("Start channel out of range 0-125")
            if not (0 <= end_ch <= 125):
                raise ValueError("End channel out of range 0-125")
            if start_ch > end_ch:
                raise ValueError("Start channel must be <= end channel")

            self.config.channel.start_channel = start_ch
            self.config.channel.end_channel = end_ch
            self.config.scan.measurement_window = window_s
            self.config.scan.sampling_interval = interval_ms / 1000.0
            self.config.default_backend = self._backend

            self.spectrum_data.clear()
            self.spectrum_data.set_backend(self._backend)

            self._scanner = ScannerThread(
                self.config,
                self.spectrum_data,
                radio=None,  # ScannerThread creates the radio for the backend
                on_observation=self._on_observation_cb,
                on_error=self._on_error_cb,
                on_scan_complete=self._on_complete_cb,
            )
            self._scanner.start()
            self._scanning = True
            self._start_refresh_timer()

            live_page = self._pages[PAGE_LIVE_SPECTRUM]
            live_page.update_source_label()
            live_page.btn_start.configure(state=tk.DISABLED)
            live_page.btn_stop.configure(state=tk.NORMAL)

            backend_name = (
                "Hardware (nRF24L01+)" if self._backend == "hardware"
                else "Simulation"
            )
            self._sb().set(
                f"Scanning ({backend_name}) channels {start_ch}-{end_ch}"
            )
            logger.info("Scanner started (%s backend, channels %d-%d)",
                        self._backend, start_ch, end_ch)

        except Exception as e:  # noqa: BLE001
            logger.error("Failed to start scanning: %s", e)
            messagebox.showerror("Scanner error", f"Failed to start scanning: {e}")
            self._sb().set(f"Error: {e}")

    def stop_scan(self) -> None:
        """Stop the scanner thread and clean up."""
        if not self._scanning:
            return
        try:
            if self._scanner is not None:
                self._scanner.shutdown()
                self._scanner = None
        except Exception as e:  # noqa: BLE001
            logger.warning("Error stopping scanner: %s", e)
            self._sb().set(f"Warning stopping scanner: {e}")
        finally:
            self._scanning = False
            self._scanner = None
            self._stop_refresh_timer()
            live_page = self._pages[PAGE_LIVE_SPECTRUM]
            live_page.btn_start.configure(state=tk.NORMAL)
            live_page.btn_stop.configure(state=tk.DISABLED)
            self._sb().set("Stopped")
            logger.info("Scanner stopped")

    def is_scanning(self) -> bool:
        return self._scanning

    def set_backend(self, backend: str) -> None:
        if backend not in ("sim", "hardware"):
            return
        if self._scanning:
            messagebox.showwarning(
                "Cannot change mode", "Stop scanning before changing mode."
            )
            return
        self._backend = backend
        self.config.default_backend = backend
        backend_name = (
            "Hardware (nRF24L01+)" if backend == "hardware" else "Simulation"
        )
        self._sb().set(f"Mode: {backend_name}")

    def get_backend(self) -> str:
        return self._backend

    def hardware_available(self) -> bool:
        return hardware_available()

    def get_blocked_channels(self) -> Set[int]:
        """Return the current blocked/excluded channel set from the Blocker page.

        Provides a live read of the blocker's in-memory exclusion list for
        use by the Analysis page. No blocker data is persisted or invented.
        """
        blocker_page = self._pages.get(PAGE_BLOCKER)
        if blocker_page is not None and hasattr(blocker_page, "excluded_channels"):
            return set(blocker_page.excluded_channels())
        return set()

    # ----------------------------------------------------------------- scanner callbacks (background thread)
    def _on_observation_cb(self, obs) -> None:
        """Called from the scanner thread. Use Tk after for thread safety."""
        live_page = self._pages[PAGE_LIVE_SPECTRUM]
        self.after(0, lambda o=obs: live_page.set_last_channel(o.channel))

    def _on_error_cb(self, error: Exception) -> None:
        """Called from the scanner thread on per-channel errors."""
        logger.error("Scanner error: %s", error)
        self.after(0, lambda e=str(error): self._sb().set(f"Scanner error: {e}"))

    def _on_complete_cb(self) -> None:
        """Called from the scanner thread when a full cycle completes."""
        logger.debug("Scan cycle complete")

    # ----------------------------------------------------------------- UI refresh timer (main thread only via Tk after)
    def _start_refresh_timer(self) -> None:
        self._stop_refresh_timer()
        self.refresh_ui()
        self._refresh_job = self.after(500, self._start_refresh_timer)

    def _stop_refresh_timer(self) -> None:
        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except tk.TclError:
                pass
            self._refresh_job = None

    def refresh_ui(self) -> None:
        """Poll shared spectrum data and redraw. Main thread only."""
        if not self._scanning:
            return
        try:
            live_page = self._pages[PAGE_LIVE_SPECTRUM]
            live_page.refresh_from_data()
        except Exception as e:  # noqa: BLE001 - keep UI alive
            logger.error("UI refresh error: %s", e)

    # ----------------------------------------------------------------- UI state
    def _update_ui_state(self) -> None:
        live_page = self._pages[PAGE_LIVE_SPECTRUM]
        if self._scanning:
            live_page.btn_start.configure(state=tk.DISABLED)
            live_page.btn_stop.configure(state=tk.NORMAL)
        else:
            live_page.btn_start.configure(state=tk.NORMAL)
            live_page.btn_stop.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        self.stop_scan()
        self.destroy()

    def run(self) -> None:
        self.mainloop()
