#!/usr/bin/env python3
"""RF Spectrum Visualizer v3.1 - Simulation Mode Launcher.

Launches the application explicitly in simulation mode. This is useful
on machines without nRF24L01+ hardware (e.g., Windows development machines,
Raspberry Pi without SPI configured).

Usage:
    python run_sim.py
"""

from __future__ import annotations

import os
import sys

# Make src/rf_spectrum_visualizer importable.
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Force simulation mode before the GUI is constructed.
os.environ.setdefault("RF_SPECTRUM_BACKEND", "sim")

from rf_spectrum_visualizer.config import AppConfig
from rf_spectrum_visualizer.gui.main_window import MainWindow


def main() -> int:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config = AppConfig.defaults()
    config.default_backend = "sim"  # Explicitly simulation mode

    app = MainWindow(config=config)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
