"""Waterfall widget - clean 2D heatmap implementation with single unified colorbar."""

import tkinter as tk
from tkinter import ttk
import time
from collections import deque
from typing import List, Optional

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from config import AppConfig
from scanner.scanner_engine import SpectrumData, ChannelObservation
from mitigation.blocklist_manager import BlocklistManager


class WaterfallWidget:
    """Clean 2D waterfall heatmap with single unified colorbar."""
    
    def __init__(
        self,
        parent: ttk.Frame,
        config: AppConfig,
        spectrum_data: SpectrumData,
        blocklist: BlocklistManager,
    ):
        self._config = config
        self._spectrum_data = spectrum_data
        self._blocklist = blocklist
        
        # Data storage
        self._waterfall_data: deque = deque(maxlen=config.gui.waterfall_history_size)
        self._waterfall_timestamps: deque = deque(maxlen=config.gui.waterfall_history_size)
        self._channels: List[int] = []
        
        # Matplotlib colormap
        self._cmap = LinearSegmentedColormap.from_list(
            "rf_cmap", ["#000000", "#0000ff", "#00ffff", "#ffff00", "#ff0000"]
        )
        
        self._create_ui(parent)
    
    def _create_ui(self, parent: ttk.Frame) -> None:
        """Create the waterfall widget UI with a single colorbar on the right."""
        self._frame = ttk.Frame(parent)
        self._frame.pack(fill=tk.BOTH, expand=True)
        
        # Create figure with extra space on right for colorbar
        self._fig = Figure(figsize=(10, 3.5), dpi=100)
        self._fig.subplots_adjust(right=0.85)  # Make room for colorbar
        
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._fig, self._frame)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self._ax.set_xlabel("Channel (nRF24)")
        self._ax.set_ylabel("Time (s ago)")
        self._ax.grid(True, alpha=0.2)
        
        # Colorbar axis (will be created on first update)
        self._cbar_ax = None
        self._cbar = None
        self._wf_image = None
        
        # WiFi channel markers (constant)
        self._wifi_channels = {1: 2412, 6: 2437, 11: 2462}
    
    @property
    def frame(self) -> ttk.Frame:
        return self._frame
    
    def update(self, observations: dict = None) -> None:
        """Update the waterfall with new data row."""
        if observations is None:
            observations = self._spectrum_data.get_all_observations()
        
        channels = self._spectrum_data.get_channels_in_range()
        if not self._channels:
            self._channels = list(channels)
        
        now = time.time()
        row = []
        for ch in channels:
            obs = observations.get(ch)
            row.append(obs.activity_percentage if obs and obs.activity_percentage is not None else 0)
        
        self._waterfall_data.append(row)
        self._waterfall_timestamps.append(now)
        
        if len(self._waterfall_data) < 2:
            return
        
        self._render_heatmap()
    
    def _render_heatmap(self) -> None:
        """Render the waterfall as a clean 2D heatmap."""
        data = np.array(list(self._waterfall_data))
        times = np.array(list(self._waterfall_timestamps))
        now = time.time()
        time_diffs = now - times
        
        self._ax.clear()
        self._ax.set_xlabel("Channel (nRF24)", fontsize=10)
        self._ax.set_ylabel("Time (s ago)", fontsize=10)
        self._ax.grid(True, alpha=0.2, linestyle=':')
        
        # Create the heatmap
        extent = [
            0, 
            max(time_diffs) if len(time_diffs) > 0 else 60,
            self._channels[0] - 0.5, 
            self._channels[-1] + 0.5
        ]
        
        self._wf_image = self._ax.imshow(
            data.T,
            aspect="auto",
            origin="lower",
            extent=extent,
            cmap=self._cmap,
            vmin=0,
            vmax=100,
            interpolation='nearest'
        )
        
        # WiFi channel markers as vertical lines
        for wifi_ch, freq in self._wifi_channels.items():
            nrf_ch = freq - 2400
            if self._config.channel.start_channel <= nrf_ch <= self._config.channel.end_channel:
                self._ax.axvline(x=nrf_ch, color="#1976d2", linestyle="--", alpha=0.6, linewidth=1.5)
                self._ax.text(nrf_ch, extent[3] + 1.5, f"WiFi {wifi_ch}", 
                            rotation=90, va="bottom", ha="center", fontsize=7, color="#1976d2")
        
        # Channel blocked markers (red X markers)
        blocked_channels = self._blocklist.get_blocked_channels()
        for ch in blocked_channels:
            if ch in self._channels:
                self._ax.plot(ch, -1, 'rx', markersize=8, markeredgewidth=2, alpha=0.8)
        
        self._ax.set_ylim(self._channels[0] - 0.5, self._channels[-1] + 0.5)
        self._ax.set_xlim(0, max(time_diffs) if len(time_diffs) > 0 else 60)
        
        # Single unified colorbar on the right
        if self._cbar is None:
            self._cbar_ax = self._fig.add_axes([0.87, 0.15, 0.02, 0.7])
            self._cbar = self._fig.colorbar(
                self._wf_image, 
                cax=self._cbar_ax, 
                label="Activity (%)"
            )
            self._cbar.ax.tick_params(labelsize=8)
        else:
            self._cbar.update_normal(self._wf_image)
        
        self._fig.tight_layout(rect=[0, 0, 0.85, 1])
        self._canvas.draw_idle()
    
    def export_png(self, path: str) -> None:
        """Export waterfall as PNG."""
        self._fig.savefig(path, dpi=150, bbox_inches="tight")
    
    def clear(self) -> None:
        """Clear waterfall data."""
        self._waterfall_data.clear()
        self._waterfall_timestamps.clear()
        self._ax.clear()
        self._ax.set_xlabel("Channel (nRF24)")
        self._ax.set_ylabel("Time (s ago)")
        self._ax.grid(True, alpha=0.2)
        self._canvas.draw_idle()


class SpectrumWidget:
    """Clean live spectrum bar graph."""
    
    WIFI_CHANNELS = {1: 2412, 6: 2437, 11: 2462}
    
    def __init__(
        self,
        parent: ttk.Frame,
        config: AppConfig,
        spectrum_data: SpectrumData,
        blocklist: BlocklistManager,
    ):
        self._config = config
        self._spectrum_data = spectrum_data
        self._blocklist = blocklist
        
        self._create_ui(parent)
    
    def _create_ui(self, parent: ttk.Frame) -> None:
        """Create the spectrum widget UI."""
        self._frame = ttk.Frame(parent)
        self._frame.pack(fill=tk.BOTH, expand=True)
        
        self._fig = Figure(figsize=(10, 3), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasTkAgg(self._fig, self._frame)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self._ax.set_xlabel("Channel (nRF24)", fontsize=10)
        self._ax.set_ylabel("Activity (%)", fontsize=10)
        self._ax.set_ylim(0, 100)
        self._ax.grid(True, alpha=0.2, linestyle=':')
        
        self._bars = None
    
    @property
    def frame(self) -> ttk.Frame:
        return self._frame
    
    def update(self, observations: dict = None) -> None:
        """Update the spectrum graph."""
        if observations is None:
            observations = self._spectrum_data.get_all_observations()
        
        channels = self._spectrum_data.get_channels_in_range()
        
        self._ax.clear()
        self._ax.set_xlabel("Channel (nRF24)", fontsize=10)
        self._ax.set_ylabel("Activity (%)", fontsize=10)
        self._ax.set_ylim(0, 100)
        self._ax.grid(True, alpha=0.2, linestyle=':')
        self._ax.set_title(
            f"Live Spectrum — {self._spectrum_data.get_backend().upper()}", 
            fontsize=11, fontweight='bold', pad=10
        )
        
        activities = []
        colors = []
        for ch in channels:
            obs = observations.get(ch)
            blocked = self._blocklist.is_blocked(ch)
            
            if obs and obs.activity_percentage is not None:
                activities.append(obs.activity_percentage)
            else:
                activities.append(0)
            
            # Clean color scheme
            if blocked:
                colors.append("#b71c1c")  # Dark red for blocked
            elif obs and obs.status == "Heavy Load":
                colors.append("#c62828")  # Red
            elif obs and obs.status == "Busy":
                colors.append("#ef6c00")  # Orange
            elif obs and obs.status == "Moderate":
                colors.append("#f9a825")  # Amber
            elif obs and obs.status == "Clear":
                colors.append("#2e7d32")  # Green
            else:
                colors.append("#757575")  # Grey
        
        self._bars = self._ax.bar(
            channels, activities, color=colors, width=0.85, 
            edgecolor="white", linewidth=0.3
        )
        
        # WiFi channel markers
        for wifi_ch, freq in self.WIFI_CHANNELS.items():
            nrf_ch = freq - 2400
            if self._config.channel.start_channel <= nrf_ch <= self._config.channel.end_channel:
                self._ax.axvline(x=nrf_ch, color="#1976d2", linestyle="--", alpha=0.6, linewidth=1.5)
                self._ax.text(nrf_ch, 103, f"WiFi {wifi_ch}", 
                            rotation=90, va="bottom", ha="center", fontsize=7, color="#1976d2")
        
        # Threshold lines with subtle styling
        for threshold, label, color in [
            (self._config.thresholds.clear_max, "Clear", "#2e7d32"),
            (self._config.thresholds.moderate_max, "Moderate", "#f9a825"),
            (self._config.thresholds.busy_max, "Busy", "#ef6c00"),
        ]:
            self._ax.axhline(y=threshold, color=color, linestyle=":", alpha=0.4, linewidth=1)
            self._ax.text(self._config.channel.end_channel + 0.5, threshold + 1, label, 
                        fontsize=7, color=color, va="bottom")
        
        self._ax.set_xlim(self._config.channel.start_channel - 0.5, self._config.channel.end_channel + 0.5)
        self._fig.tight_layout()
        self._canvas.draw_idle()
    
    def export_png(self, path: str) -> None:
        """Export spectrum as PNG."""
        self._fig.savefig(path, dpi=150, bbox_inches="tight")


class ChannelTableWidget:
    """Enhanced channel table with status badges and zebra striping."""
    
    STATUS_COLORS = {
        "Clear": {"bg": "#e8f5e9", "fg": "#1b5e20", "badge": "#2e7d32"},
        "Moderate": {"bg": "#fff8e1", "fg": "#f57f17", "badge": "#f9a825"},
        "Busy": {"bg": "#fff3e0", "fg": "#e65100", "badge": "#ef6c00"},
        "Heavy Load": {"bg": "#fbe9e7", "fg": "#bf360c", "badge": "#c62828"},
        "INSUFFICIENT DATA": {"bg": "#f5f5f5", "fg": "#616161", "badge": "#757575"},
        "SENSOR_ERROR": {"bg": "#fdecea", "fg": "#c62828", "badge": "#c62828"},
        "Pending": {"bg": "#f5f5f5", "fg": "#9e9e9e", "badge": "#9e9e9e"},
        "BLOCKED": {"bg": "#fce4ec", "fg": "#ad1457", "badge": "#c62828"},
    }
    
    def __init__(
        self,
        parent: ttk.Frame,
        config: AppConfig,
        spectrum_data: SpectrumData,
        channel_selector,
        blocklist,
        data_service,
    ):
        self._config = config
        self._spectrum_data = spectrum_data
        self._channel_selector = channel_selector
        self._blocklist = blocklist
        self._data_service = data_service
        
        self._sort_column = "channel"
        self._sort_reverse = False
        self._search_filter = ""
        self._status_filter = "All"
        
        self._create_ui(parent)
    
    @property
    def frame(self) -> ttk.Frame:
        return self._frame
    
    def _create_ui(self, parent: ttk.Frame) -> None:
        """Create the channel table UI with modern styling."""
        self._frame = ttk.Frame(parent)
        
        # Filter toolbar - compact and clean
        filter_frame = ttk.Frame(self._frame)
        filter_frame.pack(fill=tk.X, padx=8, pady=(8, 4))
        
        ttk.Label(filter_frame, text="Search:", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self._search_var, width=18)
        search_entry.pack(side=tk.LEFT, padx=(0, 12))
        search_entry.bind("<KeyRelease>", self._on_search_change)
        
        ttk.Label(filter_frame, text="Status:", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self._status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(
            filter_frame, textvariable=self._status_filter_var,
            values=["All", "Clear", "Moderate", "Busy", "Heavy Load", "INSUFFICIENT DATA", "SENSOR_ERROR", "BLOCKED"],
            width=18, state="readonly", font=("Segoe UI", 9)
        )
        status_combo.pack(side=tk.LEFT, padx=(0, 12))
        status_combo.bind("<<ComboboxSelected>>", self._on_status_filter_change)
        
        ttk.Button(filter_frame, text="Clear", command=self._clear_filters).pack(side=tk.LEFT)
        
        # Channel count label
        self._count_var = tk.StringVar(value="126 channels")
        ttk.Label(filter_frame, textvariable=self._count_var, font=("Segoe UI", 9), foreground="#616161").pack(side=tk.RIGHT, padx=8)
        
        # Table with columns optimized for badge display
        columns = ("channel", "frequency", "activity_pct", "status_badge", "samples", "rpd_pos", "eligible", "blocked")
        self._tree = ttk.Treeview(self._frame, columns=columns, show="headings", selectmode="browse")
        
        self._tree.heading("channel", text="Ch", command=lambda: self._sort_table("channel"))
        self._tree.heading("frequency", text="Freq (MHz)", command=lambda: self._sort_table("frequency"))
        self._tree.heading("activity_pct", text="Activity (%)", command=lambda: self._sort_table("activity_pct"))
        self._tree.heading("status_badge", text="Status")
        self._tree.heading("samples", text="Samples")
        self._tree.heading("rpd_pos", text="RPD+")
        self._tree.heading("eligible", text="Eligible")
        self._tree.heading("blocked", text="Blocked")
        
        # Column widths
        self._tree.column("channel", width=50, anchor=tk.CENTER, minwidth=45)
        self._tree.column("frequency", width=85, anchor=tk.CENTER, minwidth=80)
        self._tree.column("activity_pct", width=95, anchor=tk.CENTER, minwidth=90)
        self._tree.column("status_badge", width=120, anchor=tk.CENTER, minwidth=110)
        self._tree.column("samples", width=70, anchor=tk.CENTER, minwidth=65)
        self._tree.column("rpd_pos", width=60, anchor=tk.CENTER, minwidth=55)
        self._tree.column("eligible", width=70, anchor=tk.CENTER, minwidth=65)
        self._tree.column("blocked", width=70, anchor=tk.CENTER, minwidth=65)
        
        # Scrollbars
        vsb = ttk.Scrollbar(self._frame, orient=tk.VERTICAL, command=self._tree.yview)
        hsb = ttk.Scrollbar(self._frame, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self._tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")
        
        self._frame.grid_rowconfigure(1, weight=1)
        self._frame.grid_columnconfigure(0, weight=1)
        
        # Tag configurations with modern badge colors
        self._tree.tag_configure("clear", background="#fafafa")
        self._tree.tag_configure("moderate", background="#fafafa")
        self._tree.tag_configure("busy", background="#fafafa")
        self._tree.tag_configure("heavy", background="#fafafa")
        self._tree.tag_configure("insufficient", background="#fafafa")
        self._tree.tag_configure("error", background="#fafafa")
        self._tree.tag_configure("blocked", background="#fce4ec")
        self._tree.tag_configure("eligible", background="#e8f5e9")
        
        # Zebra striping tags
        self._tree.tag_configure("odd", background="#ffffff")
        self._tree.tag_configure("even", background="#fafafa")
    
    def _on_search_change(self, event=None) -> None:
        self._search_filter = self._search_var.get().lower()
        self.update()
    
    def _on_status_filter_change(self, event=None) -> None:
        self._status_filter = self._status_filter_var.get()
        self.update()
    
    def _clear_filters(self) -> None:
        self._search_var.set("")
        self._status_filter_var.set("All")
        self._search_filter = ""
        self._status_filter = "All"
        self.update()
    
    def _sort_table(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self.update()
    
    def update(self, observations: dict = None) -> None:
        """Update the channel table with modern badge styling."""
        if observations is None:
            observations = self._spectrum_data.get_all_observations()
        channels = self._spectrum_data.get_channels_in_range()
        
        # Apply filters
        filtered_channels = []
        for ch in channels:
            if self._search_filter and self._search_filter not in str(ch) and self._search_filter not in str(2400+ch):
                continue
            
            obs = observations.get(ch)
            status = obs.status if obs else "Pending"
            blocked = self._blocklist.is_blocked(ch)
            
            if self._status_filter != "All":
                if self._status_filter == "BLOCKED" and not blocked:
                    continue
                if self._status_filter != "BLOCKED" and status != self._status_filter:
                    continue
            
            filtered_channels.append(ch)
        
        # Sort
        if self._sort_column == "channel":
            filtered_channels.sort(reverse=self._sort_reverse)
        elif self._sort_column == "frequency":
            filtered_channels.sort(key=lambda c: 2400+c, reverse=self._sort_reverse)
        elif self._sort_column == "activity_pct":
            filtered_channels.sort(
                key=lambda c: observations.get(c).activity_percentage if observations.get(c) and observations.get(c).activity_percentage is not None else -1,
                reverse=self._sort_reverse
            )
        elif self._sort_column == "status_badge":
            filtered_channels.sort(
                key=lambda c: observations.get(c).status if observations.get(c) else "",
                reverse=self._sort_reverse
            )
        
        existing = set(self._tree.get_children())
        needed = set(str(ch) for ch in filtered_channels)
        
        for idx, ch in enumerate(filtered_channels):
            obs = observations.get(ch)
            blocked = self._blocklist.is_blocked(ch)
            assessment = self._channel_selector.assess_channel(ch, obs)
            
            iid = str(ch)
            if obs:
                activity_str = f"{obs.activity_percentage:.1f}%" if obs.activity_percentage is not None else "N/A"
                status = obs.status
                badge_text = self._get_status_badge(status, blocked, assessment.eligible)
                tag = self._get_row_tag(obs, blocked, assessment.eligible)
                
                # Zebra striping
                if idx % 2 == 1:
                    tag = (tag, "even")
                else:
                    tag = (tag, "odd")
                
                values = (
                    ch, obs.frequency_mhz, activity_str, badge_text,
                    obs.valid_samples, obs.rpd_positive,
                    "✓" if assessment.eligible else "✗",
                    "🔒" if blocked else "✓",
                )
            else:
                tag = ("insufficient", "odd" if idx % 2 == 1 else "even")
                values = (ch, 2400+ch, "N/A", "⏳ Pending", 0, 0, "✗", "🔒" if blocked else "✓")
            
            if iid in existing:
                self._tree.item(iid, values=values, tags=tag)
            else:
                self._tree.insert("", tk.END, iid=iid, values=values, tags=tag)
        
        for iid in existing - needed:
            self._tree.delete(iid)
        
        self._count_var.set(f"{len(filtered_channels)}/{len(channels)} channels")
    
    def _get_status_badge(self, status: str, blocked: bool, eligible: bool) -> str:
        """Return status text with badge styling."""
        if blocked:
            return "🔒 BLOCKED"
        if status == "INSUFFICIENT DATA":
            return "⚠ INSUFFICIENT"
        if status == "SENSOR_ERROR":
            return "✗ ERROR"
        if status == "Clear" and eligible:
            return "✓ CLEAR"
        if status == "Moderate":
            return "◐ MODERATE"
        if status == "Busy":
            return "◑ BUSY"
        if status == "Heavy Load":
            return "● HEAVY"
        return status
    
    def _get_row_tag(self, obs: ChannelObservation, blocked: bool, eligible: bool) -> str:
        if blocked:
            return "blocked"
        if obs.error:
            return "error"
        if not obs.data_sufficient:
            return "insufficient"
        if eligible:
            return "eligible"
        status = obs.status.lower().replace(" ", "")
        if status in ("clear", "moderate", "busy", "heavyload"):
            return status
        return ""
    
    def refresh(self) -> None:
        self.update()


class ExportDropdown(ttk.Menubutton):
    """Clean export dropdown menu button."""
    
    def __init__(self, parent, commands: dict):
        super().__init__(parent, text="Export ▼", direction="below")
        self.menu = tk.Menu(self, tearoff=0)
        self["menu"] = self.menu
        
        for label, command in commands.items():
            self.menu.add_command(label=label, command=command)
        
        self.menu.add_separator()
        self.menu.add_command(label="Export All Formats...", command=commands.get("export_all", lambda: None))
        
        # Style
        self.configure(style="Export.TMenubutton")


class ControlGroup(ttk.LabelFrame):
    """Styled control group for toolbar organization."""
    
    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, text=title, padding=(10, 5), **kwargs)
        self._widgets = []
    
    def add_widget(self, widget, side=tk.LEFT, **pack_kwargs):
        default_pad = {"padx": 4, "pady": 2}
        default_pad.update(pack_kwargs)
        widget.pack(side=side, **default_pad)
        self._widgets.append(widget)
    
    def add_separator(self):
        sep = ttk.Separator(self, orient=tk.VERTICAL)
        sep.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=2)
        return sep


class StatusBar(ttk.Frame):
    """Clean status bar with progress indicator."""
    
    def __init__(self, parent):
        super().__init__(parent, relief=tk.FLAT, padding=(8, 4))
        
        self._status_var = tk.StringVar(value="Ready")
        self._mode_var = tk.StringVar(value="SIM")
        
        # Left side - status
        self._status_label = ttk.Label(self, textvariable=self._status_var, font=("Segoe UI", 9))
        self._status_label.pack(side=tk.LEFT)
        
        # Right side - mode indicator
        self._mode_label = ttk.Label(self, textvariable=self._mode_var, font=("Segoe UI", 9, "bold"), foreground="#1976d2")
        self._mode_label.pack(side=tk.RIGHT, padx=12)
    
    def set_status(self, status: str) -> None:
        self._status_var.set(status)
    
    def set_mode(self, mode: str) -> None:
        self._mode_var.set(mode.upper())


class CollapsiblePanel(ttk.Frame):
    """Collapsible panel for saving vertical space."""
    
    def __init__(self, parent, title: str, initially_open: bool = True):
        super().__init__(parent)
        
        self._title = title
        self._is_open = initially_open
        
        # Header with toggle button
        self._header = ttk.Frame(self)
        self._header.pack(fill=tk.X)
        
        self._toggle_btn = ttk.Button(
            self._header, text="▼" if initially_open else "▶",
            width=3, command=self._toggle
        )
        self._toggle_btn.pack(side=tk.LEFT, padx=4, pady=2)
        
        self._title_label = ttk.Label(self._header, text=title, font=("Segoe UI", 10, "bold"))
        self._title_label.pack(side=tk.LEFT, padx=8, pady=2)
        
        # Content frame
        self._content = ttk.Frame(self)
        if initially_open:
            self._content.pack(fill=tk.BOTH, expand=True)
    
    def _toggle(self) -> None:
        self._is_open = not self._is_open
        self._toggle_btn.config(text="▼" if self._is_open else "▶")
        if self._is_open:
            self._content.pack(fill=tk.BOTH, expand=True)
        else:
            self._content.pack_forget()
    
    @property
    def content(self) -> ttk.Frame:
        return self._content