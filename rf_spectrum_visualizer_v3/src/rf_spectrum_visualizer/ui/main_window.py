"""Main application window for RF Spectrum Visualizer V3.

Provides the unified desktop GUI with a permanent vertical left-side toolbar
and three primary navigation tools: Live Spectrum, Start Analysis, Blocker.

Design:
- Dark charcoal sidebar (200px wide) with tool buttons and active highlighting
- Light main workspace with three page frames
- Consistent spacing, typography, and tooltips
- Keyboard-accessible navigation (Tab cycling between tools)
- Responsive charts and tables
- Loading, empty, and error states for each tool
- Shared services: ScannerService, BlocklistService, AnalysisService

The application uses a frame-switching pattern where each tool's widgets
are built inside its own frame, and the active frame is raised when the
user selects a different tool from the sidebar.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
from typing import Dict, Any, Optional, Callable

from rf_spectrum_visualizer.models.channel import (
    channel_to_frequency, validate_channel, CHANNEL_MIN, CHANNEL_MAX,
    ALL_CHANNELS, format_channel, get_all_channels
)
from rf_spectrum_visualizer.exceptions import (
    InvalidChannelError, HardwareError, ScannerError,
    BlocklistError, SimulationError,
)
from rf_spectrum_visualizer.services.scanner import ScannerService
from rf_spectrum_visualizer.services.blocklist import BlocklistService
from rf_spectrum_visualizer.services.analysis import AnalysisService
from rf_spectrum_visualizer.radio import HardwareRadioAdapter, SimRadioAdapter

logger = logging.getLogger("rf_visualizer.ui.main_window")


# ── Color palette ──────────────────────────────────────────────────────
SIDEBAR_BG = "#2b2b2b"       # charcoal
SIDEBAR_ACTIVE_BG = "#3a3a3a"  # active item
SIDEBAR_FG = "#e0e0e0"       # light text
ACCENT_BLUE = "#3b82f6"
ACCENT_GREEN = "#10b981"
ACCENT_ORANGE = "#f59e0b"
ACCENT_RED = "#ef4444"
PANEL_BG = "#f3f4f6"         # light background
ENTRY_BG = "#ffffff"
BORDER_COLOR = "#d1d5db"


class MainWindow(tk.Tk):
    """Main application window with vertical three-tool sidebar."""

    def __init__(self, config: Any = None):
        """Initialize the main application window.

        Args:
            config: Application configuration object. If None, defaults are used.
        """
        super().__init__()

        self.config = config or {}

        # ── Window basics ──────────────────────────────────────────────
        self.title("RF Spectrum Visualizer V3")
        self.geometry("1400x900")
        self.minsize(1200, 700)
        self.configure(bg=PANEL_BG)

        # ── Shared services ────────────────────────────────────────────
        self.scanner_service: Optional[ScannerService] = None
        self.blocklist_service: Optional[BlocklistService] = None
        self.analysis_service: Optional[AnalysisService] = None

        # ── State ──────────────────────────────────────────────────────
        self.tool_var = tk.StringVar(value="live")  # "live", "analysis", "blocker"
        self.refresh_job: Optional[str] = None

        # ── Build UI ────────────────────────────────────────────────────
        self._build_sidebar()
        self._build_content_area()
        self._build_status_bar()

        # ── Initialise services (lazy - after data is available) ───────
        self._init_services_after_gui()

        logger.info("MainWindow UI built")

    # ── Sidebar ───────────────────────────────────────────────────────
    def _build_sidebar(self) -> None:
        """Create the vertical left-side toolbar with three tool buttons."""
        self.sidebar = ttk.Frame(self, width=200, style="Sidebar.TFrame")
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)
        self.sidebar.pack_propagate(False)  # keep fixed width

        # Configure style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(
            "Sidebar.TFrame", background=SIDEBAR_BG
        )
        self.style.configure(
            "Tool.TButton",
            background=SIDEBAR_BG,
            foreground=SIDEBAR_FG,
            font=("-family Segoe UI", -size 10),
            borderwidth=0,
            focuscolor=SIDEBAR_BG,
        )
        self.style.map(
            "Tool.TButton",
            background=[("active", SIDEBAR_ACTIVE_BG), ("pressed", SIDEBAR_ACTIVE_BG)],
        )

        # Tool definitions: (icon_text, tooltip, page_key)
        self.tools = [
            {
                "key": "live",
                "label": "Live Spectrum",
                "tooltip": "Live spectrum scanning and visualization",
            },
            {
                "key": "analysis",
                "label": "Start Analysis",
                "tooltip": "Channel analysis, statistics, rankings, recommendations",
            },
            {
                "key": "blocker",
                "label": "Blocker",
                "tooltip": "Channel blocklist management and avoidance",
            },
        ]

        self.tool_buttons: Dict[str, ttk.Button] = {}

        # Create sidebar buttons
        for i, tool in enumerate(self.tools):
            btn = ttk.Button(
                self.sidebar,
                text=tool["label"],
                style="Tool.TButton",
                cursor="hand2",
                command=lambda k=tool["key"]: self._switch_tool(k),
            )
            btn.pack(fill=tk.X, padx=10, pady=4)
            btn.bind("<Enter>", lambda e, t=tool["tooltip"]: self._set_tooltip(t))
            btn.bind("<Leave>", lambda e: self._hide_tooltip())
            self.tool_buttons[tool["key"]] = btn

        # Highlight the initially active tool
        self._highlight_tool("live")

        # Store tooltip label
        self._tooltip_label: Optional[ttk.Label] = None
        self._tooltip_var = tk.StringVar(value="")

    def _set_tooltip(self, text: str) -> None:
        """Show a tooltip for the currently hovered tool."""
        if self._tooltip_label is not None:
            self._tooltip_label.destroy()
        self._tooltip_label = ttk.Label(
            self.sidebar,
            text=text,
            background=SIDEBAR_ACTIVE_BG,
            foreground=SIDEBAR_FG,
            font=("-family Segoe UI", -size 9),
            padding=(5, 2),
        )
        self._tooltip_label.pack(pady=(0, 5))

    def _hide_tooltip(self) -> None:
        """Hide the tooltip."""
        if self._tooltip_label is not None:
            self._tooltip_label.destroy()
            self._tooltip_label = None

    def _highlight_tool(self, active_key: str) -> None:
        """Highlight the active tool button and deactivate others."""
        for key, btn in self.tool_buttons.items():
            if key == active_key:
                btn.configure(style="ToolActive.TButton")
            else:
                btn.configure(style="Tool.TButton")

    # ── Content area ────────────────────────────────────────────────
    def _build_content_area(self) -> None:
        """Create the main content area with three page frames."""
        self.content = ttk.Frame(self, style="Content.TFrame")
        self.content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Configure grid weights
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        # Three page frames
        self.pages: Dict[str, ttk.Frame] = {}
        for key in ["live", "analysis", "blocker"]:
            frame = ttk.Frame(self.content, style="Page.TFrame")
            frame.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = frame

        # Show the initially active page
        self._switch_tool("live")

    # ── Tool switching ────────────────────────────────────────────────
    def _switch_tool(self, key: str) -> None:
        """Switch to the selected tool page.

        Hides all pages, shows the selected one, and updates the sidebar
        highlighting. Also ensures shared services are connected.
        """
        # Hide all pages
        for frame in self.pages.values():
            frame.pack_forget()

        # Show the selected page
        self.pages[key].pack(fill=tk.BOTH, expand=True)

        # Update sidebar highlighting
        self._highlight_tool(key)
        self.tool_var.set(key)

        # Initialize services if not done yet (lazy init tied to first tool access)
        if key == "live" and self.scanner_service is None:
            self._init_services(lazy=True)

        logger.info(f"Switched to tool: {key}")

    # ── Status bar ────────────────────────────────────────────────────
    def _build_status_bar(self) -> None:
        """Create the bottom status bar."""
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W,
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ── Service initialization ────────────────────────────────────────
    def _init_services_after_gui(self) -> None:
        """Lazy service initialization after GUI is built.

        Services are initialized on first use rather than at construction
        time, since they depend on GUI components (SpectrumData, etc.)
        that are built within the tool frames.
        """
        # We'll re-init on first tool switch; this is just a placeholder
        pass

    def _init_services(self, lazy: bool = False) -> None:
        """Initialize the shared services.

        Creates ScannerService, BlocklistService, and AnalysisService
        and connects them to the appropriate GUI components.

        Args:
            lazy: If True, minimal initialization; full init on first tool switch.
        """
        if self.scanner_service is not None:
            return  # already initialized

        # Build shared configuration
        from rf_spectrum_visualizer.models.channel import ChannelConfig
        from rf_spectrum_visualizer.services.blocklist import BlocklistService as BlkService

        channel_config = ChannelConfig(start_channel=0, end_channel=125)
        from rf_spectrum_visualizer.config import AppConfig
        from rf_spectrum_visualizer.services.scanner import ScannerService as SvcScanner

        app_config = AppConfig()
        # Override default backend to sim for development environments
        app_config.default_backend = "sim"

        # Create BlocklistService
        self.blocklist_service = BlkService(config_file_path="blocklist.json")

        # Create AnalysisService
        from v6.channel_selector import ChannelSelector, ChannelEligibility, EligibilityReason
        from v6.config import ThresholdConfig
        from v6.blocklist_manager import BlocklistManager as V6BlocklistManager

        thresholds = ThresholdConfig(clear_max=24, moderate_max=49, busy_max=74, heavy_min=75)
        blocklist = V6BlocklistManager(BlocklistConfig(file_path="blocklist.json"))
        self.analysis_service = AnalysisService(
            channel_config=channel_config,
            threshold_config=thresholds,
            blocklist=blocklist,
            persistent_threshold=75.0,
            hysteresis=5.0,
        )

        # Create ScannerService
        self.scanner_service = SvcScanner(
            config=app_config,
            backend="sim",  # use simulation by default
        )

        # Connect scanner spectrum_data to shared SpectrumData
        # The scanner service's spectrum_data is set by each tool frame
        # when it builds its UI. For now, just log.
        logger.info("Services initialized: scanner, blocklist, analysis")

        # Update status bar
        if self.status_var:
            backends = self.scanner_service.get_status_summary()
            self.status_var.set(
                f"Ready | {backends.get('backend_label', 'sim')} | "
                f"Blocked: {self.blocklist_service.get_blocked_count()}"
            )

    # ── Public API for services ───────────────────────────────────────
    def get_scanner_service(self) -> Optional[ScannerService]:
        """Get the scanner service instance."""
        return self.scanner_service

    def get_blocklist_service(self) -> Optional[BlocklistService]:
        """Get the blocklist service instance."""
        return self.blocklist_service

    def get_analysis_service(self) -> Optional[AnalysisService]:
        """Get the analysis service instance."""
        return self.analysis_service

    # ── Export helpers ────────────────────────────────────────────────
    def export_csv(self, data: list, filename: str) -> bool:
        """Export data to CSV file via dialog."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export CSV",
        )
        if not path:
            return False
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys() if data else [])
                writer.writeheader()
                writer.writerows(data)
            return True
        except Exception as e:
            logger.error(f"CSV export error: {e}")
            messagebox.showerror("Export Error", str(e))
            return False

    def export_json(self, data: dict, filename: str) -> bool:
        """Export data to JSON file via dialog."""
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export JSON",
        )
        if not path:
            return False
        try:
            import json
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"JSON export error: {e}")
            messagebox.showerror("Export Error", str(e))
            return False


def run_app(config: Any = None) -> None:
    """Run the RF Spectrum Visualizer V3 application.

    Args:
        config: Optional application configuration object.
    """
    app = MainWindow(config=config)
    app.mainloop()