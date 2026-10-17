"""Placeholder page: Start Analysis.

Real implementation arrives in Phase 4.  This stub keeps the GUI shell
navigable from Phase 3 without pulling in analysis logic.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class StartAnalysisPage(ttk.Frame):
    """Stub Start Analysis page."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        label = ttk.Label(
            self,
            text="Start Analysis\n(Phase 4 - not yet implemented)",
            anchor="center",
        )
        label.pack(expand=True)
