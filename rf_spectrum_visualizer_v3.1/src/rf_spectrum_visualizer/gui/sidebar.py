# rf_spectrum_visualizer.gui.sidebar - Clickable Sidebar Component (Tkinter)
# Three navigation items: Live Spectrum, Start Analysis, Blocker

from __future__ import annotations

import tkinter as tk

from rf_spectrum_visualizer.constants import (
    COLOR_NAVY_SIDEBAR,
    COLOR_CRIMON_ACCENT,
    COLOR_CRIMON_LIGHT,
    COLOR_TEXT_LIGHT,
    FONT_FAMILY,
    FONT_SIZE_DEFAULT,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    FONT_WEIGHT_BOLD,
    SIDEBAR_WIDTH,
)

PAGE_NAMES = ["live_spectrum", "start_analysis", "blocker"]
PAGE_LABELS = {
    "live_spectrum": "Live Spectrum",
    "start_analysis": "Start Analysis",
    "blocker": "Blocker",
}


class _Signal:
    """Tiny signal with a PyQt-like :meth:`connect` (for MainWindow wiring)."""

    def __init__(self) -> None:
        self._callbacks: list = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in self._callbacks:
            callback(*args)


class Sidebar(tk.Frame):
    """Dark navy sidebar with three clickable navigation items."""

    # Emitted with the selected page id (str). MainWindow connects _navigate_to.
    page_selected = _Signal()

    def __init__(self, parent, navigation_callback=None, selected_page=None,
                 **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self["background"] = COLOR_NAVY_SIDEBAR
        self.navigation_callback = navigation_callback
        self.selected_page = selected_page or PAGE_NAMES[0]
        self.buttons: dict[str, tk.Button] = {}

        self._build_ui()
        self.select_page(self.selected_page)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        for i in range(6):
            self.grid_rowconfigure(i, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Application title.
        self.title_label = tk.Label(
            self,
            text="RF Spectrum\nVisualizer",
            font=(FONT_FAMILY, FONT_SIZE_TITLE, FONT_WEIGHT_BOLD),
            foreground="#c0c0c0",
            background=COLOR_NAVY_SIDEBAR,
            justify=tk.CENTER,
            anchor="center",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(15, 8))

        # Navigation buttons.
        for idx, page_name in enumerate(PAGE_NAMES, start=1):
            btn = tk.Button(
                self,
                text=PAGE_LABELS[page_name],
                font=(FONT_FAMILY, FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
                foreground=COLOR_TEXT_LIGHT,
                background=COLOR_NAVY_SIDEBAR,
                activeforeground=COLOR_NAVY_SIDEBAR,
                activebackground=COLOR_CRIMON_ACCENT,
                cursor="hand2",
                relief="flat",
                overrelief="flat",
                command=lambda p=page_name: self._on_click(p),
                width=25,
            )
            btn.grid(row=idx, column=0, sticky="ew", padx=10, pady=6)
            self.buttons[page_name] = btn

        self.separator = tk.Label(self, background=COLOR_NAVY_SIDEBAR, height=1)
        self.separator.grid(row=4, column=0, sticky="ew", padx=10)

        self.info_label = tk.Label(
            self,
            text="v3.1",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            foreground="#606060",
            background=COLOR_NAVY_SIDEBAR,
        )
        self.info_label.grid(row=5, column=0, sticky="sw", padx=10, pady=8)

    # ------------------------------------------------------------------ actions
    def _on_click(self, page_name: str) -> None:
        self.select_page(page_name)
        self.page_selected.emit(page_name)
        # navigation_callback is accepted for signature compatibility;
        # navigation is driven exclusively by page_selected to avoid double calls.

    def select_page(self, page_name: str) -> None:
        """Visually highlight the selected sidebar button."""
        self.selected_page = page_name
        for name, btn in self.buttons.items():
            active = name == page_name
            if active:
                btn.configure(
                    background=COLOR_CRIMON_ACCENT,
                    foreground="white",
                )
            else:
                btn.configure(
                    background=COLOR_NAVY_SIDEBAR,
                    foreground=COLOR_TEXT_LIGHT,
                )

    # ------------------------------------------------------------------ API used by tests / main window
    def item_pages(self) -> list[str]:
        """Return the ordered list of page ids."""
        return list(PAGE_NAMES)

    def set_active_page(self, page_id: str) -> None:
        """Set the active page (visual highlight + navigation)."""
        if page_id in self.buttons:
            self.select_page(page_id)
            self.page_selected.emit(page_id)

    def active_page(self) -> str:
        """Return the currently active page id."""
        return self.selected_page
