"""Reusable matplotlib canvas for Tkinter.

Charts are rendered with matplotlib's TkAgg backend and embedded in a Tkinter
frame. Exposes .figure, .axes, .draw(), .clear_plot() for use by page modules.
"""

from __future__ import annotations

import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class MplCanvas:
    """Embeddable matplotlib figure canvas for Tkinter."""

    def __init__(self, parent, width: float = 5.0, height: float = 4.0, dpi: int = 100):
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        try:
            self.figure.set_layout_engine("constrained")
        except Exception:  # pragma: no cover - older matplotlib fallback
            self.figure.set_constrained_layout(True)
        self.axes = self.figure.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self._widget = self._canvas.get_tk_widget()
        self._widget.pack(fill=tk.BOTH, expand=True)

    def draw(self) -> None:
        """Redraw the canvas."""
        self._canvas.draw_idle()

    def clear_plot(self) -> None:
        """Clear all axes content and redraw."""
        self.axes.clear()
        self.draw()

    def pack(self, **kwargs) -> None:
        self._widget.pack(**kwargs)

    def grid(self, **kwargs) -> None:
        self._widget.grid(**kwargs)

    def destroy(self) -> None:
        self._widget.destroy()
