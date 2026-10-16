"""Live Spectrum page: real V3 scanner integration (Tkinter).

Displays a live spectrum chart, channel activity table, activity percentage
(0-100%), status labels (Clear/Moderate/Busy/Heavy Load), working Start/Stop
Scan controls, Hardware/Simulation mode selection, scanner status, scan
progress, busiest channel, and average activity.

All GUI updates happen on the main thread via Tk after() polling, reading
from the thread-safe V3 SpectrumData. No fake measurements are displayed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import logging

from .canvas import MplCanvas
from ..constants import (
    PAGE_LIVE_SPECTRUM,
    RF_CHANNEL_MIN,
    RF_CHANNEL_MAX,
    RF_BASE_FREQUENCY_MHZ,
    COLOR_WORKSPACE_BG,
    COLOR_TEXT_DARK,
    COLOR_CRIMON_ACCENT,
    COLOR_CRIMON_LIGHT,
)
from ..v3_bridge import ChannelObservation

CHANNEL_MIN = RF_CHANNEL_MIN
CHANNEL_MAX = RF_CHANNEL_MAX
BASE_FREQUENCY = RF_BASE_FREQUENCY_MHZ

STATUS_TAG_COLOURS = {
    "Clear": "#e8f5e9",
    "Moderate": "#fff3e0",
    "Busy": "#ffebee",
    "Heavy Load": "#fce4ec",
    "INSUFFICIENT DATA": "#f5f5f5",
    "SENSOR_ERROR": "#ffcdd2",
    "Pending": "#eceff1",
}


class LiveSpectrumPage(tk.Frame):
    """Live Spectrum page backed by the V3 scanner implementation."""

    def __init__(self, parent, main_window, spectrum_data):
        super().__init__(parent, bg=COLOR_WORKSPACE_BG)
        self.main_window = main_window
        self.spectrum_data = spectrum_data
        self._config = main_window.config

        self.backend_var = tk.StringVar(value=self.main_window.get_backend())
        self.start_ch_var = tk.IntVar(value=self._config.channel.start_channel)
        self.end_ch_var = tk.IntVar(value=self._config.channel.end_channel)
        self.window_var = tk.DoubleVar(value=self._config.scan.measurement_window)
        self.interval_var = tk.DoubleVar(value=self._config.scan.sampling_interval * 1000.0)

        self._last_channel = None

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # Toolbar.
        tb = tk.Frame(self, bg=COLOR_WORKSPACE_BG)
        tb.pack(fill=tk.X, padx=6, pady=5)

        tk.Label(tb, text="Mode:", bg=COLOR_WORKSPACE_BG).pack(side=tk.LEFT, padx=(0, 2))
        self.mode_combo = ttk.Combobox(
            tb, textvariable=self.backend_var,
            values=["sim", "hardware"], width=10, state="readonly",
            takefocus=1,
        )
        self.mode_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.mode_combo.focus_set()
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        self.btn_start = tk.Button(
            tb, text="Start Scan", command=self._on_start_scan,
            bg=COLOR_CRIMON_ACCENT, fg="white", activebackground="#b71c1c",
            relief=tk.FLAT, padx=12, pady=4,
        )
        self.btn_start.pack(side=tk.LEFT, padx=2)

        self.btn_stop = tk.Button(
            tb, text="Stop Scan", command=self._on_stop_scan, state=tk.DISABLED,
            bg="#9e9e9e", fg="white", activebackground="#616161",
            relief=tk.FLAT, padx=12, pady=4,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        tk.Label(tb, text="Channels:", bg=COLOR_WORKSPACE_BG).pack(side=tk.LEFT, padx=(0, 2))
        self.spin_start = tk.Spinbox(
            tb, from_=CHANNEL_MIN, to=CHANNEL_MAX, textvariable=self.start_ch_var,
            width=5,
        )
        self.spin_start.pack(side=tk.LEFT)
        tk.Label(tb, text="–", bg=COLOR_WORKSPACE_BG).pack(side=tk.LEFT, padx=2)
        self.spin_end = tk.Spinbox(
            tb, from_=CHANNEL_MIN, to=CHANNEL_MAX, textvariable=self.end_ch_var,
            width=5,
        )
        self.spin_end.pack(side=tk.LEFT)

        ttk.Separator(tb, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        tk.Label(tb, text="Window (s):", bg=COLOR_WORKSPACE_BG).pack(side=tk.LEFT, padx=(0, 2))
        self.spin_window = tk.Spinbox(
            tb, from_=0.05, to=10.0, increment=0.05,
            textvariable=self.window_var, width=6,
        )
        self.spin_window.pack(side=tk.LEFT)
        tk.Label(tb, text="Interval (ms):", bg=COLOR_WORKSPACE_BG).pack(side=tk.LEFT, padx=(8, 2))
        self.spin_interval = tk.Spinbox(
            tb, from_=1, to=1000, increment=1,
            textvariable=self.interval_var, width=6,
        )
        self.spin_interval.pack(side=tk.LEFT)

        # Main paned window.
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=5)

        left = tk.Frame(paned, bg=COLOR_WORKSPACE_BG)
        paned.add(left, weight=1)
        right = tk.Frame(paned, bg=COLOR_WORKSPACE_BG)
        paned.add(right, weight=1)

        self._create_left_pane(left)
        self._create_right_pane(right)

    def _create_left_pane(self, parent: tk.Frame) -> None:
        # Source indicator banner.
        src_frame = tk.LabelFrame(
            parent, text="Data Source", bg=COLOR_WORKSPACE_BG, fg=COLOR_TEXT_DARK,
        )
        src_frame.pack(fill=tk.X, pady=(0, 6))
        self.source_label = tk.Label(
            src_frame,
            text="Source: not started",
            fg="#555555", bg=COLOR_WORKSPACE_BG,
            font=("Segoe UI", 9, "italic"),
        )
        self.source_label.pack(anchor=tk.W, padx=6, pady=4)

        # Channel activity table.
        table_frame = tk.LabelFrame(
            parent, text="Channel Activity (0–125)",
            bg=COLOR_WORKSPACE_BG, fg=COLOR_TEXT_DARK,
        )
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("channel", "frequency", "activity_pct", "status", "samples", "rpd_pos", "sufficient")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse",
        )
        self.tree.heading("channel", text="Ch")
        self.tree.heading("frequency", text="Freq (MHz)")
        self.tree.heading("activity_pct", text="Activity %")
        self.tree.heading("status", text="Status")
        self.tree.heading("samples", text="Samples")
        self.tree.heading("rpd_pos", text="RPD+")
        self.tree.heading("sufficient", text="Data OK")

        self.tree.column("channel", width=45, anchor=tk.CENTER)
        self.tree.column("frequency", width=85, anchor=tk.CENTER)
        self.tree.column("activity_pct", width=90, anchor=tk.CENTER)
        self.tree.column("status", width=115, anchor=tk.CENTER)
        self.tree.column("samples", width=65, anchor=tk.CENTER)
        self.tree.column("rpd_pos", width=55, anchor=tk.CENTER)
        self.tree.column("sufficient", width=60, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Pre-create rows for all channels in range.
        self._iid_by_channel: dict[int, str] = {}
        for ch in range(CHANNEL_MIN, CHANNEL_MAX + 1):
            freq = BASE_FREQUENCY + ch
            iid = str(ch)
            self._iid_by_channel[ch] = iid
            self.tree.insert(
                "", tk.END, iid=iid,
                values=(ch, freq, "N/A", "Pending", 0, 0, "No"),
                tags=("Pending",),
            )

        for tag, colour in STATUS_TAG_COLOURS.items():
            self.tree.tag_configure(tag, background=colour)

    def _create_right_pane(self, parent: tk.Frame) -> None:
        # Spectrum graph.
        spec_frame = tk.LabelFrame(
            parent, text="Live Spectrum — Activity % by Channel",
            bg=COLOR_WORKSPACE_BG, fg=COLOR_TEXT_DARK,
        )
        spec_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = MplCanvas(spec_frame, width=6, height=3.4, dpi=100)
        self._draw_empty_chart()

        # Diagnostics / log.
        diag_frame = tk.LabelFrame(
            parent, text="Diagnostics / Log",
            bg=COLOR_WORKSPACE_BG, fg=COLOR_TEXT_DARK,
        )
        diag_frame.pack(fill=tk.BOTH, expand=True)
        self.diag_text = tk.Text(
            diag_frame, height=9, wrap=tk.WORD, state=tk.DISABLED,
            bg="#ffffff", fg=COLOR_TEXT_DARK,
        )
        vsb = ttk.Scrollbar(diag_frame, orient=tk.VERTICAL, command=self.diag_text.yview)
        self.diag_text.configure(yscrollcommand=vsb.set)
        self.diag_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        diag_frame.grid_rowconfigure(0, weight=1)
        diag_frame.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------ public API
    def update_source_label(self) -> None:
        if self.main_window.get_backend() == "hardware":
            text = "Source: Hardware (nRF24L01+ RPD) — real measurements"
            colour = "#1b5e20"
        else:
            text = ("Source: Simulation (deterministic channel model) — "
                    "simulated data, not calibrated hardware readings")
            colour = "#1565c0"
        self.source_label.config(text=text, fg=colour)

    def set_last_channel(self, channel: int) -> None:
        """Called from main thread to track last scanned channel."""
        self._last_channel = channel

    def refresh_from_data(self) -> None:
        """Refresh table and graph from thread-safe SpectrumData (main thread)."""
        observations = self.spectrum_data.get_all_observations()
        start_ch = self._config.channel.start_channel
        end_ch = self._config.channel.end_channel

        for ch in range(start_ch, end_ch + 1):
            obs = observations.get(ch)
            iid = self._iid_by_channel[ch]
            if obs is not None:
                activity_str = (
                    f"{obs.activity_percentage:.1f}%"
                    if obs.activity_percentage is not None else "N/A"
                )
                status = obs.status
                tag = status if status in STATUS_TAG_COLOURS else "Pending"
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
                values = (ch, BASE_FREQUENCY + ch, "N/A", "Pending", 0, 0, "No")
                tag = "Pending"

            self.tree.item(iid, values=values, tags=(tag,))

        self._update_spectrum_graph(observations, start_ch, end_ch)
        self._update_status_bar(observations)

    def _update_spectrum_graph(self, observations, start_ch, end_ch) -> None:
        channels = list(range(start_ch, end_ch + 1))
        activities = []
        colours = []
        for ch in channels:
            obs = observations.get(ch)
            if obs is not None and obs.activity_percentage is not None:
                activities.append(obs.activity_percentage)
            else:
                activities.append(0.0)

            if obs is None:
                colours.append("#9e9e9e")
            elif obs.status == "Heavy Load":
                colours.append("#ef5350")
            elif obs.status == "Busy":
                colours.append("#ffa726")
            elif obs.status == "Moderate":
                colours.append("#ffca28")
            elif obs.status == "Clear":
                colours.append("#66bb6a")
            else:
                colours.append("#9e9e9e")

        ax = self.canvas.axes
        ax.clear()
        ax.set_xlabel("Channel (nRF24L01+)")
        ax.set_ylabel("Activity (%)")
        ax.set_ylim(0, 100)
        ax.set_xlim(CHANNEL_MIN - 0.5, CHANNEL_MAX + 0.5)
        ax.grid(True, alpha=0.3)
        backend_label = (
            "Hardware (nRF24L01+)" if self.main_window.get_backend() == "hardware"
            else "Simulation (deterministic model)"
        )
        ax.set_title(f"Live Spectrum — {backend_label}")

        if any(a > 0 for a in activities):
            ax.bar(channels, activities, color=colours, width=0.8,
                   edgecolor="white", linewidth=0.5)

        thr = self._config.thresholds
        for val, label, colour in [
            (thr.clear_max, "Clear ≤ 24%", "green"),
            (thr.moderate_max, "Moderate ≤ 49%", "orange"),
            (thr.busy_max, "Busy ≤ 74%", "red"),
        ]:
            ax.axhline(y=val, color=colour, linestyle=":", alpha=0.5, linewidth=1)

        self.canvas.figure.tight_layout()
        self.canvas.draw()

    def _update_status_bar(self, observations) -> None:
        scan_count = self.spectrum_data.get_scan_count()

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
        backend_label = (
            "Hardware (nRF24L01+)" if self.main_window.get_backend() == "hardware"
            else "Simulation (deterministic model)"
        )

        if self.main_window.is_scanning():
            prog = (
                f" — last scanned: Ch {self._last_channel}"
                if self._last_channel is not None else ""
            )
            status_txt = (
                f"Scanning ({backend_label}) | cycles: {scan_count} | "
                f"busiest: Ch {busiest_ch} ({busiest_pct:.1f}%) | "
                f"avg activity: {avg:.1f}%{prog}"
            )
        else:
            status_txt = f"Stopped ({backend_label}) | cycles: {scan_count}"

        self.main_window._sb().set(status_txt)

    # ------------------------------------------------------------------ slots
    def _on_start_scan(self) -> None:
        start_ch = int(self.start_ch_var.get())
        end_ch = int(self.end_ch_var.get())
        window_s = float(self.window_var.get())
        interval_ms = float(self.interval_var.get())
        self.main_window.start_scan(start_ch, end_ch, window_s, interval_ms)
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)

    def _on_stop_scan(self) -> None:
        self.main_window.stop_scan()
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)

    def _on_mode_change(self, event=None) -> None:
        backend = self.backend_var.get()
        self.main_window.set_backend(backend)
        self.update_source_label()

    def _draw_empty_chart(self) -> None:
        ax = self.canvas.axes
        ax.clear()
        ax.set_title("Live Spectrum — not scanning")
        ax.set_xlabel("Channel (nRF24L01+)")
        ax.set_ylabel("Activity (%)")
        ax.set_ylim(0, 100)
        ax.set_xlim(CHANNEL_MIN - 0.5, CHANNEL_MAX + 0.5)
        ax.grid(True, alpha=0.3)
        ax.text(
            0.5, 0.5, "No scan data\nPress Start Scan",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=11, color="#94a3b8",
        )
        self.canvas.draw()

    def _log(self, message: str, level: str = "INFO") -> None:
        import time
        timestamp = time.strftime("%H:%M:%S")
        self.diag_text.config(state=tk.NORMAL)
        self.diag_text.insert(tk.END, f"[{timestamp}] {level}: {message}\n")
        self.diag_text.see(tk.END)
        self.diag_text.config(state=tk.DISABLED)
