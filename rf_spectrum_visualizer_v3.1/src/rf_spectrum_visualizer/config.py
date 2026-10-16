# rf_spectrum_visualizer - Configuration Settings
# Application configuration loaded at startup

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from rf_spectrum_visualizer.constants import (
    COLOR_NAVY_SIDEBAR,
    COLOR_WORKSPACE_BG,
    COLOR_CRIMON_ACCENT,
    COLOR_CRIMON_LIGHT,
    COLOR_WHITE,
    COLOR_TEXT_DARK,
    COLOR_TEXT_LIGHT,
    FONT_FAMILY,
    FONT_SIZE_DEFAULT,
    FONT_SIZE_SMALL,
    FONT_SIZE_LARGE,
    FONT_SIZE_TITLE,
    FONT_WEIGHT_NORMAL,
    FONT_WEIGHT_BOLD,
    SIDEBAR_WIDTH,
    SIDEBAR_MIN_WIDTH,
    SIDEBAR_MAX_WIDTH,
    MAIN_PANEL_PADDING,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_CHANNEL,
    RF_CHANNEL_MIN,
    RF_CHANNEL_MAX,
    RF_BASE_FREQUENCY_MHZ,
    PAGE_LIVE_SPECTRUM,
    PAGE_START_ANALYSIS,
    PAGE_BLOCKER,
)

# Application settings
APP_NAME = "RF Spectrum Visualizer v3.1"
APP_VERSION = "3.1.0"
APP_WINDOW_TITLE = f"{APP_NAME}"
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600

# Channel configuration
# Validate: channel_number must be in range 0-125
# Frequency calculation: frequency_mhz = 2400 + channel_number
CHANNEL_VALIDATION_RANGE = (RF_CHANNEL_MIN, RF_CHANNEL_MAX)

# Scan settings
ENABLE_AUTO_SCAN = False
DEFAULT_SCAN_DURATION = 5000  # milliseconds

# UI themes
THEME_DARK = "dark"
THEME_LIGHT = "light"
CURRENT_THEME = THEME_DARK

# File paths
CONFIG_FILE = "rf_spectrum_visualizer_config.json"
DEFAULT_SETTINGS = {
    "theme": CURRENT_THEME,
    "selected_page": PAGE_LIVE_SPECTRUM,
    "channel_number": DEFAULT_CHANNEL,
    "scan_running": False,
    "window_geometry": f"{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}",
}


# ---------------------------------------------------------------------------
# V3-compatible configuration dataclasses (used by V3 ScannerThread)
# ---------------------------------------------------------------------------
@dataclass
class ChannelConfig:
    """Channel scanning configuration (0-125)."""

    start_channel: int = RF_CHANNEL_MIN
    end_channel: int = RF_CHANNEL_MAX

    def __post_init__(self):
        if not (RF_CHANNEL_MIN <= self.start_channel <= RF_CHANNEL_MAX):
            raise ValueError("start_channel must be between 0 and 125")
        if not (RF_CHANNEL_MIN <= self.end_channel <= RF_CHANNEL_MAX):
            raise ValueError("end_channel must be between 0 and 125")
        if self.start_channel > self.end_channel:
            raise ValueError("start_channel must be <= end_channel")

    @property
    def channel_count(self) -> int:
        return self.end_channel - self.start_channel + 1

    def channel_range(self) -> range:
        return range(self.start_channel, self.end_channel + 1)


@dataclass
class ScanConfig:
    """Scanning timing configuration."""

    measurement_window: float = 1.0  # seconds per channel
    sampling_interval: float = 0.01  # seconds between RPD samples
    min_valid_samples: int = 10

    def __post_init__(self):
        if self.measurement_window <= 0:
            raise ValueError("measurement_window must be positive")
        if self.sampling_interval <= 0:
            raise ValueError("sampling_interval must be positive")
        if self.min_valid_samples < 1:
            raise ValueError("min_valid_samples must be >= 1")

    @property
    def expected_samples_per_channel(self) -> int:
        return int(self.measurement_window / self.sampling_interval)


@dataclass
class ThresholdConfig:
    """Activity classification thresholds (Clear/Moderate/Busy/Heavy Load)."""

    clear_max: int = 24
    moderate_max: int = 49
    busy_max: int = 74
    heavy_min: int = 75

    def __post_init__(self):
        if not (
            0 <= self.clear_max < self.moderate_max < self.busy_max < self.heavy_min <= 100
        ):
            raise ValueError(
                "Thresholds must be ordered: 0 <= clear < moderate < busy < heavy <= 100"
            )

    def classify(self, percentage: Optional[float]) -> str:
        """Classify activity percentage into a status label."""
        if percentage is None:
            return "INSUFFICIENT DATA"
        if percentage <= self.clear_max:
            return "Clear"
        if percentage <= self.moderate_max:
            return "Moderate"
        if percentage <= self.busy_max:
            return "Busy"
        return "Heavy Load"


@dataclass
class StorageConfig:
    """Data storage configuration."""

    rolling_history_size: int = 100
    waterfall_history_size: int = 200


@dataclass
class GUIConfig:
    """GUI configuration."""

    refresh_interval_ms: int = 500


@dataclass
class AppConfig:
    """Main application configuration (compatible with V3 ScannerThread)."""

    channel: ChannelConfig = field(default_factory=ChannelConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    gui: GUIConfig = field(default_factory=GUIConfig)
    default_backend: str = "sim"  # "sim" or "hardware"
    enable_rf_scanning: bool = True
    enable_analysis: bool = False
    enable_persistent_blocker_storage: bool = False

    def __post_init__(self):
        if self.default_backend not in ("hardware", "sim"):
            raise ValueError("default_backend must be 'hardware' or 'sim'")

    @classmethod
    def defaults(cls) -> "AppConfig":
        """Return a fresh config with default values."""
        return cls()


def get_frequency_mhz(channel_number: int) -> float:
    """
    Calculate frequency in MHz from channel number.

    Formula: frequency_mhz = 2400 + channel_number

    Args:
        channel_number: Channel number (0-125)

    Returns:
        Frequency in MHz

    Raises:
        ValueError: If channel number is outside valid range
    """
    if not (RF_CHANNEL_MIN <= channel_number <= RF_CHANNEL_MAX):
        raise ValueError(
            f"Channel number {channel_number} is outside valid range "
            f"[{RF_CHANNEL_MIN}, {RF_CHANNEL_MAX}]"
        )
    return RF_BASE_FREQUENCY_MHZ + channel_number


def validate_channel(channel_number: int) -> bool:
    """
    Validate that a channel number is within the acceptable range.

    Args:
        channel_number: Channel number to validate

    Returns:
        True if valid, False otherwise
    """
    return RF_CHANNEL_MIN <= channel_number <= RF_CHANNEL_MAX


def get_channel_label(channel_number: int) -> str:
    """
    Get a human-readable label for a channel.

    Args:
        channel_number: Channel number (0-125)

    Returns:
        String label like "Channel 11" or "Channel 0"
    """
    if not validate_channel(channel_number):
        return "Invalid Channel"
    return f"Channel {channel_number}"
