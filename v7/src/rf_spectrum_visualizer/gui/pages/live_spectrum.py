"""rf_spectrum_visualizer.gui.pages.live_spectrum

Page 1: Live Spectrum.

Toolbar: Mode dropdown (sim/hardware), Start Scan, Stop Scan, Clear Display,
Channels from-to spinboxes (0-125), Window (s), Interval (ms), scan-rate
readout, Data Source note label.
Channel table: Ch, Freq MHz, Activity %, Status (Clear/Busy/Heavy Load),
Samples, RPD+, Data OK — green/pink row colors.
Live bar chart: Activity % by channel, green/orange/red, dotted threshold
lines.
Waterfall: heatmap of Activity % over time (rows = scan cycles, columns =
channels 0-125).
Diagnostics/Log box.

Background scan thread + queue; clean Start/Stop; errors logged; falls
back to SimBackend if HardwareBackend fails.

The only metric is Activity % = (samples with RPD true / total samples) x 100.
No dBm or calibrated power is ever claimed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from rf_spectrum_visualizer.gui.theme import (
    BG,
    CARD,
    GREEN,
    GREEN_BG,
    MUTED,
    ORANGE,
    PINK,
    RED,
    RED_ALERT,
    TEXT,
    THRESHOLD_BUSY,
    THRESHOLD_HEAVY,
    activity_color,
    channel_status,
)
from rf_spectrum_visualizer.scan_backend import (
    ChannelStats,
    HardwareBackend,
    SimBackend,
)
from rf_spectrum_visualizer.scan_worker import (
    ScanComplete,
    ScanError,
    ScanProgress,
    ScanResult,
    ScanWorker,
)

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:  # pragma: no cover - matplotlib required for GUI
    HAS_MATPLOTLIB = False

# Waterfall config
WATERFALL_MAX_ROWS = 120   # number of scan cycles to keep in the heatmap
WATERFALL_COLS = 126       # channels 0-125


class LiveSpectrumPage(ttk.Frame):
    """Live Spectrum page."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.configure(style="Card.TFrame")

        self.worker: Optional[ScanWorker] = None
        self._channel_stats: dict[int, ChannelStats] = {}
        self._scanning = False
        self._after_id: Optional[str] = None

        # Waterfall buffer: list of rows, each row is a list of 126 activity %.
        self._waterfall_rows: list[list[float]] = []

        self._build_ui()
        self._poll_queue()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # Toolbar
        toolbar = tk.Frame(self, bg=BG)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))

        tk.Label(toolbar, text="Mode:", bg=BG, fg=TEXT).pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="sim")
        self.mode_combo = ttk.Combobox(
            toolbar,
            textvariable=self.mode_var,
            values=["sim", "hardware"],
            state="readonly",
            width=10,
        )
        self.mode_combo.pack(side=tk.LEFT, padx=(4, 12))

        self.start_btn = tk.Button(
            toolbar,
            text="Start Scan",
            bg=GREEN,
            fg="white",
            bd=0,
            padx=12,
            pady=4,
            command=self._start_scan,
        )
        self.start_btn.pack(side=tk.LEFT, padx=2)

        self.stop_btn = tk.Button(
            toolbar,
            text="Stop Scan",
            bg=RED,
            fg="white",
            bd=0,
            padx=12,
            pady=4,
            command=self._stop_scan,
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, padx=2)

        self.clear_btn = tk.Button(
            toolbar,
            text="Clear Display",
            bg=ORANGE,
            fg="white",
            bd=0,
            padx=12,
            pady=4,
            command=self._clear_display,
        )
        self.clear_btn.pack(side=tk.LEFT, padx=2)

        tk.Label(toolbar, text="Ch from:", bg=BG, fg=TEXT).pack(
            side=tk.LEFT, padx=(16, 2)
        )
        self.ch_from = tk.Spinbox(toolbar, from_=0, to=125, width=5)
        self.ch_from.delete(0, tk.END)
        self.ch_from.insert(0, "0")
        self.ch_from.pack(side=tk.LEFT)

        tk.Label(toolbar, text="to:", bg=BG, fg=TEXT).pack(side=tk.LEFT, padx=(4, 2))
        self.ch_to = tk.Spinbox(toolbar, from_=0, to=125, width=5)
        self.ch_to.delete(0, tk.END)
        self.ch_to.insert(0, "125")
        self.ch_to.pack(side=tk.LEFT)

        tk.Label(toolbar, text="Window (s):", bg=BG, fg=TEXT).pack(
            side=tk.LEFT, padx=(16, 2)
        )
        self.window_s = tk.Spinbox(toolbar, from_=1, to=3600, width=6)
        self.window_s.delete(0, tk.END)
        self.window_s.insert(0, "10")
        self.window_s.pack(side=tk.LEFT)

        tk.Label(toolbar, text="Interval (ms):", bg=BG, fg=TEXT).pack(
            side=tk.LEFT, padx=(8, 2)
        )
        self.interval_ms = tk.Spinbox(toolbar, from_=100, to=60000, width=6)
        self.interval_ms.delete(0, tk.END)
        self.interval_ms.insert(0, "1000")
        self.interval_ms.pack(side=tk.LEFT)

        # Scan-rate readout
        self.scan_rate_var = tk.StringVar(value="Scan rate: -- ch/s")
        self.scan_rate_label = tk.Label(
            toolbar,
            textvariable=self.scan_rate_var,
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9, "bold"),
        )
        self.scan_rate_label.pack(side=tk.LEFT, padx=(16, 0))

        # Data Source note
        self.data_source_var = tk.StringVar(
            value="Data Source: Simulation (deterministic model, no radio)"
        )
        self.data_source_label = tk.Label(
            toolbar,
            textvariable=self.data_source_var,
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9),
        )
        self.data_source_label.pack(side=tk.LEFT, padx=(24, 0))

        # Middle: table + chart split
        middle = tk.PanedWindow(self, bg=BG, orient=tk.HORIZONTAL)
        middle.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Channel table
        table_frame = tk.Frame(middle, bg=CARD, bd=1, relief=tk.SOLID)
        middle.add(table_frame, width=520)

        tk.Label(
            table_frame,
            text="Channel Table",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=8, pady=(6, 2))

        cols = ("ch", "freq", "activity", "status", "samples", "rpd", "ok")
        self.tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", height=14
        )
        self.tree.heading("ch", text="Ch")
        self.tree.heading("freq", text="Freq MHz")
        self.tree.heading("activity", text="Activity %")
        self.tree.heading("status", text="Status")
        self.tree.heading("samples", text="Samples")
        self.tree.heading("rpd", text="RPD+")
        self.tree.heading("ok", text="Data OK")
        self.tree.column("ch", width=40, anchor=tk.CENTER)
        self.tree.column("freq", width=70, anchor=tk.CENTER)
        self.tree.column("activity", width=70, anchor=tk.CENTER)
        self.tree.column("status", width=90, anchor=tk.CENTER)
        self.tree.column("samples", width=60, anchor=tk.CENTER)
        self.tree.column("rpd", width=50, anchor=tk.CENTER)
        self.tree.column("ok", width=55, anchor=tk.CENTER)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)

        tree_scroll = ttk.Scrollbar(
            table_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        # Chart + waterfall stacked
        chart_frame = tk.Frame(middle, bg=CARD, bd=1, relief=tk.SOLID)
        middle.add(chart_frame)

        tk.Label(
            chart_frame,
            text="Activity % by Channel",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=8, pady=(6, 2))

        self.chart_canvas: Optional[object] = None
        if HAS_MATPLOTLIB:
            # Bar chart (top half)
            self.fig = Figure(figsize=(5, 5), dpi=100)
            self.ax_bar = self.fig.add_subplot(2, 1, 1)
            self.ax_bar.set_ylabel("Activity %")
            self.ax_bar.set_ylim(0, 105)
            self.ax_bar.axhline(
                THRESHOLD_BUSY, color=ORANGE, linestyle=":", linewidth=1
            )
            self.ax_bar.axhline(
                THRESHOLD_HEAVY, color=RED_ALERT, linestyle=":", linewidth=1
            )
            # Waterfall heatmap (bottom half)
            self.ax_wf = self.fig.add_subplot(2, 1, 2)
            self.ax_wf.set_xlabel("Channel")
            self.ax_wf.set_ylabel("Scan cycle")
            self.ax_wf.set_yticks([])
            self.im = None
            self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
            self.chart_canvas = self.canvas
        else:
            tk.Label(
                chart_frame,
                text="Matplotlib not installed - chart disabled",
                bg=CARD,
                fg=MUTED,
            ).pack(padx=8, pady=8)

        # Diagnostics / Log
        log_frame = tk.Frame(self, bg=CARD, bd=1, relief=tk.SOLID)
        log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(4, 8))

        tk.Label(
            log_frame,
            text="Diagnostics / Log",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=8, pady=(4, 2))

        self.log_text = tk.Text(
            log_frame, height=6, bg="#fafafa", fg=TEXT, font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.X, padx=8, pady=(0, 6))
        log_scroll = ttk.Scrollbar(
            log_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scroll.set)

    # ------------------------------------------------------------------ log
    def _log(self, message: str) -> None:
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    # ------------------------------------------------------------------ scan control
    def _start_scan(self) -> None:
        if self._scanning:
            return
        try:
            ch_from = int(self.ch_from.get())
            ch_to = int(self.ch_to.get())
        except ValueError:
            self._log("Error: invalid channel range")
            return
        if not (0 <= ch_from <= 125 and 0 <= ch_to <= 125 and ch_from <= ch_to):
            self._log("Error: channel range must be 0-125 and from <= to")
            return

        mode = self.mode_var.get()
        backend = None
        if mode == "hardware":
            try:
                backend = HardwareBackend()
                self.data_source_var.set(
                    "Data Source: Hardware (nRF24L01+, CE=GPIO25, CSN=CE0)"
                )
            except Exception as exc:
                self._log(f"Hardware unavailable, falling back to sim: {exc}")
                backend = None
                self.data_source_var.set(
                    "Data Source: Simulation (hardware unavailable)"
                )
        if backend is None:
            backend = SimBackend()
            if mode == "hardware":
                self.data_source_var.set(
                    "Data Source: Simulation (hardware fallback)"
                )
            else:
                self.data_source_var.set(
                    "Data Source: Simulation (deterministic model)"
                )

        channels = list(range(ch_from, ch_to + 1))
        self.worker = ScanWorker(backend=backend)
        self._channel_stats.clear()
        self._waterfall_rows.clear()
        self._refresh_table()
        self._refresh_chart()

        self._scanning = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.NORMAL)
        self._log(f"Start Scan: channels {ch_from}-{ch_to} ({mode})")

        self.worker.start(channels, samples=100)

    def _stop_scan(self) -> None:
        if not self._scanning or self.worker is None:
            return
        self.worker.stop()
        self._log("Stop Scan requested")

    def _clear_display(self) -> None:
        """Clear the live display (table, chart, waterfall) without stopping the scan."""
        self._channel_stats.clear()
        self._waterfall_rows.clear()
        self._refresh_table()
        self._refresh_chart()
        self._log("Display cleared")

    # ------------------------------------------------------------------ queue polling
    def _poll_queue(self) -> None:
        """Called periodically by tkinter.after() to drain the worker queue."""
        # Update scan-rate readout every poll.
        if self.worker is not None:
            rate = self.worker.scan_rate
            self.scan_rate_var.set(f"Scan rate: {rate:.1f} ch/s")

        if self.worker is None:
            self._after_id = self.after(200, self._poll_queue)
            return

        drained = False
        while True:
            try:
                msg = self.worker.result_queue.get_nowait()
            except Exception:
                break
            drained = True
            self._handle_message(msg)

        if not self.worker.running and not drained:
            # Worker finished and queue empty
            if self._scanning:
                self._scanning = False
                self.start_btn.config(state=tk.NORMAL)
                self.stop_btn.config(state=tk.DISABLED)
                self.scan_rate_var.set("Scan rate: -- ch/s")
                self._log("Scan complete")
            self.worker = None
        else:
            self._after_id = self.after(200, self._poll_queue)

    def _handle_message(self, msg: object) -> None:
        if isinstance(msg, ScanProgress):
            self._log(msg.message)
        elif isinstance(msg, ScanResult):
            self._channel_stats[msg.stats.channel] = msg.stats
            self._refresh_table()
            self._refresh_chart()
        elif isinstance(msg, ScanError):
            self._log(f"Error: {msg.message}")
        elif isinstance(msg, ScanComplete):
            # A full scan cycle finished - add a row to the waterfall.
            self._add_waterfall_row()
            self._log("Scan complete")
            self._scanning = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.scan_rate_var.set("Scan rate: -- ch/s")
            self.worker = None

    # ------------------------------------------------------------------ waterfall
    def _add_waterfall_row(self) -> None:
        """Build one waterfall row from current channel stats and add to buffer."""
        row = [0.0] * WATERFALL_COLS
        for ch, s in self._channel_stats.items():
            if 0 <= ch < WATERFALL_COLS:
                row[ch] = s.activity_percent
        self._waterfall_rows.insert(0, row)  # newest row at top
        if len(self._waterfall_rows) > WATERFALL_MAX_ROWS:
            self._waterfall_rows = self._waterfall_rows[:WATERFALL_MAX_ROWS]

    # ------------------------------------------------------------------ table / chart
    def _refresh_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for ch in sorted(self._channel_stats):
            s = self._channel_stats[ch]
            status = channel_status(s.activity_percent)
            rpd_plus = "yes" if s.rpd_true > 0 else "no"
            ok = "yes" if s.samples > 0 else "no"
            tags = ("busy",) if s.activity_percent >= THRESHOLD_BUSY else ("clear",)
            self.tree.insert(
                "",
                tk.END,
                values=(s.channel, s.freq_mhz,
                        round(s.activity_percent, 1), status, s.samples,
                        s.rpd_true, ok),
                tags=tags,
            )
        self.tree.tag_configure("clear", background=GREEN_BG)
        self.tree.tag_configure("busy", background=PINK)

    def _refresh_chart(self) -> None:
        if not HAS_MATPLOTLIB or self.chart_canvas is None:
            return
        # Bar chart
        self.ax_bar.clear()
        self.ax_bar.set_ylabel("Activity %")
        self.ax_bar.set_ylim(0, 105)
        self.ax_bar.axhline(
            THRESHOLD_BUSY, color=ORANGE, linestyle=":", linewidth=1
        )
        self.ax_bar.axhline(
            THRESHOLD_HEAVY, color=RED_ALERT, linestyle=":", linewidth=1
        )
        if self._channel_stats:
            chans = sorted(self._channel_stats)
            values = [self._channel_stats[c].activity_percent for c in chans]
            colors = [activity_color(v) for v in values]
            self.ax_bar.bar(chans, values, color=colors, width=0.7)
        # Waterfall heatmap
        self.ax_wf.clear()
        self.ax_wf.set_xlabel("Channel")
        self.ax_wf.set_ylabel("Scan cycle (newest at top)")
        self.ax_wf.set_yticks([])
        if self._waterfall_rows:
            # imshow expects [rows, cols]; origin='upper' puts row 0 at top.
            self.im = self.ax_wf.imshow(
                self._waterfall_rows,
                aspect="auto",
                interpolation="nearest",
                cmap="RdYlGn_r",
                vmin=0,
                vmax=100,
                origin="upper",
                extent=[0, WATERFALL_COLS - 1, 0, len(self._waterfall_rows) - 1],
            )
        self.chart_canvas.draw()
