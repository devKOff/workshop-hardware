# RF Spectrum Visualizer - Constants
# Physical constants and fixed configuration values

# RF Frequency Constants
# Base frequency for 2.4 GHz band calculation
RF_BASE_FREQUENCY_MHZ = 2400  # 2.4 GHz base

# Channel range for 2.4 GHz ISM band
RF_CHANNEL_MIN = 0
RF_CHANNEL_MAX = 125
RF_CHANNEL_COUNT = RF_CHANNEL_MAX - RF_CHANNEL_MIN + 1  # 126 channels

# Channel spacing in MHz (for 802.11b/g)
CHANNEL_SPACING_MHZ = 5

# Frequency calculation: frequency_mhz = 2400 + channel_number * 5
# However, per requirements: frequency = 2400 + channel_number (simplified)

# UI Constants
# Color palette
COLOR_NAVY_SIDEBAR = "#1a1a2e"      # Dark navy sidebar
COLOR_WORKSPACE_BG = "#f0f0f0"      # Light workspace background
COLOR_CRIMON_ACCENT = "#dc143c"     # Crimson accent color
COLOR_CRIMON_LIGHT = "#f5c1c1"      # Light crimson for highlights
COLOR_WHITE = "#ffffff"              # White text/background
COLOR_TEXT_DARK = "#333333"          # Dark text color
COLOR_TEXT_LIGHT = "#ffffff"         # Light text color

# Font definitions
FONT_FAMILY = "Segoe UI"
FONT_SIZE_DEFAULT = 10
FONT_SIZE_SMALL = 9
FONT_SIZE_LARGE = 12
FONT_SIZE_TITLE = 14
FONT_WEIGHT_NORMAL = "normal"
FONT_WEIGHT_BOLD = "bold"

# UI Dimensions
SIDEBAR_WIDTH = 170
SIDEBAR_MIN_WIDTH = 160
SIDEBAR_MAX_WIDTH = 220
MAIN_PANEL_PADDING = 20

# Page names for navigation
PAGE_LIVE_SPECTRUM = "live_spectrum"
PAGE_START_ANALYSIS = "start_analysis"
PAGE_BLOCKER = "blocker"

PAGE_TITLES = {
    PAGE_LIVE_SPECTRUM: "Live Spectrum",
    PAGE_START_ANALYSIS: "Start Analysis",
    PAGE_BLOCKER: "Blocker",
}

# Default settings
DEFAULT_SCAN_INTERVAL = 1000  # milliseconds
DEFAULT_CHANNEL = 11

# Default window size
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800