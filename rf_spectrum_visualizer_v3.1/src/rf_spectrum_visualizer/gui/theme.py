# rf_spectrum_visualizer.gui.theme - Color and Style Constants (Tkinter)
# Professional dark navy sidebar, light workspace, crimson accents

from tkinter import font as tkfont

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
)

# Semantic colour aliases for readability.
NAVY_DARK = COLOR_NAVY_SIDEBAR
WORKSPACE_BG = COLOR_WORKSPACE_BG
CRIMSON = COLOR_CRIMON_ACCENT
CRIMSON_HOVER = "#b71c1c"
CRIMSON_BG = COLOR_CRIMON_LIGHT
CARD_BG = COLOR_WHITE
CARD_BORDER = "#d7dee8"
INK = COLOR_TEXT_DARK
MUTED = "#666666"
BORDER = "#e5e7eb"
DIVIDER = "#cbd5e1"


def get_sidebar_style() -> dict:
    """Return style dictionary for the sidebar frame."""
    return {
        "background": COLOR_NAVY_SIDEBAR,
        "width": SIDEBAR_WIDTH,
        "relief": "flat",
        "borderwidth": 0,
    }


def get_active_sidebar_style() -> dict:
    """Return style for the active/hover sidebar item."""
    return {
        "background": COLOR_CRIMON_ACCENT,
        "foreground": "white",
    }


def get_inactive_sidebar_style() -> dict:
    """Return style for inactive sidebar items."""
    return {
        "background": COLOR_NAVY_SIDEBAR,
        "foreground": COLOR_TEXT_LIGHT,
    }


def get_workspace_style() -> dict:
    """Return style for the main workspace frame."""
    return {
        "background": COLOR_WORKSPACE_BG,
        "relief": "flat",
        "borderwidth": 0,
    }


def get_card_style() -> dict:
    """Return style for card-style frames (summary cards, etc.)."""
    return {
        "background": COLOR_WHITE,
        "relief": "raised",
        "borderwidth": 1,
    }


def get_crimson_accent_style() -> dict:
    """Return style emphasizing crimson accent."""
    return {
        "foreground": COLOR_CRIMON_ACCENT,
        "background": COLOR_CRIMON_LIGHT,
    }


def get_table_header_style() -> dict:
    """Return style for table section headers."""
    return {
        "background": COLOR_NAVY_SIDEBAR,
        "foreground": COLOR_WHITE,
        "font": (FONT_FAMILY, FONT_SIZE_SMALL, FONT_WEIGHT_BOLD),
    }


def get_table_row_style(even: bool = True) -> dict:
    """Return style for table rows (alternating)."""
    base_bg = COLOR_WHITE if even else COLOR_CRIMON_LIGHT
    base_fg = COLOR_TEXT_DARK if even else COLOR_TEXT_DARK
    return {
        "background": base_bg,
        "foreground": base_fg,
    }


def get_font(size: int = FONT_SIZE_DEFAULT, weight: str = FONT_WEIGHT_NORMAL) -> tuple:
    """Return a font tuple (family, size, weight)."""
    return (FONT_FAMILY, size, weight)


def get_tk_font(size: int = FONT_SIZE_DEFAULT, weight: str = FONT_WEIGHT_NORMAL):
    """Return a tkinter Font object."""
    tk_weight = "bold" if weight == FONT_WEIGHT_BOLD else "normal"
    return tkfont.Font(family=FONT_FAMILY, size=size, weight=tk_weight)
