"""Live Spectrum tool — Phase 2.

Connects a Tkinter + matplotlib GUI to the actual V3 nRF24L01+ scanner
implementation (scanner.ScannerThread, SpectrumData, ChannelObservation,
SimRadio, HardwareRadio). The V3 source project is imported read-only via
sys.path (it is never modified).

Features:
- Scan all 126 channels (0-125); frequency = 2400 + channel_number MHz.
- Live spectrum bar chart, channel activity table, activity percentage
  (0-100%), status labels Clear / Moderate / Busy / Heavy Load
  (plus INSUFFICIENT DATA and SENSOR_ERROR).
- Working Start Scan / Stop Scan controls.
- Hardware and Simulation modes; real measurements vs simulated data are
  clearly distinguished (a source label and the observation.backend field).
- Scanner status, scan progress (last channel scanned), busiest channel,
  average activity.
- Responsive GUI: background scanning thread, thread-safe SpectrumData,
  UI refresh driven by tk.after (main thread only).
- No duplicate scanner threads; clean shutdown on stop / window close.
- Hardware errors are caught and reported without crashing and without
  displaying fake readings.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------------------------------------------------------------------------
# Make the V3 source project importable (read-only, never modified).
# The V3 scanner modules live at workshop/v3 and are top-level modules
# (config, scanner, sim_radio, hardware_radio, exceptions).
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
# .../rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/ui
_PROJECT_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", ".."))
# .../rf_spectrum_visualizer_v3
_V3_ROOT = os.path.normpath(os.path.join(_PROJECT_ROOT, "..", "v3"))
# .../workshop/v3
for _p in (_PROJECT_ROOT, os.path.join(_PROJECT_ROOT, "src"), _V3_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig  # noqa: E402
from scanner import ScannerThread, SpectrumData, ChannelObservation  # noqa: E402
from exceptions import (  # noqa: E402
    ScannerError,
    ScannerAlreadyRunningError,
    ScannerNotRunningError,
)

logger = logging.getLogger("rf_visualizer.ui.live_spectrum")

CHANNEL_MIN = 0
CHANNEL_MAX = 125
BASE_FREQUENCY_MHZ = 2400

# Refresh period for the UI polling loop (ms).
REFRESH_MS = 500


def _channel_to_frequency(channel: int) -> int:
    """Frequency in MHz for a channel: 2400 + channel_number."""
    return BASE_FREQUENCY_MHZ + channel


class LiveSpectrumApp:
    """Live Spectrum GUI backed by the V3 scanner implementation."""

    def __init__(self, config: AppConfig, backend: str = "sim") -> None:
        self._config = config
        self._backend = backend  # "sim" or "hardware"
        self._config.default_backend = backend

        self._spectrum_data = SpectrumData(config)
        self._scanner: Optional[ScannerThread] = None
        self._running = False
        self._refresh_job: Optional[str] = None

        # Scan progress / status indicators (updated by callbacks + poll loop).
        self._last_channel: Optional[int] = None
        self._last_channel_ts: float = 0.0
        self._scan_start_ts: float = 0.0

        self._root = tk.Tk()
        self._root.title("RF Spectrum Visualizer — Live Spectrum (2.4 GHz ISM)")
        self._root.geometry("1250x820")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._update_ui_state()
        self._log("Live Spectrum ready. Select a mode and press Start Scan.")

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self._create_toolbar()
        self._create_main_panes()
        self._create_status_bar()

    def _create_toolbar(self) -> None:
        tb = ttk.Frame(self._root)
        tb.pack(fill=tk.X, padx=6, pady=5)

        # Mode selector.
        ttk.Label(tb, text="Mode:").pack(side=tk.LEFT, padx=(0, 2))
        self._mode_var = tk.StringVar(value=self._backend)
        mode_combo = ttk.Combobox(
            tb, textvariable=self._mode_var,
            values=["sim", "hardware"], width=10, state="readonly",
        )
        mode_combo.pack(side=tk.LEFT, padx=(0, 8))
        mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # Start / Stop controls.
        self._start_btn = ttk.Button(tb, text="Start Scan", command=self._start_scan)
        self._start_btn.pack(side=tk.LEFT, padx=2)
        self._stop_btn = ttk.Button(tb, text="Stop Scan", command=self._stop_scan, state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # Channel range.
        ttk.Label(tb, text="Channels:").pack(side=tk.LEFT, padx=(0, 2))
        self._start_ch_var = tk.IntVar(value=self._config.channel.start_channel)
        self._end_ch_var = tk.IntVar(value=self._config.channel.end_channel)
        ttk.Spinbox(tb, from_=CHANNEL_MIN, to=CHANNEL_MAX, textvariable=self._start_ch_var, width=5).pack(side=tk.LEFT)
        ttk.Label(tb, text="–").pack(side=tk.LEFT, padx=2)
        ttk.Spinbox(tb, from_=CHANNEL_MIN, to=CHANNEL_MAX, textvariable=self._end_ch_var, width=5).pack(side=tk.LEFT)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        # Timing.
        ttk.Label(tb, text="Window (s):").pack(side=tk.LEFT, padx=(0, 2))
        self._window_var = tk.DoubleVar(value=self._config.scan.measurement_window)
        ttk.Spinbox(tb, from_=0.05, to=10.0, increment=0.05, textvariable=self._window_var, width=6).pack(side=tk.LEFT)
        ttk.Label(tb, text="Interval (ms):").pack(side=tk.LEFT, padx=(8, 2))
        self._interval_var = tk.DoubleVar(value=self._config.scan.sampling_interval * 1000.0)
        ttk.Spinbox(tb, from_=1, to=1000, increment=1, textvariable=self._interval_var, width=6).pack(side=tk.LEFT)

    def _create_main_panes(self) -> None:
        paned = ttk.PanedWindow(self._root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=5)

        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        self._create_left_pane(left)
        self._create_right_pane(right)

    def _create_left_pane(self, parent: ttk.Frame) -> None:
        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Source indicator banner.
        self._source_frame = ttk.LabelFrame(paned, text="Data Source")
        paned.add(self._source_frame, weight=0)
        self._source_label = ttk.Label(
            self._source_frame,
            text="Source: not started",
            foreground="#555555",
            font=("TkDefaultFont", 9, "italic"),
        )
        self._source_label.pack(anchor=tk.W, padx=6, pady=4)

        # Channel activity table.
        table_frame = ttk.LabelFrame(paned, text="Channel Activity (0–125)")
        paned.add(table_frame, weight=2)
        self._create_channel_table(table_frame)

    def _create_channel_table(self, parent: ttk.Frame) -> None:
        columns = ("channel", "frequency", "activity_pct", "status", "samples", "rpd_pos", "sufficient")
        self._tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")

        self._tree.heading("channel", text="Ch", command=lambda: self._sort_table("channel"))
        self._tree.heading("frequency", text="Freq (MHz)", command=lambda: self._sort_table("frequency"))
        self._tree.heading("activity_pct", text="Activity %", command=lambda: self._sort_table("activity_pct"))
        self._tree.heading("status", text="Status", command=lambda: self._sort_table("status"))
        self._tree.heading("samples", text="Samples")
        self._tree.heading("rpd_pos", text="RPD+")
        self._tree.heading("sufficient", text="Data OK")

        self._tree.column("channel", width=45, anchor=tk.CENTER)
        self._tree.column("frequency", width=85, anchor=tk.CENTER)
        self._tree.column("activity_pct", width=90, anchor=tk.CENTER)
        self._tree.column("status", width=115, anchor=tk.CENTER)
        self._tree.column("samples", width=65, anchor=tk.CENTER)
        self._tree.column("rpd_pos", width=55, anchor=tk.CENTER)
        self._tree.column("sufficient", width=60, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._tree.yview)
        hsb = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Status row colours.
        self._tree.tag_configure("clear", background="#e8f5e9")
        self._tree.tag_configure("moderate", background="#fff3e0")
        self._tree.tag_configure("busy", background="#ffebee")
        self._tree.tag_configure("heavy load", background="#fce4ec")
        self._tree.tag_configure("insufficient data", background="#f5f5f5")
        self._tree.tag_configure("sensor_error", background="#ffcdd2")
        self._tree.tag_configure("pending", background="#eceff1")

    def _create_right_pane(self, parent: ttk.Frame) -> None:
        paned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        spec_frame = ttk.LabelFrame(paned, text="Live Spectrum — Activity % by Channel")
        paned.add(spec_frame, weight=2)
        self._create_spectrum_graph(spec_frame)

        diag_frame = ttk.LabelFrame(paned, text="Diagnostics / Log")
        paned.add(diag_frame, weight=1)
        self._create_diagnostics(diag_frame)

    def _create_spectrum_graph(self, parent: ttk.Frame) -> None:
        self._spec_fig = Figure(figsize=(6, 3.4), dpi=100)
        self._spec_ax = self._spec_fig.add_subplot(111)
        self._spec_canvas = FigureCanvasTkAgg(self._spec_fig, parent)
        self._spec_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self._spec_ax.set_xlabel("Channel (nRF24L01+)")
        self._spec_ax.set_ylabel("Activity (%)")
        self._spec_ax.set_ylim(0, 100)
        self._spec_ax.set_xlim(CHANNEL_MIN - 0.5, CHANNEL_MAX + 0.5)
        self._spec_ax.grid(True, alpha=0.3)
        self._spec_ax.set_title("Live Spectrum — not scanning")

        self._spec_bars = None

    def _create_diagnostics(self, parent: ttk.Frame) -> None:
        self._diag_text = tk.Text(parent, height=9, wrap=tk.WORD, state=tk.DISABLED)
        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._diag_text.yview)
        self._diag_text.configure(yscrollcommand=vsb.set)
        self._diag_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

    def _create_status_bar(self) -> None:
        self._status_var = tk.StringVar(value="Stopped")
        bar = ttk.Label(self._root, textvariable=self._status_var, relief=tk.SUNKEN, anchor=tk.W)
        bar.pack(fill=tk.X, side=tk.BOTTOM, padx=6, pady=4)

    # ------------------------------------------------------------ actions
    def _on_mode_change(self, event=None) -> None:
        if self._running:
            messagebox.showwarning("Cannot change mode", "Stop scanning before changing mode.")
            self._mode_var.set(self._backend)
            return
        self._backend = self._mode_var.get()
        self._config.default_backend = self._backend
        self._log(f"Mode set to {self._backend}.")
        self._update_source_label()

    def _update_source_label(self) -> None:
        if self._backend == "hardware":
            text = "Source: Hardware (nRF24L01+ RPD) — real measurements"
            colour = "#1b5e20"
        else:
            text = ("Source: Simulation (deterministic channel model) — "
                    "simulated data, not calibrated hardware readings")
            colour = "#1565c0"
        self._source_label.config(text=text, foreground=colour)

    def _start_scan(self) -> None:
        if self._running:
            return
        try:
            self._config.channel.start_channel = int(self._start_ch_var.get())
            self._config.channel.end_channel = int(self._end_ch_var.get())
            self._config.scan.measurement_window = float(self._window_var.get())
            self._config.scan.sampling_interval = float(self._interval_var.get()) / 1000.0
            self._config.default_backend = self._backend

            # Validate channel range.
            if not (CHANNEL_MIN <= self._config.channel.start_channel <= CHANNEL_MAX):
                raise ValueError("Start channel out of range 0-125")
            if not (CHANNEL_MIN <= self._config.channel.end_channel <= CHANNEL_MAX):
                raise ValueError("End channel out of range 0-125")
            if self._config.channel.start_channel > self._config.channel.end_channel:
                raise ValueError("Start channel must be <= end channel")

            self._spectrum_data.clear()
            self._spectrum_data.set_backend(self._backend)
            self._last_channel = None
            self._scan_start_ts = time.time()

            self._scanner = ScannerThread(
                self._config,
                self._spectrum_data,
                radio=None,  # let ScannerThread create the radio for the backend
                on_observation=self._on_observation,
                on_error=self._on_scanner_error,
                on_scan_complete=self._on_scan_complete,
            )
            self._scanner.start()
            self._running = True
            self._scan_start_ts = time.time()
            self._update_ui_state()
            self._update_source_label()
            self._schedule_refresh()
            self._log(f"Started scanning ({self._config.default_backend} backend), "
                      f"channels {self._config.channel.start_channel}-{self._config.channel.end_channel}")

        except ScannerAlreadyRunningError:
            self._log("Scanner is already running.", "WARN")
        except ScannerError as e:
            logger.error("Scanner error: %s", e)
            messagebox.showerror("Scanner error", f"Failed to start scanner: {e}")
            self._log(f"Scanner error: {e}", "ERROR")
        except Exception as e:  # noqa: BLE001 - report hardware/config errors to user
            logger.error("Failed to start scanning: %s", e)
            messagebox.showerror("Error", f"Failed to start scanning: {e}")
            self._log(f"Failed to start scanning: {e}", "ERROR")

    def _stop_scan(self) -> None:
        if not self._running:
            return
        try:
            if self._scanner is not None:
                self._scanner.shutdown()
                self._scanner = None
        except Exception as e:  # noqa: BLE001
            logger.warning("Error stopping scanner: %s", e)
            self._log(f"Warning stopping scanner: {e}", "WARN")
        finally:
            self._running = False
            self._scanner = None
            self._update_ui_state()
            if self._refresh_job is not None:
                try:
                    self._root.after_cancel(self._refresh_job)
                except tk.TclError:
                    pass
                self._refresh_job = None
            self._status_var.set("Stopped")
            self._log("Scanning stopped.")

    # ------------------------------------------------------------ callbacks
    def _on_observation(self, obs: ChannelObservation) -> None:
        """Called from the scanner thread. Only record lightweight state."""
        self._last_channel = obs.channel
        self._last_channel_ts = time.time()

    def _on_scanner_error(self, error: Exception) -> None:
        """Called from the scanner thread on per-channel errors."""
        logger.error("Scanner error: %s", error)
        self._log(f"Scanner error: {error}", "ERROR")

    def _on_scan_complete(self) -> None:
        """Called from the scanner thread when a full cycle completes."""
        logger.debug("Scan cycle complete")

    # ------------------------------------------------------------ refresh
    def _schedule_refresh(self) -> None:
        if not self._running:
            return
        self._refresh_job = self._root.after(REFRESH_MS, self._refresh_ui)

    def _refresh_ui(self) -> None:
        """Poll shared (thread-safe) spectrum data and redraw. Main thread only."""
        if not self._running:
            return

        try:
            self._update_table()
            self._update_spectrum_graph()
            self._update_status_bar()
        except Exception as e:  # noqa: BLE001 - keep UI alive
            logger.error("UI refresh error: %s", e)
            self._log(f"UI refresh error: {e}", "ERROR")

        self._schedule_refresh()

    def _update_table(self) -> None:
        observations = self._spectrum_data.get_all_observations()
        channels = list(range(self._config.channel.start_channel, self._config.channel.end_channel + 1))

        existing = set(self._tree.get_children())
        needed = {str(ch) for ch in channels}

        for ch in channels:
            obs = observations.get(ch)
            iid = str(ch)
            if obs is not None:
                activity_str = (f"{obs.activity_percentage:.1f}%"
                                if obs.activity_percentage is not None else "N/A")
                status = obs.status
                tag = status.lower().replace(" ", " ") if status else "pending"
                tag = tag if tag in ("clear", "moderate", "busy", "heavy load",
                                     "insufficient data", "sensor_error") else "pending"
                values = (
                    ch,
                    obs.frequency_mhz,
                    activity_str,
                    status,
                    obs.valid_samples,
                    obs.rpd_positive,
                    "Yes" if obs.data_sufficient else "No",
                )
            else:
                values = (ch, _channel_to_frequency(ch), "N/A", "Pending", 0, 0, "No")
                tag = "pending"

            if iid in existing:
                self._tree.item(iid, values=values, tags=(tag,))
            else:
                self._tree.insert("", tk.END, iid=iid, values=values, tags=(tag,))

        for iid in existing - needed:
            self._tree.delete(iid)

    def _update_spectrum_graph(self) -> None:
        observations = self._spectrum_data.get_all_observations()
        channels = list(range(self._config.channel.start_channel, self._config.channel.end_channel + 1))

        activities = []
        colors = []
        for ch in channels:
            obs = observations.get(ch)
            if obs is not None and obs.activity_percentage is not None:
                activities.append(obs.activity_percentage)
            else:
                activities.append(0.0)

            if obs is None:
                colors.append("#9e9e9e")
            elif obs.status == "Heavy Load":
                colors.append("#ef5350")
            elif obs.status == "Busy":
                colors.append("#ffa726")
            elif obs.status == "Moderate":
                colors.append("#ffca28")
            elif obs.status == "Clear":
                colors.append("#66bb6a")
            elif obs.status in ("INSUFFICIENT DATA", "SENSOR_ERROR"):
                colors.append("#9e9e9e")
            else:
                colors.append("#9e9e9e")

        self._spec_ax.clear()
        self._spec_ax.set_xlabel("Channel (nRF24L01+)")
        self._spec_ax.set_ylabel("Activity (%)")
        self._spec_ax.set_ylim(0, 100)
        self._spec_ax.set_xlim(CHANNEL_MIN - 0.5, CHANNEL_MAX + 0.5)
        self._spec_ax.grid(True, alpha=0.3)
        backend_label = ("Hardware (nRF24L01+)" if self._backend == "hardware"
                         else "Simulation (deterministic model)")
        self._spec_ax.set_title(f"Live Spectrum — {backend_label}")

        if any(a > 0 for a in activities):
            self._spec_ax.bar(channels, activities, color=colors, width=0.8,
                              edgecolor="white", linewidth=0.5)

        # Threshold reference lines.
        thr = self._config.thresholds
        for val, label, colour in [
            (thr.clear_max, "Clear ≤ 24%", "green"),
            (thr.moderate_max, "Moderate ≤ 49%", "orange"),
            (thr.busy_max, "Busy ≤ 74%", "red"),
        ]:
            self._spec_ax.axhline(y=val, color=colour, linestyle=":", alpha=0.5, linewidth=1)

        self._spec_fig.tight_layout()
        self._spec_canvas.draw_idle()

    def _update_status_bar(self) -> None:
        scan_count = self._spectrum_data.get_scan_count()
        observations = self._spectrum_data.get_all_observations()

        # Busiest channel and average activity across sufficient observations.
        busiest_ch = None
        busiest_pct = -1.0
        total = 0.0
        count = 0
        for ch, obs in observations.items():
            if obs.data_sufficient and obs.activity_percentage is not None:
                total += obs.activity_percentage
                count += 1
                if obs.activity_percentage > busiest_pct:
                    busiest_pct = obs.activity_percentage
                    busiest_ch = obs.channel

        avg = (total / count) if count else 0.0
        backend_label = ("Hardware (nRF24L01+)" if self._backend == "hardware"
                         else "Simulation (deterministic model)")

        if self._running:
            prog = f" — last scanned: Ch {self._last_channel}" if self._last_channel is not None else ""
            status_txt = (f"Scanning ({backend_label}) | cycles: {scan_count} | "
                          f"busiest: Ch {busiest_ch} ({busiest_pct:.1f}%) | "
                          f"avg activity: {avg:.1f}%{prog}")
        else:
            status_txt = f"Stopped ({backend_label}) | cycles: {scan_count}"

        self._status_var.set(status_txt)

    # ------------------------------------------------------------ helpers
    def _sort_table(self, column: str) -> None:
        # Table sorting hook (kept minimal; Treeview re-inserted each refresh).
        pass

    def _log(self, message: str, level: str = "INFO") -> None:
        timestamp = time.strftime("%H:%M:%S")
        self._diag_text.config(state=tk.NORMAL)
        self._diag_text.insert(tk.END, f"[{timestamp}] {level}: {message}\n")
        self._diag_text.see(tk.END)
        self._diag_text.config(state=tk.DISABLED)

    def _update_ui_state(self) -> None:
        if self._running:
            self._start_btn.config(state=tk.DISABLED)
            self._stop_btn.config(state=tk.NORMAL)
            self._status_var.set("Scanning...")
        else:
            self._start_btn.config(state=tk.NORMAL)
            self._stop_btn.config(state=tk.DISABLED)
            if not self._status_var.get().startswith("Stopped"):
                self._status_var.set("Stopped")

    def _on_close(self) -> None:
        self._stop_scan()
        self._root.destroy()

    def run(self) -> None:
        self._root.mainloop()


def main() -> None:
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    config = AppConfig()
    app = LiveSpectrumApp(config, backend="sim")
    app.run()


if __name__ == "__main__":
    main()
