"""rf_spectrum_visualizer.gui.main_window

Application shell: dark navy left sidebar (title + nav buttons), light
content area, bottom status bar.  Nothing creates a window at import time;
call run() to start the Tkinter event loop.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from rf_spectrum_visualizer.gui.theme import (
    BG,
    CARD,
    MUTED,
    NAVY,
    NAVY_DARK,
    RED,
    TEXT,
    WINDOW_TITLE,
)
from rf_spectrum_visualizer.blocker import BlockerManager
from rf_spectrum_visualizer.gui.pages.blocker import BlockerPage
from rf_spectrum_visualizer.gui.pages.live_spectrum import LiveSpectrumPage
from rf_spectrum_visualizer.gui.pages.start_analysis import StartAnalysisPage


class MainWindow:
    """Top-level application window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("1024x700")
        self.root.configure(bg=BG)

        self._current_page_name = "Live Spectrum"
        self._status_var = tk.StringVar(value="Stopped")

        # Shared blocker manager (JSON persistence) passed to pages that need it.
        self.blocker_manager = BlockerManager()

        self._build_layout()
        self._show_page("Live Spectrum")

    # ------------------------------------------------------------------ layout
    def _build_layout(self) -> None:
        # Sidebar
        self.sidebar = tk.Frame(self.root, bg=NAVY, width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        title = tk.Label(
            self.sidebar,
            text="RF Spectrum\nVisualizer v3.1",
            bg=NAVY,
            fg="white",
            font=("Segoe UI", 13, "bold"),
            justify=tk.CENTER,
        )
        title.pack(pady=(24, 16), padx=12)

        self._nav_buttons: dict[str, tk.Button] = {}
        for label, page_name in (
            ("Live Spectrum", "Live Spectrum"),
            ("Start Analysis", "Start Analysis"),
            ("Blocker", "Blocker"),
        ):
            btn = tk.Button(
                self.sidebar,
                text=label,
                bg=NAVY,
                fg="white",
                activebackground=NAVY_DARK,
                activeforeground="white",
                bd=0,
                highlightthickness=0,
                font=("Segoe UI", 10),
                anchor="w",
                padx=16,
                pady=10,
                command=lambda p=page_name: self._show_page(p),
            )
            btn.pack(fill=tk.X, padx=4, pady=2)
            self._nav_buttons[page_name] = btn

        # Content area
        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._page_frames: dict[str, ttk.Frame] = {}

        # Status bar
        self.status_bar = tk.Frame(self.root, bg=CARD, height=28)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar.pack_propagate(False)

        self.status_label = tk.Label(
            self.status_bar,
            textvariable=self._status_var,
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

        self.page_label = tk.Label(
            self.status_bar,
            text=f"Page: {self._current_page_name}",
            bg=CARD,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="e",
        )
        self.page_label.pack(side=tk.RIGHT, padx=10)

    # ------------------------------------------------------------------ pages
    def _show_page(self, page_name: str) -> None:
        """Switch to the named page, highlighting its sidebar button."""
        self._current_page_name = page_name
        self.page_label.config(text=f"Page: {page_name}")

        # Highlight active button
        for name, btn in self._nav_buttons.items():
            if name == page_name:
                btn.config(bg=RED)
            else:
                btn.config(bg=NAVY)

        # Remove previous page frame
        for frame in self._page_frames.values():
            frame.pack_forget()

        if page_name not in self._page_frames:
            if page_name == "Live Spectrum":
                frame = LiveSpectrumPage(self.content)
            elif page_name == "Start Analysis":
                frame = StartAnalysisPage(self.content, blocker_manager=self.blocker_manager)
            elif page_name == "Blocker":
                frame = BlockerPage(self.content, blocker_manager=self.blocker_manager)
            else:
                frame = ttk.Frame(self.content)
            self._page_frames[page_name] = frame

        self._page_frames[page_name].pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------ status
    def set_status(self, message: str) -> None:
        self._status_var.set(message)

    # ------------------------------------------------------------------ run
    def run(self) -> None:
        self.root.mainloop()


def run() -> None:
    """Entry point: build the window and start the event loop."""
    app = MainWindow()
    app.run()
