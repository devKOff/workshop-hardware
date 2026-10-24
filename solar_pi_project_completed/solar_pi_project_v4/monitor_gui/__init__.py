"""Solar Panel Performance Monitor — simple 10-minute single-window GUI.

This package is a standalone Tkinter + Matplotlib monitor that reuses the
existing INA219 sensor backends from ``solar_monitor.backends``. It is
deliberately separate from the project's PySide6 multi-page GUI.
"""

from __future__ import annotations

__version__ = "1.0.0-monitor-gui"
