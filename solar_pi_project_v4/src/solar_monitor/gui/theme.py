"""Application theme: dark charcoal title bar, navy-and-green accents,
white main workspace. All values are used by the main window stylesheet."""

from __future__ import annotations

# --- Palette -----------------------------------------------------------------
TITLE_BAR = "#2b2b3a"          # dark charcoal title bar
TITLE_BAR_TEXT = "#e5e7eb"     # near-white title text
SIDEBAR_BG = "#f3f4f6"         # light sidebar background
SIDEBAR_TEXT = "#111827"       # dark sidebar text
SIDEBAR_ACTIVE = "#1f3a5f"     # navy accent (active nav item)
SIDEBAR_ACTIVE_TEXT = "#ffffff"
ACCENT_NAVY = "#1f3a5f"
ACCENT_GREEN = "#2e7d5b"
ACCENT_GREEN_LIGHT = "#dcfce7"
WORKSPACE_BG = "#ffffff"       # clean white main workspace
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#6b7280"
BORDER = "#e5e7eb"
CARD_BG = "#ffffff"
CARD_BORDER = "#e5e7eb"
ERROR_BG = "#fef2f2"
ERROR_TEXT = "#991b1b"
OK_TEXT = "#15803d"
WARN_TEXT = "#b45309"
INPUT_BG = "#ffffff"
INPUT_BORDER = "#d1d5db"
HOVER_BG = "#e5e7eb"

APP_NAME = "Solar Panel Performance Monitor"


def stylesheet() -> str:
    """Return the application-wide Qt style sheet."""
    return f"""
    QMainWindow {{
        background: {WORKSPACE_BG};
    }}
    QWidget {{
        font-family: 'Segoe UI', 'Arial', sans-serif;
        font-size: 13px;
        color: {TEXT_PRIMARY};
        background: transparent;
    }}
    QLabel {{
        color: {TEXT_PRIMARY};
        background: transparent;
    }}
    QLabel#pageHeading {{
        font-size: 27px;
        font-weight: 700;
        color: {TEXT_PRIMARY};
        padding-bottom: 6px;
    }}
    QLabel#pageSubheading {{
        font-size: 15px;
        color: {TEXT_SECONDARY};
        padding-bottom: 18px;
    }}
    QLabel#sectionLabel {{
        font-size: 16px;
        font-weight: 700;
        color: {ACCENT_NAVY};
        padding-top: 10px;
        padding-bottom: 6px;
    }}
    QLabel#muted {{
        color: {TEXT_SECONDARY};
        font-size: 12px;
    }}
    QPushButton {{
        background: {ACCENT_NAVY};
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 600;
        min-width: 110px;
    }}
    QPushButton:hover {{
        background: #2a4a75;
    }}
    QPushButton:pressed {{
        background: #1a304d;
    }}
    QPushButton#ghost {{
        background: {HOVER_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
    }}
    QPushButton#ghost:hover {{
        background: {BORDER};
    }}
    QPushButton#danger {{
        background: #dc2626;
        color: #ffffff;
    }}
    QPushButton#danger:hover {{
        background: #b91c1c;
    }}
    QPushButton#success {{
        background: {ACCENT_GREEN};
        color: #ffffff;
    }}
    QPushButton#success:hover {{
        background: #276747;
    }}
    QPushButton#sidebarButton {{
        text-align: left;
        padding: 12px 16px;
        min-height: 44px;
        font-size: 14px;
        font-weight: 600;
        border: none;
        border-radius: 0;
        background: transparent;
        color: {SIDEBAR_TEXT};
    }}
    QPushButton#sidebarButton:hover {{
        background: {HOVER_BG};
        color: {ACCENT_NAVY};
    }}
    QPushButton#sidebarButton:checked {{
        background: {SIDEBAR_ACTIVE};
        color: {SIDEBAR_ACTIVE_TEXT};
    }}
    QPushButton#sidebarButton:checked:hover {{
        background: {SIDEBAR_ACTIVE};
    }}
    QPushButton#appOptions {{
        background: {HOVER_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        padding: 8px 14px;
        font-size: 12px;
        min-width: 100px;
    }}
    QPushButton#appOptions:hover {{
        background: {BORDER};
    }}
    QFrame#card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 8px;
    }}
    QFrame#sidebar {{
        background: {SIDEBAR_BG};
        border-right: 1px solid {BORDER};
    }}
    QFrame#statusBar {{
        background: {TITLE_BAR};
        color: {TITLE_BAR_TEXT};
        border-top: 1px solid {BORDER};
    }}
    QLabel#statusBarLabel {{
        color: {TITLE_BAR_TEXT};
        font-size: 12px;
        padding: 6px 12px;
        background: transparent;
    }}
    QTableView {{
        background: {WORKSPACE_BG};
        border: 1px solid {BORDER};
        border-radius: 6px;
        gridline-color: {BORDER};
        selection-background-color: {ACCENT_GREEN_LIGHT};
        selection-color: {TEXT_PRIMARY};
    }}
    QHeaderView::section {{
        background: {SIDEBAR_BG};
        color: {TEXT_SECONDARY};
        font-weight: 700;
        font-size: 12px;
        padding: 6px 8px;
        border: none;
        border-bottom: 1px solid {BORDER};
        border-right: 1px solid {BORDER};
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {INPUT_BG};
        border: 1px solid {INPUT_BORDER};
        border-radius: 6px;
        padding: 6px 10px;
        color: {TEXT_PRIMARY};
        min-height: 30px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {ACCENT_NAVY};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        border-radius: 6px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: 6px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {TEXT_SECONDARY};
    }}
    """
