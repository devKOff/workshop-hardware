"""Tkinter GUI application for RF Spectrum Visualizer v6."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import time
import threading
import logging
from typing import Optional, List, Dict, Any, Set
from collections import deque

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from .config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, BlocklistConfig, StorageConfig
from .scanner import ScannerThread, SpectrumData, ChannelObservation
from .sim_radio import SimRadio, ScenarioType
from .hardware_radio import HardwareRadio, check_hardware_availability
from .blocklist_manager import BlocklistManager
from .channel_selector import ChannelSelector, ChannelEligibility, EligibilityReason
from .report_generator import ReportGenerator
from .channel_utils import validate_channel, format_channel, parse_channel_input
from .exceptions import HardwareError, ScannerError, InvalidChannelError, BlocklistError
from .logging_config import setup_logging, get_logger

logger = get_logger("rf_visualizer.gui")


class ChannelTableModel:
    """Data model for the channel table."""
    
    def __init__(self, config: AppConfig):
        self._config = config
        self._observations: Dict[int, ChannelObservation] = {}
        self._lock = threading.RLock()
    
    def update(self, observations: Dict[int, ChannelObservation]) -> None:
        with self._lock:
            self._observations = observations
    
    def get_row_data(self, channel: int) -> Optional[Dict]:
        with self._lock:
            obs = self._observations.get(channel)
            if not obs:
                return None
            return {
                "channel": obs.channel,
                "frequency": obs.frequency_mhz,
                "activity_pct": obs.activity_percentage,
                "status": obs.status,
                "valid_samples": obs.valid_samples,
                "rpd_positive": obs.rpd_positive,
                "data_sufficient": obs.data_sufficient,
                "error": obs.error,
            }
    
    def get_all_channels(self) -> List[int]:
        with self._lock:
            return sorted(self._observations.keys())


class SpectrumVisualizerApp:
    """Main GUI application."""
    
    WIFI_CHANNELS = {
        1: 2412,
        6: 2437,
        11: 2462,
    }
    
    def __init__(self, config: AppConfig):
        self._config = config
        self._root = tk.Tk()
        self._root.title("RF Spectrum Visualizer v6 - 2.4 GHz ISM Band")
        self._root.geometry("1400x900")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._spectrum_data = SpectrumData(config)
        self._scanner: Optional[ScannerThread] = None
        self._radio = None
        self._blocklist = BlocklistManager(config.blocklist)
        self._channel_selector = ChannelSelector(config.channel, config.thresholds, self._blocklist)
        self._report_gen = ReportGenerator(config, self._spectrum_data, self._blocklist, self._channel_selector)
        self._table_model = ChannelTableModel(config)
        
        self._refresh_job: Optional[str] = None
        self._running = False
        self._waterfall_data: deque = deque(maxlen=config.gui.waterfall_history_size)
        self._waterfall_timestamps: deque = deque(maxlen=config.gui.waterfall_history_size)
        
        self._sort_column = "channel"
        self._sort_reverse = False
        self._search_filter = ""
        self._status_filter = "All"
        
        self._setup_logging()
        self._build_ui()
        self._update_ui_state()
        self._refresh_blocklist_display()
    
    def _setup_logging(self) -> None:
        setup_logging(
            log_path=self._config.storage.log_path,
            level=logging.INFO,
            console_level=logging.WARNING,
        )
    
    def _build_ui(self) -> None:
        """Build the main UI layout."""
        self._create_menu()
        self._create_toolbar()
        self._create_main_panes()
        self._create_status_bar()
    
    def _create_menu(self) -> None:
        menubar = tk.Menu(self._root)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Export All Formats...", command=self._export_all_formats)
        file_menu.add_command(label="Export JSON...", command=self._export_json)
        file_menu.add_command(label="Export CSV...", command=self._export_csv)
        file_menu.add_command(label="Export PNG (Spectrum)...", command=lambda: self._export_png("spectrum"))
        file_menu.add_command(label="Export PNG (Waterfall)...", command=lambda: self._export_png("waterfall"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Clear History", command=self._clear_history)
        view_menu.add_command(label="Reset Peak Tracking", command=self._reset_peaks)
        menubar.add_cascade(label="View", menu=view_menu)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Hardware Diagnostic", command=self._run_diagnostic)
        tools_menu.add_command(label="Run Simulation Scenario", command=self._run_simulation_dialog)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self._root.config(menu=menubar)
    
    def _create_toolbar(self) -> None:
        toolbar = ttk.Frame(self._root)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(toolbar, text="Backend:").pack(side=tk.LEFT, padx=2)
        self._backend_var = tk.StringVar(value=self._config.default_backend)
        backend_combo = ttk.Combobox(
            toolbar, textvariable=self._backend_var,
            values=["sim", "hardware"], width=10, state="readonly"
        )
        backend_combo.pack(side=tk.LEFT, padx=2)
        backend_combo.bind("<<ComboboxSelected>>", self._on_backend_change)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        self._start_btn = ttk.Button(toolbar, text="Start Scanning", command=self._start_scanning)
        self._start_btn.pack(side=tk.LEFT, padx=2)
        
        self._stop_btn = ttk.Button(toolbar, text="Stop", command=self._stop_scanning, state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Label(toolbar, text="Channels:").pack(side=tk.LEFT, padx=2)
        self._start_ch_var = tk.IntVar(value=self._config.channel.start_channel)
        ttk.Spinbox(toolbar, from_=0, to=125, textvariable=self._start_ch_var, width=5).pack(side=tk.LEFT)
        ttk.Label(toolbar, text="-").pack(side=tk.LEFT)
        self._end_ch_var = tk.IntVar(value=self._config.channel.end_channel)
        ttk.Spinbox(toolbar, from_=0, to=125, textvariable=self._end_ch_var, width=5).pack(side=tk.LEFT)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Label(toolbar, text="Window (s):").pack(side=tk.LEFT, padx=2)
        self._window_var = tk.DoubleVar(value=self._config.scan.measurement_window)
        ttk.Spinbox(toolbar, from_=0.1, to=10.0, increment=0.1, textvariable=self._window_var, width=5).pack(side=tk.LEFT)
        
        ttk.Label(toolbar, text="Interval (ms):").pack(side=tk.LEFT, padx=2)
        self._interval_var = tk.DoubleVar(value=self._config.scan.sampling_interval * 1000)
        ttk.Spinbox(toolbar, from_=1, to=1000, increment=1, textvariable=self._interval_var, width=6).pack(side=tk.LEFT)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Button(toolbar, text="Export All", command=self._export_all_formats).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export JSON", command=self._export_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export PNG", command=lambda: self._export_png("spectrum")).pack(side=tk.LEFT, padx=2)
    
    def _create_main_panes(self) -> None:
        main_paned = ttk.PanedWindow(self._root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)
        
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        self._create_left_pane(left_frame)
        self._create_right_pane(right_frame)
    
    def _create_left_pane(self, parent: ttk.Frame) -> None:
        """Create left pane with controls, table and spectrum graph."""
        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Blocklist controls
        block_frame = ttk.LabelFrame(paned, text="Channel Blocklist Control")
        paned.add(block_frame, weight=0)
        self._create_blocklist_controls(block_frame)
        
        # Channel table
        table_frame = ttk.LabelFrame(paned, text="Channel Activity (126 channels)")
        paned.add(table_frame, weight=2)
        self._create_channel_table(table_frame)
        
        # Spectrum graph
        spectrum_frame = ttk.LabelFrame(paned, text="Live Spectrum")
        paned.add(spectrum_frame, weight=1)
        self._create_spectrum_graph(spectrum_frame)
    
    def _create_blocklist_controls(self, parent: ttk.Frame) -> None:
        """Create blocklist control panel."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(frame, text="Channel:").pack(side=tk.LEFT, padx=2)
        self._block_ch_var = tk.StringVar()
        block_entry = ttk.Entry(frame, textvariable=self._block_ch_var, width=15)
        block_entry.pack(side=tk.LEFT, padx=2)
        block_entry.bind("<Return>", lambda e: self._block_channel())
        
        ttk.Button(frame, text="Block Channel", command=self._block_channel).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame, text="Unblock Channel", command=self._unblock_channel).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame, text="Check Channel", command=self._check_channel).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Label(frame, text="Reason:").pack(side=tk.LEFT, padx=2)
        self._block_reason_var = tk.StringVar(value="User blocked")
        ttk.Entry(frame, textvariable=self._block_reason_var, width=20).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self._block_status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self._block_status_var, foreground="blue").pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Button(frame, text="Refresh Blocklist", command=self._refresh_blocklist_display).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame, text="Clear All Blocks", command=self._clear_all_blocks).pack(side=tk.LEFT, padx=2)
    
    def _create_right_pane(self, parent: ttk.Frame) -> None:
        """Create right pane with waterfall, recommendations, and alerts."""
        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Recommendations
        rec_frame = ttk.LabelFrame(paned, text="Channel Recommendations")
        paned.add(rec_frame, weight=0)
        self._create_recommendations_panel(rec_frame)
        
        # Waterfall
        waterfall_frame = ttk.LabelFrame(paned, text="Waterfall (Time vs Frequency)")
        paned.add(waterfall_frame, weight=2)
        self._create_waterfall_graph(waterfall_frame)
        
        # Alerts
        alerts_frame = ttk.LabelFrame(paned, text="Alerts & Diagnostics")
        paned.add(alerts_frame, weight=1)
        self._create_alerts_panel(alerts_frame)
    
    def _create_recommendations_panel(self, parent: ttk.Frame) -> None:
        """Create recommendations display panel."""
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._rec_text = tk.Text(frame, height=6, wrap=tk.WORD, state=tk.DISABLED, font=("Consolas", 9))
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._rec_text.yview)
        self._rec_text.configure(yscrollcommand=vsb.set)
        
        self._rec_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        self._update_recommendations_display()
    
    def _create_channel_table(self, parent: ttk.Frame) -> None:
        """Create the channel activity table with sorting and filtering."""
        # Filter controls
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(filter_frame, text="Search:").pack(side=tk.LEFT, padx=2)
        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self._search_var, width=15)
        search_entry.pack(side=tk.LEFT, padx=2)
        search_entry.bind("<KeyRelease>", self._on_search_change)
        
        ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT, padx=2)
        self._status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(
            filter_frame, textvariable=self._status_filter_var,
            values=["All", "Clear", "Moderate", "Busy", "Heavy Load", "INSUFFICIENT DATA", "SENSOR_ERROR", "BLOCKED"],
            width=15, state="readonly"
        )
        status_combo.pack(side=tk.LEFT, padx=2)
        status_combo.bind("<<ComboboxSelected>>", self._on_status_filter_change)
        
        ttk.Button(filter_frame, text="Clear Filters", command=self._clear_filters).pack(side=tk.LEFT, padx=5)
        
        # Table
        columns = ("channel", "frequency", "activity_bar", "activity_pct", "status", "samples", "rpd_pos", "sufficient", "eligible", "blocked")
        self._tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        
        self._tree.heading("channel", text="Ch", command=lambda: self._sort_table("channel"))
        self._tree.heading("frequency", text="Freq (MHz)", command=lambda: self._sort_table("frequency"))
        self._tree.heading("activity_bar", text="Activity")
        self._tree.heading("activity_pct", text="%", command=lambda: self._sort_table("activity_pct"))
        self._tree.heading("status", text="Status", command=lambda: self._sort_table("status"))
        self._tree.heading("samples", text="Samples")
        self._tree.heading("rpd_pos", text="RPD+")
        self._tree.heading("sufficient", text="Data OK")
        self._tree.heading("eligible", text="Eligible")
        self._tree.heading("blocked", text="Blocked")
        
        self._tree.column("channel", width=40, anchor=tk.CENTER)
        self._tree.column("frequency", width=70, anchor=tk.CENTER)
        self._tree.column("activity_bar", width=150)
        self._tree.column("activity_pct", width=50, anchor=tk.CENTER)
        self._tree.column("status", width=100, anchor=tk.CENTER)
        self._tree.column("samples", width=60, anchor=tk.CENTER)
        self._tree.column("rpd_pos", width=50, anchor=tk.CENTER)
        self._tree.column("sufficient", width=60, anchor=tk.CENTER)
        self._tree.column("eligible", width=60, anchor=tk.CENTER)
        self._tree.column("blocked", width=60, anchor=tk.CENTER)
        
        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._tree.yview)
        hsb = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self._tree.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        hsb.grid(row=2, column=0, sticky="ew")
        
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        # Tags for coloring
        self._tree.tag_configure("clear", background="#e8f5e9")
        self._tree.tag_configure("moderate", background="#fff3e0")
        self._tree.tag_configure("busy", background="#ffebee")
        self._tree.tag_configure("heavy", background="#fce4ec")
        self._tree.tag_configure("insufficient", background="#f5f5f5")
        self._tree.tag_configure("error", background="#ffcdd2")
        self._tree.tag_configure("blocked", background="#ffcdd2")
        self._tree.tag_configure("eligible", background="#e3f2fd")
    
    def _create_spectrum_graph(self, parent: ttk.Frame) -> None:
        """Create the live spectrum bar graph."""
        self._spec_fig = Figure(figsize=(8, 3), dpi=100)
        self._spec_ax = self._spec_fig.add_subplot(111)
        self._spec_canvas = FigureCanvasTkAgg(self._spec_fig, parent)
        self._spec_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self._spec_ax.set_xlabel("Channel (nRF24)")
        self._spec_ax.set_ylabel("Activity (%)")
        self._spec_ax.set_ylim(0, 100)
        self._spec_ax.grid(True, alpha=0.3)
        
        self._spec_bars = None
    
    def _create_waterfall_graph(self, parent: ttk.Frame) -> None:
        """Create the waterfall visualization."""
        self._wf_fig = Figure(figsize=(8, 3), dpi=100)
        self._wf_ax = self._wf_fig.add_subplot(111)
        self._wf_canvas = FigureCanvasTkAgg(self._wf_fig, parent)
        self._wf_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self._wf_ax.set_xlabel("Channel (nRF24)")
        self._wf_ax.set_ylabel("Time (s ago)")
        self._wf_ax.grid(True, alpha=0.3)
        
        self._wf_image = None
        self._wf_cmap = LinearSegmentedColormap.from_list(
            "rf_cmap", ["#000000", "#0000ff", "#00ffff", "#ffff00", "#ff0000"]
        )
    
    def _create_alerts_panel(self, parent: ttk.Frame) -> None:
        """Create alerts and diagnostics panel."""
        self._alerts_text = tk.Text(parent, height=10, wrap=tk.WORD, state=tk.DISABLED)
        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._alerts_text.yview)
        self._alerts_text.configure(yscrollcommand=vsb.set)
        
        self._alerts_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        self._log_message("RF Spectrum Visualizer v6 ready. Select backend and press Start.")
    
    def _create_status_bar(self) -> None:
        self._status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self._root, textvariable=self._status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
    
    def _update_ui_state(self) -> None:
        """Update UI element states based on running state."""
        if self._running:
            self._start_btn.config(state=tk.DISABLED)
            self._stop_btn.config(state=tk.NORMAL)
            self._status_var.set(f"Scanning... ({self._spectrum_data.get_backend().upper()})")
        else:
            self._start_btn.config(state=tk.NORMAL)
            self._stop_btn.config(state=tk.DISABLED)
            self._status_var.set("Stopped")
    
    def _on_backend_change(self, event=None) -> None:
        if self._running:
            messagebox.showwarning("Cannot Change", "Stop scanning before changing backend")
            self._backend_var.set(self._config.default_backend)
            return
        self._config.default_backend = self._backend_var.get()
        logger.info(f"Backend changed to {self._config.default_backend}")
    
    def _block_channel(self) -> None:
        """Block the entered channel."""
        try:
            channel = parse_channel_input(self._block_ch_var.get())
        except ValueError as e:
            self._block_status_var.set(f"Error: {e}")
            return
        
        try:
            entry = self._blocklist.block_channel(channel, self._block_reason_var.get())
            self._block_status_var.set(f"Blocked {format_channel(channel)} - {entry.reason}")
            self._refresh_blocklist_display()
            self._update_table()
            self._update_recommendations_display()
        except (InvalidChannelError, BlocklistError) as e:
            self._block_status_var.set(f"Error: {e}")
    
    def _unblock_channel(self) -> None:
        """Unblock the entered channel."""
        try:
            channel = parse_channel_input(self._block_ch_var.get())
        except ValueError as e:
            self._block_status_var.set(f"Error: {e}")
            return
        
        try:
            if self._blocklist.unblock_channel(channel):
                self._block_status_var.set(f"Unblocked {format_channel(channel)}")
            else:
                self._block_status_var.set(f"{format_channel(channel)} was not blocked")
            self._refresh_blocklist_display()
            self._update_table()
            self._update_recommendations_display()
        except (InvalidChannelError, BlocklistError) as e:
            self._block_status_var.set(f"Error: {e}")
    
    def _check_channel(self) -> None:
        """Check channel block status."""
        try:
            channel = parse_channel_input(self._block_ch_var.get())
        except ValueError as e:
            self._block_status_var.set(f"Error: {e}")
            return
        
        blocked = self._blocklist.is_blocked(channel)
        entry = self._blocklist.get_entry(channel)
        
        if blocked:
            self._block_status_var.set(f"{format_channel(channel)} is BLOCKED (since {entry.blocked_at})")
        else:
            self._block_status_var.set(f"{format_channel(channel)} is NOT blocked")
    
    def _refresh_blocklist_display(self) -> None:
        """Refresh blocklist display in table."""
        self._update_table()
    
    def _clear_all_blocks(self) -> None:
        """Clear all blocked channels."""
        if messagebox.askyesno("Confirm", "Clear all blocked channels?"):
            count = self._blocklist.clear()
            self._block_status_var.set(f"Cleared {count} blocked channels")
            self._refresh_blocklist_display()
            self._update_table()
            self._update_recommendations_display()
    
    def _on_search_change(self, event=None) -> None:
        self._search_filter = self._search_var.get().lower()
        self._update_table()
    
    def _on_status_filter_change(self, event=None) -> None:
        self._status_filter = self._status_filter_var.get()
        self._update_table()
    
    def _clear_filters(self) -> None:
        self._search_var.set("")
        self._status_filter_var.set("All")
        self._search_filter = ""
        self._status_filter = "All"
        self._update_table()
    
    def _sort_table(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self._update_table()
    
    def _start_scanning(self) -> None:
        if self._running:
            return
        
        try:
            self._config.channel.start_channel = self._start_ch_var.get()
            self._config.channel.end_channel = self._end_ch_var.get()
            self._config.scan.measurement_window = self._window_var.get()
            self._config.scan.sampling_interval = self._interval_var.get() / 1000.0
            
            if self._config.default_backend == "hardware":
                self._radio = HardwareRadio(self._config.channel, self._config.scan, self._config.hardware)
                if not self._radio.is_available():
                    messagebox.showerror("Hardware Unavailable", "pyrf24 not installed or SPI unavailable")
                    return
            else:
                self._radio = SimRadio(self._config.channel, self._config.scan, self._config.sim)
            
            self._scanner = ScannerThread(
                self._config,
                self._spectrum_data,
                self._radio,
                on_observation=self._on_observation,
                on_error=self._on_scanner_error,
                on_scan_complete=self._on_scan_complete,
            )
            
            self._scanner.start()
            self._running = True
            self._update_ui_state()
            self._schedule_refresh()
            self._log_message(f"Started scanning with {self._config.default_backend} backend")
            
        except Exception as e:
            logger.error(f"Failed to start scanner: {e}")
            messagebox.showerror("Error", f"Failed to start scanning: {e}")
    
    def _stop_scanning(self) -> None:
        if not self._running:
            return
        
        if self._scanner:
            self._scanner.shutdown()
            self._scanner = None
        
        if self._radio:
            self._radio.cleanup()
            self._radio = None
        
        self._running = False
        self._update_ui_state()
        if self._refresh_job:
            self._root.after_cancel(self._refresh_job)
            self._refresh_job = None
        self._log_message("Scanning stopped")
    
    def _schedule_refresh(self) -> None:
        if not self._running:
            return
        self._refresh_job = self._root.after(self._config.gui.refresh_interval_ms, self._refresh_ui)
    
    def _refresh_ui(self) -> None:
        if not self._running:
            return
        
        self._update_table()
        self._update_spectrum_graph()
        self._update_waterfall()
        self._update_recommendations_display()
        
        self._schedule_refresh()
    
    def _on_observation(self, obs: ChannelObservation) -> None:
        pass
    
    def _on_scanner_error(self, error: Exception) -> None:
        self._log_message(f"Scanner error: {error}", "ERROR")
    
    def _on_scan_complete(self) -> None:
        pass
    
    def _update_table(self) -> None:
        observations = self._spectrum_data.get_all_observations()
        self._table_model.update(observations)
        
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
        elif self._sort_column == "status":
            filtered_channels.sort(
                key=lambda c: observations.get(c).status if observations.get(c) else "",
                reverse=self._sort_reverse
            )
        
        existing = set(self._tree.get_children())
        needed = set(str(ch) for ch in filtered_channels)
        
        for ch in filtered_channels:
            obs = observations.get(ch)
            blocked = self._blocklist.is_blocked(ch)
            assessment = self._channel_selector.assess_channel(ch, obs)
            
            iid = str(ch)
            if obs:
                activity_str = f"{obs.activity_percentage:.1f}%" if obs.activity_percentage is not None else "N/A"
                bar = self._make_activity_bar(obs.activity_percentage)
                tag = self._get_status_tag(obs, blocked, assessment.eligible)
                values = (
                    ch, obs.frequency_mhz, bar, activity_str,
                    obs.status, obs.valid_samples, obs.rpd_positive,
                    "Yes" if obs.data_sufficient else "No",
                    "Yes" if assessment.eligible else "No",
                    "Yes" if blocked else "No",
                )
            else:
                values = (ch, 2400+ch, "", "N/A", "Pending", 0, 0, "No", "No", "Yes" if blocked else "No")
                tag = "blocked" if blocked else "insufficient"
            
            if iid in existing:
                self._tree.item(iid, values=values, tags=(tag,))
            else:
                self._tree.insert("", tk.END, iid=iid, values=values, tags=(tag,))
        
        for iid in existing - needed:
            self._tree.delete(iid)
    
    def _make_activity_bar(self, pct: Optional[float]) -> str:
        width = 20
        if pct is None:
            return "?" * width
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)
    
    def _get_status_tag(self, obs: ChannelObservation, blocked: bool, eligible: bool) -> str:
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
    
    def _update_spectrum_graph(self) -> None:
        observations = self._spectrum_data.get_all_observations()
        channels = self._spectrum_data.get_channels_in_range()
        
        self._spec_ax.clear()
        self._spec_ax.set_xlabel("Channel (nRF24)")
        self._spec_ax.set_ylabel("Activity (%)")
        self._spec_ax.set_ylim(0, 100)
        self._spec_ax.grid(True, alpha=0.3)
        self._spec_ax.set_title(f"Live Spectrum - {self._spectrum_data.get_backend().upper()}")
        
        activities = []
        colors = []
        for ch in channels:
            obs = observations.get(ch)
            blocked = self._blocklist.is_blocked(ch)
            
            if obs and obs.activity_percentage is not None:
                activities.append(obs.activity_percentage)
            else:
                activities.append(0)
            
            if blocked:
                colors.append("#b71c1c")
            elif obs and obs.status == "Heavy Load":
                colors.append("#ef5350")
            elif obs and obs.status == "Busy":
                colors.append("#ffa726")
            elif obs and obs.status == "Moderate":
                colors.append("#ffca28")
            elif obs and obs.status == "Clear":
                colors.append("#66bb6a")
            else:
                colors.append("#9e9e9e")
        
        bars = self._spec_ax.bar(channels, activities, color=colors, width=0.8, edgecolor="white", linewidth=0.5)
        self._spec_bars = bars
        
        for wifi_ch, freq in self.WIFI_CHANNELS.items():
            nrf_ch = freq - 2400
            if self._config.channel.start_channel <= nrf_ch <= self._config.channel.end_channel:
                self._spec_ax.axvline(x=nrf_ch, color="blue", linestyle="--", alpha=0.5, linewidth=1)
                self._spec_ax.text(nrf_ch, 102, f"WiFi {wifi_ch}", rotation=90, va="bottom", ha="center", fontsize=8, color="blue")
        
        for threshold, label, color in [
            (self._config.thresholds.clear_max, "Clear", "green"),
            (self._config.thresholds.moderate_max, "Moderate", "orange"),
            (self._config.thresholds.busy_max, "Busy", "red"),
        ]:
            self._spec_ax.axhline(y=threshold, color=color, linestyle=":", alpha=0.5, linewidth=1)
        
        self._spec_fig.tight_layout()
        self._spec_canvas.draw_idle()
    
    def _update_waterfall(self) -> None:
        observations = self._spectrum_data.get_all_observations()
        channels = self._spectrum_data.get_channels_in_range()
        
        now = time.time()
        row = []
        for ch in channels:
            obs = observations.get(ch)
            row.append(obs.activity_percentage if obs and obs.activity_percentage is not None else 0)
        self._waterfall_data.append(row)
        self._waterfall_timestamps.append(now)
        
        if len(self._waterfall_data) < 2:
            return
        
        self._wf_ax.clear()
        self._wf_ax.set_xlabel("Channel (nRF24)")
        self._wf_ax.set_ylabel("Time (s ago)")
        
        data = np.array(list(self._waterfall_data))
        times = np.array(list(self._waterfall_timestamps))
        time_diffs = now - times
        
        im = self._wf_ax.imshow(
            data.T,
            aspect="auto",
            origin="lower",
            extent=[0, max(time_diffs) if len(time_diffs) > 0 else 60, channels[0], channels[-1]],
            cmap=self._wf_cmap,
            vmin=0,
            vmax=100,
        )
        
        self._wf_ax.set_ylim(channels[0] - 0.5, channels[-1] + 0.5)
        self._wf_fig.colorbar(im, ax=self._wf_ax, label="Activity (%)")
        self._wf_fig.tight_layout()
        self._wf_canvas.draw_idle()
    
    def _update_recommendations_display(self) -> None:
        observations = self._spectrum_data.get_all_observations()
        recommendations = self._channel_selector.get_recommendations(observations, count=10)
        blocked_channels = self._blocklist.get_blocked_channels()
        
        self._rec_text.config(state=tk.NORMAL)
        self._rec_text.delete(1.0, tk.END)
        
        if not recommendations:
            self._rec_text.insert(tk.END, "NO ELIGIBLE CHANNELS\n")
            self._rec_text.insert(tk.END, "All channels are blocked or have high activity.\n")
        else:
            self._rec_text.insert(tk.END, "RECOMMENDED CHANNELS (lowest activity):\n")
            self._rec_text.insert(tk.END, "-" * 50 + "\n")
            for i, rec in enumerate(recommendations, 1):
                self._rec_text.insert(tk.END, 
                    f"{i:2d}. {format_channel(rec.channel)}  "
                    f"Activity: {rec.activity_percentage:.1f}%  "
                    f"Status: {rec.status}\n"
                )
            
            if blocked_channels:
                self._rec_text.insert(tk.END, f"\nBLOCKED: {blocked_channels}\n")
        
        self._rec_text.config(state=tk.DISABLED)
    
    def _log_message(self, message: str, level: str = "INFO") -> None:
        timestamp = time.strftime("%H:%M:%S")
        self._alerts_text.config(state=tk.NORMAL)
        self._alerts_text.insert(tk.END, f"[{timestamp}] {level}: {message}\n")
        self._alerts_text.see(tk.END)
        self._alerts_text.config(state=tk.DISABLED)
    
    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export CSV"
        )
        if path:
            try:
                self._report_gen.export_csv_file(path)
                messagebox.showinfo("Export", f"CSV exported to {path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def _export_json(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export JSON"
        )
        if path:
            try:
                self._report_gen.export_json_file(path)
                messagebox.showinfo("Export", f"JSON exported to {path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def _export_all_formats(self) -> None:
        base = filedialog.asksaveasfilename(
            defaultextension="",
            filetypes=[("All files", "*.*")],
            title="Export All Formats (base filename)"
        )
        if base:
            try:
                base_path = Path(base)
                results = self._report_gen.export_all_formats(base_path.stem)
                msg = "Exported:\n" + "\n".join(f"  {fmt}: {path}" for fmt, path in results.items())
                messagebox.showinfo("Export", msg)
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def _export_png(self, plot_type: str) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title=f"Export {plot_type.capitalize()} PNG"
        )
        if path:
            try:
                if plot_type == "spectrum":
                    self._spec_fig.savefig(path, dpi=150, bbox_inches="tight")
                else:
                    self._wf_fig.savefig(path, dpi=150, bbox_inches="tight")
                messagebox.showinfo("Export", f"PNG exported to {path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def _clear_history(self) -> None:
        self._spectrum_data.clear()
        self._waterfall_data.clear()
        self._waterfall_timestamps.clear()
        self._channel_selector.reset_peaks()
        self._log_message("History cleared")
    
    def _reset_peaks(self) -> None:
        self._channel_selector.reset_peaks()
        self._log_message("Peak tracking reset")
    
    def _run_diagnostic(self) -> None:
        result = check_hardware_availability()
        msg = f"Platform: {result['platform']}\n"
        msg += f"pyrf24 installed: {result['pyrf24_installed']}\n"
        if result['pyrf24_version']:
            msg += f"pyrf24 version: {result['pyrf24_version']}\n"
        msg += f"SPI devices: {result['spi_devices'] or 'None found'}\n"
        msg += f"GPIO access: {result['gpio_access']}\n"
        if result['errors']:
            msg += "\nErrors:\n" + "\n".join(f"  - {e}" for e in result['errors'])
        
        messagebox.showinfo("Hardware Diagnostic", msg)
    
    def _run_simulation_dialog(self) -> None:
        dialog = tk.Toplevel(self._root)
        dialog.title("Run Simulation Scenario")
        dialog.geometry("400x300")
        dialog.transient(self._root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Select scenario:").pack(pady=10)
        
        scenario_var = tk.StringVar(value="mixed")
        for scenario in ScenarioType:
            ttk.Radiobutton(dialog, text=f"{scenario.value}: {SimRadio.SCENARIOS[scenario]['description']}", 
                           variable=scenario_var, value=scenario.value).pack(anchor=tk.W, padx=20, pady=2)
        
        def run_scenario():
            scenario = ScenarioType(scenario_var.get())
            dialog.destroy()
            self._run_simulation_scenario(scenario)
        
        ttk.Button(dialog, text="Run", command=run_scenario).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=5)
    
    def _run_simulation_scenario(self, scenario: ScenarioType) -> None:
        if self._running:
            messagebox.showwarning("Busy", "Stop scanning first")
            return
        
        self._log_message(f"Running simulation scenario: {scenario.value}")
        
        radio = SimRadio(self._config.channel, self._config.scan, self._config.sim, scenario=scenario)
        radio.initialize()
        
        for channel in self._config.channel.channel_range():
            valid, positive, negative = radio.scan_channel(
                channel,
                self._config.scan.measurement_window,
                self._config.scan.sampling_interval,
            )
            
            if valid >= self._config.scan.min_valid_samples:
                activity = (positive / valid) * 100.0
                data_sufficient = True
            else:
                activity = None
                data_sufficient = False
            
            status = self._config.thresholds.classify(activity)
            if not data_sufficient:
                status = "INSUFFICIENT DATA"
            
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=channel,
                frequency_mhz=2400 + channel,
                backend="sim",
                valid_samples=valid,
                rpd_positive=positive,
                rpd_negative=negative,
                activity_percentage=activity,
                status=status,
                data_sufficient=data_sufficient,
                measurement_window=self._config.scan.measurement_window,
                sampling_interval=self._config.scan.sampling_interval,
                error=None,
            )
            self._spectrum_data.update_observation(obs)
        
        radio.cleanup()
        self._update_table()
        self._update_spectrum_graph()
        self._update_waterfall()
        self._update_recommendations_display()
        self._log_message(f"Simulation scenario {scenario.value} complete")
    
    def _show_about(self) -> None:
        messagebox.showinfo(
            "About RF Spectrum Visualizer v6",
            "RF Spectrum Visualizer v6\n"
            "2.4 GHz ISM Band Monitor for nRF24L01+\n\n"
            "Features:\n"
            "  • 126-channel scanning (0-125)\n"
            "  • Persistent JSON blocklist\n"
            "  • Channel avoidance algorithm\n"
            "  • Deterministic simulation modes\n"
            "  • Hardware support (Raspberry Pi 3B+)\n"
            "  • CSV/JSON export\n"
            "  • Real-time spectrum & waterfall\n\n"
            "Hardware: Raspberry Pi 3B+ + nRF24L01+\n"
            "Pins: CE=GPIO25, CSN=GPIO8 (SPI CE0)\n\n"
            "Note: nRF24L01+ is a narrowband transceiver.\n"
            "RPD observations are not calibrated power measurements."
        )
    
    def _on_close(self) -> None:
        self._stop_scanning()
        self._root.destroy()
    
    def run(self) -> None:
        self._root.mainloop()


def main() -> None:
    import sys
    config = AppConfig()
    if len(sys.argv) > 1 and sys.argv[1] == "--sim":
        config.default_backend = "sim"
    
    setup_logging(level=logging.INFO)
    app = SpectrumVisualizerApp(config)
    app.run()


if __name__ == "__main__":
    main()
