"""Bridge to V3 scanner implementation (read-only, never modified).

Adds the V3 source project (workshop/v3) to sys.path so its scanner modules
can be imported. The V3 project is never modified — only inspected and used.

V3 modules imported:
    config        - AppConfig, ChannelConfig, ScanConfig, ThresholdConfig
    scanner       - ScannerThread, SpectrumData, ChannelObservation
    sim_radio     - SimRadio (deterministic simulation backend)
    hardware_radio - HardwareRadio (nRF24L01+ via pyrf24)
    exceptions    - V3 custom exceptions
"""

from __future__ import annotations

import os
import sys
from typing import Optional

_V3_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "v3")
)

if _V3_ROOT not in sys.path:
    sys.path.insert(0, _V3_ROOT)

# Import V3 modules (read-only).
# These are top-level modules in the v3/ project.
from config import (  # noqa: E402,F401
    AppConfig as V3AppConfig,
    ChannelConfig as V3ChannelConfig,
    ScanConfig as V3ScanConfig,
    ThresholdConfig as V3ThresholdConfig,
)
from scanner import (  # noqa: E402,F401
    ScannerThread,
    SpectrumData,
    ChannelObservation,
)
from sim_radio import SimRadio  # noqa: E402,F401
from hardware_radio import HardwareRadio  # noqa: E402,F401
from exceptions import (  # noqa: E402,F401
    ScannerError,
    ScannerAlreadyRunningError,
    ScannerNotRunningError,
    HardwareError,
    SimulationError,
    InvalidChannelError,
)

__all__ = [
    "ScannerThread",
    "SpectrumData",
    "ChannelObservation",
    "SimRadio",
    "HardwareRadio",
    "ScannerError",
    "ScannerAlreadyRunningError",
    "ScannerNotRunningError",
    "HardwareError",
    "SimulationError",
    "InvalidChannelError",
    "V3AppConfig",
    "V3ChannelConfig",
    "V3ScanConfig",
    "V3ThresholdConfig",
]


def hardware_available() -> bool:
    """Check if the V3 hardware backend (pyrf24) is available."""
    try:
        import pyrf24  # noqa: F401
        return True
    except ImportError:
        return False
