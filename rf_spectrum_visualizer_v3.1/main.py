"""Entry point for rf_spectrum_visualizer v3.1 GUI (Tkinter).

Run with:
    python main.py

(from the project root)
"""

from __future__ import annotations

import logging
import os
import sys

# Make `src/rf_spectrum_visualizer` importable as `rf_spectrum_visualizer`.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from rf_spectrum_visualizer.config import AppConfig
from rf_spectrum_visualizer.gui.main_window import MainWindow


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    config = AppConfig.defaults()
    app = MainWindow(config=config)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
