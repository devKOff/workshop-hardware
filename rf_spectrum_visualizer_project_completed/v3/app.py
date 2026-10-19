"""Tkinter GUI application for RF Spectrum Visualizer."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import time
import threading
import logging
from typing import Optional, List, Dict, Any
from collections import deque

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, MitigationConfig
from scanner import ScannerThread, SpectrumData, ChannelObservation
from sim_radio import SimRadio
from hardware_radio import HardwareRadio, check_hardware_availability
from mitigation import MitigationEngine, MitigationState, ChannelAlert
from exceptions import HardwareError, ScannerError
from logging_config import setup_logging, get_logger

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
        self._root.title("RF Spectrum Visualizer - 2.4 GHz ISM Band")
        self._root.geometry("1200x800")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._spectrum_data = SpectrumData(config)
        self._scanner: Optional[ScannerThread] = None
        self._radio = None
        self._mitigation_engine: Optional[MitigationEngine] = None
        self._table_model = ChannelTableModel(config)
        
        self._refresh_job: Optional[str] = None
        self._running = False
        self._waterfall_data: deque = deque(maxlen=config.gui.waterfall_history_size)
        self._waterfall_timestamps: deque = deque(maxlen=config.gui.waterfall_history_size)
        
        self._setup_logging()
        self._build_ui()
        self._update_ui_state()
    
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
        file_menu.add_command(label="Export CSV...", command=self._export_csv)
        file_menu.add_command(label="Export JSON...", command=self._export_json)
        file_menu.add_command(label="Export PNG (Spectrum)...", command=lambda: self._export_png("spectrum"))
        file_menu.add_command(label="Export PNG (Waterfall)...", command=lambda: self._export_png("waterfall"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Clear History", command=self._clear_history)
        menubar.add_cascade(label="View", menu=view_menu)
        
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
        
        self._start_btn = ttk.Button(toolbar, text="Start", command=self._start_scanning)
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
        
        self._armed_var = tk.BooleanVar(value=self._config.mitigation.armed)
        ttk.Checkbutton(toolbar, text="ARMED", variable=self._armed_var, command=self._on_armed_change).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export JSON", command=self._export_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export PNG", command=lambda: self._export_png("spectrum")).pack(side=tk.LEFT, padx=2)
    
    def _create_main_panes(self) -> None:
        main_paned = ttk.PanedWindow(self._root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        self._create_left_pane(left_frame)
        self._create_right_pane(right_frame)
    
    def _create_left_pane(self, parent: ttk.Frame) -> None:
        """Create left pane with table and spectrum graph."""
        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        table_frame = ttk.LabelFrame(paned, text="Channel Activity")
        paned.add(table_frame, weight=2)
        
        self._create_channel_table(table_frame)
        
        spectrum_frame = ttk.LabelFrame(paned, text="Live Spectrum")
        paned.add(spectrum_frame, weight=1)
        
        self._create_spectrum_graph(spectrum_frame)
    
    def _create_right_pane(self, parent: ttk.Frame) -> None:
        """Create right pane with waterfall and alerts."""
        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        waterfall_frame = ttk.LabelFrame(paned, text="Waterfall (Time vs Frequency)")
        paned.add(waterfall_frame, weight=2)
        
        self._create_waterfall_graph(waterfall_frame)
        
        alerts_frame = ttk.LabelFrame(paned, text="Alerts & Diagnostics")
        paned.add(alerts_frame, weight=1)
        
        self._create_alerts_panel(alerts_frame)
    
    def _create_channel_table(self, parent: ttk.Frame) -> None:
        """Create the channel activity table."""
        columns = ("channel", "frequency", "activity_bar", "activity_pct", "status", "samples", "rpd_pos", "sufficient")
        self._tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        
        self._tree.heading("channel", text="Ch", command=lambda: self._sort_table("channel"))
        self._tree.heading("frequency", text="Freq (MHz)", command=lambda: self._sort_table("frequency"))
        self._tree.heading("activity_bar", text="Activity")
        self._tree.heading("activity_pct", text="%", command=lambda: self._sort_table("activity_pct"))
        self._tree.heading("status", text="Status", command=lambda: self._sort_table("status"))
        self._tree.heading("samples", text="Samples")
        self._tree.heading("rpd_pos", text="RPD+")
        self._tree.heading("sufficient", text="Data OK")
        
        self._tree.column("channel", width=40, anchor=tk.CENTER)
        self._tree.column("frequency", width=70, anchor=tk.CENTER)
        self._tree.column("activity_bar", width=150)
        self._tree.column("activity_pct", width=50, anchor=tk.CENTER)
        self._tree.column("status", width=100, anchor=tk.CENTER)
        self._tree.column("samples", width=60, anchor=tk.CENTER)
        self._tree.column("rpd_pos", width=50, anchor=tk.CENTER)
        self._tree.column("sufficient", width=60, anchor=tk.CENTER)
        
        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._tree.yview)
        hsb = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        self._tree.tag_configure("clear", background="#e8f5e9")
        self._tree.tag_configure("moderate", background="#fff3e0")
        self._tree.tag_configure("busy", background="#ffebee")
        self._tree.tag_configure("heavy", background="#fce4ec")
        self._tree.tag_configure("insufficient", background="#f5f5f5")
        self._tree.tag_configure("error", background="#ffcdd2")
        self._tree.tag_configure("persistent", background="#f8bbd0")
    
    def _create_spectrum_graph(self, parent: ttk.Frame) -> None:
        """Create the live spectrum bar graph."""
        self._spec_fig = Figure(figsize=(6, 3), dpi=100)
        self._spec_ax = self._spec_fig.add_subplot(111)
        self._spec_canvas = FigureCanvasTkAgg(self._spec_fig, parent)
        self._spec_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self._spec_ax.set_xlabel("Channel (nRF24)")
        self._spec_ax.set_ylabel("Activity (%)")
        self._spec_ax.set_ylim(0, 100)
        self._spec_ax.grid(True, alpha=0.3)
        
        self._spec_bars = None
        self._spec_threshold_lines = []
    
    def _create_waterfall_graph(self, parent: ttk.Frame) -> None:
        """Create the waterfall visualization."""
        self._wf_fig = Figure(figsize=(6, 3), dpi=100)
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
        
        self._log_message("RF Spectrum Visualizer ready. Select backend and press Start.")
    
    def _create_status_bar(self) -> None:
        self._status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self._root, textvariable=self._status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
    
    def _update_ui_state(self) -> None:
        """Update UI element states based on running state."""
        if self._running:
            self._start_btn.config(state=tk.DISABLED)
            self._stop_btn.config(state=tk.NORMAL)
            self._status_var.set(f"Scanning... ({self._spectrum_data.get_backend()})")
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
    
    def _on_armed_change(self) -> None:
        if self._mitigation_engine:
            if self._armed_var.get():
                self._mitigation_engine.arm()
                self._log_message("Mitigation system ARMED")
            else:
                self._mitigation_engine.disarm()
                self._log_message("Mitigation system DISARMED")
    
    def _start_scanning(self) -> None:
        if self._running:
            return
        
        try:
            self._config.channel.start_channel = self._start_ch_var.get()
            self._config.channel.end_channel = self._end_ch_var.get()
            self._config.scan.measurement_window = self._window_var.get()
            self._config.scan.sampling_interval = self._interval_var.get() / 1000.0
            self._config.mitigation.armed = self._armed_var.get()
            
            if self._config.default_backend == "hardware":
                self._radio = HardwareRadio(self._config.channel, self._config.scan)
                if not self._radio.is_available():
                    messagebox.showerror("Hardware Unavailable", "pyrf24 not installed or SPI unavailable")
                    return
            else:
                self._radio = SimRadio(self._config.channel, self._config.scan)
            
            self._scanner = ScannerThread(
                self._config,
                self._spectrum_data,
                self._radio,
                on_observation=self._on_observation,
                on_error=self._on_scanner_error,
                on_scan_complete=self._on_scan_complete,
            )
            
            self._mitigation_engine = MitigationEngine(
                self._config.mitigation,
                self._config.thresholds,
                self._config.channel,
                on_alert=self._on_alert,
                on_recommendation=self._on_recommendation,
            )
            if self._config.mitigation.armed:
                self._mitigation_engine.arm()
            
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
        
        self._schedule_refresh()
    
    def _on_observation(self, obs: ChannelObservation) -> None:
        pass
    
    def _on_scanner_error(self, error: Exception) -> None:
        self._log_message(f"Scanner error: {error}", "ERROR")
    
    def _on_scan_complete(self) -> None:
        pass
    
    def _on_alert(self, alert: ChannelAlert) -> None:
        self._log_message(
            f"ALERT: Ch {alert.channel} ({alert.frequency_mhz} MHz) - "
            f"{alert.activity_percentage:.1f}% persistent activity. "
            f"Recommended: {alert.recommended_channels}",
            "WARNING"
        )
    
    def _on_recommendation(self, channels: List[int]) -> None:
        self._log_message(f"Safe channel recommendations: {channels}", "INFO")
    
    def _update_table(self) -> None:
        observations = self._spectrum_data.get_all_observations()
        self._table_model.update(observations)
        
        channels = self._spectrum_data.get_channels_in_range()
        existing = set(self._tree.get_children())
        needed = set(str(ch) for ch in channels)
        
        for ch in channels:
            obs = observations.get(ch)
            iid = str(ch)
            if obs:
                activity_str = f"{obs.activity_percentage:.1f}%" if obs.activity_percentage is not None else "N/A"
                bar = self._make_activity_bar(obs.activity_percentage)
                tag = self._get_status_tag(obs)
                values = (
                    ch, obs.frequency_mhz, bar, activity_str,
                    obs.status, obs.valid_samples, obs.rpd_positive,
                    "Yes" if obs.data_sufficient else "No"
                )
            else:
                values = (ch, 2400+ch, "", "N/A", "Pending", 0, 0, "No")
                tag = "insufficient"
            
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
    
    def _get_status_tag(self, obs: ChannelObservation) -> str:
        if obs.error:
            return "error"
        if not obs.data_sufficient:
            return "insufficient"
        if self._mitigation_engine and self._mitigation_engine.get_channel_status(obs.channel, obs) == MitigationState.ARMED:
            return "persistent"
        status = obs.status.lower()
        if status in ("clear", "moderate", "busy", "heavy load"):
            return status.replace(" ", "")
        return ""
    
    def _sort_table(self, column: str) -> None:
        pass
    
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
            if obs and obs.activity_percentage is not None:
                activities.append(obs.activity_percentage)
            else:
                activities.append(0)
            
            if obs and obs.status == "Heavy Load":
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
        self._waterfall_data.append([observations.get(ch, ChannelObservation(0, ch, 2400+ch, "", 0,0,0,None,"",False,0,0)).activity_percentage or 0 for ch in channels])
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
                from scanner import ChannelObservation
                observations = self._spectrum_data.export_all()
                import csv
                with open(path, "w", newline="") as f:
                    if observations:
                        fieldnames = observations[0].keys()
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(observations)
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
                import json
                data = self._spectrum_data.export_all()
                with open(path, "w") as f:
                    json.dump({
                        "backend": self._spectrum_data.get_backend(),
                        "scan_count": self._spectrum_data.get_scan_count(),
                        "observations": data,
                    }, f, indent=2)
                messagebox.showinfo("Export", f"JSON exported to {path}")
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
        if self._mitigation_engine:
            self._mitigation_engine.clear_history()
        self._log_message("History cleared")
    
    def _show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "RF Spectrum Visualizer\n"
            "2.4 GHz ISM Band Monitor\n\n"
            "Hardware: Raspberry Pi 3B+ + nRF24L01+\n"
            "Simulation: Deterministic RF activity model\n\n"
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