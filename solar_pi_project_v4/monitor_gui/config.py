"""Configuration defaults for the 10-minute solar panel monitor GUI.

All timing uses ``time.monotonic()`` for durations/scheduling and timezone-aware
``datetime`` (ISO 8601) only to label samples. Nothing here is hardware-specific
beyond the INA219 defaults taken from the existing project (docs/HARDWARE.md).
"""

from __future__ import annotations

# --- Session / timing ---
DURATION_S = 600.0                 # 10 minutes default
SAMPLING_INTERVAL_S = 1.0          # default seconds between samples
SAMPLING_INTERVAL_MIN = 0.2        # validated lower bound (seconds)
SAMPLING_INTERVAL_MAX = 60.0       # validated upper bound (seconds)

# --- Validity thresholds ---
REVERSE_CURRENT_TOLERANCE_MA = -5.0  # reverse current beyond this is invalid
MAX_VOLTAGE_V = 30.0
MAX_CURRENT_A = 10.0
MAX_POWER_W = 60.0
MAX_GAP_MULTIPLIER = 5.0           # do not integrate across gaps > 5 x interval

# --- INA219 hardware (existing project defaults) ---
I2C_BUS = 1
I2C_ADDRESS = 0x40
SHUNT_OHM = 0.1
MAX_CURRENT_A_HARDWARE = 1.0

# --- Data source labels ---
DATA_SOURCE_HARDWARE = "hardware"
DATA_SOURCE_SIMULATION = "simulation"

# --- Sample statuses ---
STATUS_OK = "ok"
STATUS_READ_ERROR = "read_error"
STATUS_OVERFLOW = "overflow"
STATUS_OUT_OF_RANGE = "out_of_range"
STATUS_REVERSE_CURRENT = "reverse_current"

VALID_STATUSES = (
    STATUS_OK,
    STATUS_READ_ERROR,
    STATUS_OVERFLOW,
    STATUS_OUT_OF_RANGE,
    STATUS_REVERSE_CURRENT,
)

# --- GUI ---
APP_TITLE = "Solar Panel Performance Monitor"
SIMULATION_BANNER_TEXT = "SIMULATION — NOT REAL DATA"
