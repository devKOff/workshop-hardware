"""Placeholder page: Blocker.

Real implementation arrives in Phase 5.  This stub keeps the GUI shell
navigable from Phase 3 without pulling in blocker logic.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class BlockerPage(ttk.Frame):
    """Stub Blocker page."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        label = ttk.Label(
            self,
            text="Blocker\n(Phase 5 - not yet implemented)",
            anchor="center",
        )
        label.pack(expand=True)
