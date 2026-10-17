"""rf_spectrum_visualizer.gui.theme

UI color palette and constants.  No hardware imports, no Tkinter at import
time - safe to import on any machine.

Palette:
    NAVY      - dark navy sidebar (#0f1f3c)
    NAVY_DARK - slightly darker navy for active button (#0a162c)
    BG        - light content background (#f4f6f9)
    CARD      - white card background (#ffffff)
    TEXT      - dark text (#1a1a2e)
    MUTED     - muted text (#6b7280)
    RED       - active button / alert red (#e53935)
    GREEN     - clear channel green (#2e7d32)
    ORANGE    - moderate load orange (#ef6c00)
    RED_ALERT - heavy load red (#c62828)
    PINK      - busy/heavy row tint (#fce4ec)
    GREEN_BG  - clear row tint (#e8f5e9)
"""

from __future__ import annotations

# Sidebar / layout
NAVY = "#0f1f3c"
NAVY_DARK = "#0a162c"
SIDEBAR_WIDTH = 220
BUTTON_HEIGHT = 44

# Content area
BG = "#f4f6f9"
CARD = "#ffffff"

# Text
TEXT = "#1a1a2e"
MUTED = "#6b7280"

# Status colors
RED = "#e53935"
GREEN = "#2e7d32"
ORANGE = "#ef6c00"
RED_ALERT = "#c62828"

# Row tints
GREEN_BG = "#e8f5e9"   # Clear row
PINK = "#fce4ec"       # Busy / Heavy Load row

# Activity thresholds (Activity %)
THRESHOLD_BUSY = 50.0
THRESHOLD_HEAVY = 75.0

# Channel range
CHANNEL_MIN = 0
CHANNEL_MAX = 125
FREQ_BASE_MHZ = 2400

# UI version label
UI_VERSION = "v3.1"
WINDOW_TITLE = f"RF Spectrum Visualizer {UI_VERSION}"

# Status bar messages
STATUS_STOPPED = "Stopped"
STATUS_SCANNING = "Scanning..."


def activity_color(activity_percent: float) -> str:
    """Return the bar color for a given Activity % value.

    Green = clear, Orange = busy, Red = heavy load.
    """
    if activity_percent >= THRESHOLD_HEAVY:
        return RED_ALERT
    if activity_percent >= THRESHOLD_BUSY:
        return ORANGE
    return GREEN


def row_tint(activity_percent: float) -> str:
    """Return the table row background tint for a given Activity %."""
    if activity_percent >= THRESHOLD_BUSY:
        return PINK
    return GREEN_BG


def channel_status(activity_percent: float) -> str:
    """Return the status string for a given Activity %."""
    if activity_percent >= THRESHOLD_HEAVY:
        return "Heavy Load"
    if activity_percent >= THRESHOLD_BUSY:
        return "Busy"
    return "Clear"
