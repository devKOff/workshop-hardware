"""Shared pytest fixtures for the GUI tests.

Adds the project `src/` directory to sys.path so that `rf_spectrum_visualizer`
is importable as a top-level package (matching the imports used inside the
package modules).
"""

from __future__ import annotations

import os
import sys

import pytest

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


@pytest.fixture(scope="session")
def tk_root():
    """Shared Tk root window for GUI tests."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()  # hide the window during tests
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass
