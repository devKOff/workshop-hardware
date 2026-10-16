"""Start Analysis page: real analysis of shared scanner data.

Analyzes actual measurements from the shared SpectrumData produced by the
Live Spectrum scanner (Phase 2). Does NOT start a second scanner and does
NOT create its own radio/hardware access.

Features:
- Working Start Analysis button (on-demand analysis of latest scan data)
- Summary cards: channels analyzed, busiest channel, average activity,
  recommended clear channels
- Channel activity bar chart, color-coded by status
- Results table: Channel, Freq (MHz), Activity (%), Status, Recommendation
- Status labels: Clear / Moderate / Busy / Heavy Load / INSUFFICIENT DATA
- Blocked channels excluded from recommendations (interface for future
  blocker integration — no blocker data is invented)
- Handles missing data, incomplete scans, invalid readings
- Data freshness / staleness indicators
- No fake measurements are invented
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass, field
from typing import Optional, Set

from .canvas import MplCanvas
from ..constants import (
    RF_CHANNEL_MIN,
    RF_CHANNEL_MAX,
    RF_BASE_FREQUENCY_MHZ,
    COLOR_WORKSPACE_BG,
    COLOR_TEXT_DARK,
    COLOR_CRIMON_ACCENT,
    COLOR_CRIMON_LIGHT,
)
from ..v3_bridge import ChannelObservation
from ..utils.channel import channel_to_frequency, validate_channel

CHANNEL_MIN = RF_CHANNEL_MIN
CHANNEL_MAX = RF_CHANNEL_MAX
BASE_FREQUENCY = RF_BASE_FREQUENCY_MHZ

# Stale data threshold: observations older than this many seconds are "stale".
STALE_SECONDS = 60.0

STATUS_COLOURS = {
    "Clear": "#e8f5e9",
    "Moderate": "#fff3e0",
    "Busy": "#ffebee",
    "Heavy Load": "#fce4ec",
    "INSUFFICIENT DATA": "#f5f5f5",
    "Pending": "#eceff1",
    "Blocked": "#f3e5f5",
}

RECOMMENDATION_COLOURS = {
    "Recommended": "#1b5e20",
    "Use with caution": "#b45309",
    "Avoid": "#b00020",
    "Blocked — excluded": "#6a1b9a",
    "No data": "#666666",
    "Blocked — no data": "#6a1b9a",
}


@dataclass
class AnalysisEntry:
    """Single-channel analysis result."""
    channel: int
    frequency_mhz: int
    activity_percentage: Optional[float]
    status: str
    blocked: bool
    recommendation: str
    data_sufficient: bool


@dataclass
class AnalysisResult:
    """Snapshot of an analysis run over the shared scan data."""
    entries: list[AnalysisEntry] = field(default_factory=list)
    channels_analyzed: int = 0
    busiest_channel: Optional[int] = None
    busiest_activity: Optional[float] = None
    average_activity: float = 0.0
    recommended_channels: list[int] = field(default_factory=list)
    scan_count: int = 0
    last_update: Optional[float] = None
    empty: bool = True
    stale: bool = False


def run_analysis(
    spectrum_data,
    config,
    excluded_channels: Optional[Set[int]] = None,
) -> AnalysisResult:
    """Analyze the latest observations from SpectrumData.

    Pure function — no GUI, no scanner thread, no hardware access. Returns
    an AnalysisResult snapshot based solely on measurements already present
    in SpectrumData.

    Args:
        spectrum_data: Shared SpectrumData instance (read-only).
        config: AppConfig with channel range and thresholds.
        excluded_channels: Optional set of blocked channel numbers (from
            Blocker page). Blocked channels are excluded from recommendations.

    Returns:
        AnalysisResult with per-channel entries and summary statistics.
    """
    import time

    excluded = excluded_channels or set()
    observations = spectrum_data.get_all_observations()
    start_ch = config.channel.start_channel
    end_ch = config.channel.end_channel
    thresholds = config.thresholds

    scan_count = spectrum_data.get_scan_count()
    last_update = spectrum_data.get_last_update()

    # No observations at all -> empty result.
    if not observations:
        return AnalysisResult(
            entries=[], channels_analyzed=0, busiest_channel=None,
            busiest_activity=None, average_activity=0.0,
            recommended_channels=[], scan_count=scan_count,
            last_update=last_update, empty=True, stale=False,
        )

    # Staleness: no new observations in the last STALE_SECONDS.
    now = time.time()
    stale = (
        last_update is not None and (now - last_update) > STALE_SECONDS
    )

    entries: list[AnalysisEntry] = []
    sufficient: list[AnalysisEntry] = []

    for ch in range(start_ch, end_ch + 1):
        obs = observations.get(ch)
        freq = BASE_FREQUENCY + ch
        blocked = ch in excluded

        # Missing observation, insufficient samples, or invalid reading.
        if (
            obs is None
            or not obs.data_sufficient
            or obs.activity_percentage is None
        ):
            entries.append(AnalysisEntry(
                channel=ch,
                frequency_mhz=freq,
                activity_percentage=None,
                status="INSUFFICIENT DATA",
                blocked=blocked,
                recommendation=(
                    "Blocked — no data" if blocked else "No data"
                ),
                data_sufficient=False,
            ))
            continue

        activity = obs.activity_percentage
        status = thresholds.classify(activity)

        entry = AnalysisEntry(
            channel=ch,
            frequency_mhz=freq,
            activity_percentage=activity,
            status=status,
            blocked=blocked,
            recommendation="",  # assigned below
            data_sufficient=True,
        )
        sufficient.append(entry)
        entries.append(entry)

    # Assign recommendations based on status + blocker exclusion.
    for entry in sufficient:
        if entry.blocked:
            entry.recommendation = "Blocked — excluded"
        elif entry.status == "Clear":
            entry.recommendation = "Recommended"
        elif entry.status == "Moderate":
            entry.recommendation = "Use with caution"
        else:  # Busy or Heavy Load
            entry.recommendation = "Avoid"

    channels_analyzed = len(sufficient)
    if sufficient:
        busiest = max(sufficient, key=lambda e: e.activity_percentage or 0.0)
        busiest_channel = busiest.channel
        busiest_activity = busiest.activity_percentage
        average_activity = (
            sum(e.activity_percentage or 0.0 for e in sufficient)
            / channels_analyzed
        )
        recommended_channels = sorted(
            e.channel for e in sufficient
            if e.recommendation == "Recommended" and not e.blocked
        )
    else:
        busiest_channel = None
        busiest_activity = None
        average_activity = 0.0
        recommended_channels = []

    return AnalysisResult(
        entries=entries,
        channels_analyzed=channels_analyzed,
        busiest_channel=busiest_channel,
        busiest_activity=busiest_activity,
        average_activity=average_activity,
        recommended_channels=recommended_channels,
        scan_count=scan_count,
        last_update=last_update,
        empty=False,
        stale=stale,
    )


class StartAnalysisPage(tk.Frame):
    """Start Analysis page backed by the shared SpectrumData."""

    def __init__(self, parent, main_window, spectrum_data):
        super().__init__(parent, bg=COLOR_WORKSPACE_BG)
        self.main_window = main_window
        self.spectrum_data = spectrum_data
        self._config = main_window.config

        self._result: Optional[AnalysisResult] = None
        self._analyzing = False

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = tk.Frame(self, bg=COLOR_WORKSPACE_BG)
        root.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Title.
        tk.Label(
            root, text="Start Analysis",
            font=("Segoe UI", 16, "bold"), bg=COLOR_WORKSPACE_BG,
            fg=COLOR_TEXT_DARK,
        ).pack(anchor=tk.W, pady=(0, 4))

        # Toolbar: Start Analysis button + status indicator.
        tb = tk.Frame(root, bg=COLOR_WORKSPACE_BG)
        tb.pack(fill=tk.X, pady=(0, 12))

        self.btn_analyze = tk.Button(
            tb, text="Start Analysis", command=self._on_start_analysis,
            bg=COLOR_CRIMON_ACCENT, fg="white", activebackground="#b71c1c",
            relief=tk.FLAT, padx=14, pady=4,
        )
        self.btn_analyze.pack(side=tk.LEFT, padx=(0, 8))

        self.status_var = tk.StringVar(value="Ready — no analysis run yet")
        self.status_label = tk.Label(
            tb, textvariable=self.status_var, bg=COLOR_WORKSPACE_BG,
            fg=COLOR_TEXT_DARK, font=("Segoe UI", 9, "italic"),
        )
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Freshness indicator (stale data warning).
        self.freshness_var = tk.StringVar(value="")
        self.freshness_label = tk.Label(
            tb, textvariable=self.freshness_var, bg=COLOR_WORKSPACE_BG,
            fg="#b00020", font=("Segoe UI", 9, "bold"),
        )
        self.freshness_label.pack(side=tk.LEFT, padx=(16, 0))

        # Summary cards.
        cards = tk.Frame(root, bg=COLOR_WORKSPACE_BG)
        cards.pack(fill=tk.X, pady=(0, 16))

        self.card_scanned = self._make_card(cards, "Channels Analyzed", "0")
        self.card_busiest = self._make_card(cards, "Busiest Channel", "—")
        self.card_average = self._make_card(cards, "Average Activity", "0.0%")
        self.card_recommended = self._make_card(cards, "Recommended Clear", "0")

        for card in (
            self.card_scanned, self.card_busiest, self.card_average,
            self.card_recommended,
        ):
            card.pack(side=tk.LEFT, padx=(0, 10))

        # Chart section.
        tk.Label(
            root, text="Channel Activity Comparison",
            font=("Segoe UI", 14, "bold"), bg=COLOR_WORKSPACE_BG,
            fg=COLOR_TEXT_DARK,
        ).pack(anchor=tk.W, pady=(0, 4))
        self.canvas = MplCanvas(root, width=10, height=3.2, dpi=100)
        self._draw_placeholder_chart()

        # Results table section.
        tk.Label(
            root, text="Analysis Results",
            font=("Segoe UI", 14, "bold"), bg=COLOR_WORKSPACE_BG,
            fg=COLOR_TEXT_DARK,
        ).pack(anchor=tk.W, pady=(16, 4))

        columns = ("channel", "frequency", "activity", "status", "recommendation")
        self.tree = ttk.Treeview(root, columns=columns, show="headings")
        self.tree.heading("channel", text="Ch")
        self.tree.heading("frequency", text="Freq (MHz)")
        self.tree.heading("activity", text="Activity (%)")
        self.tree.heading("status", text="Status")
        self.tree.heading("recommendation", text="Recommendation")
        self.tree.column("channel", width=50, anchor=tk.CENTER)
        self.tree.column("frequency", width=100, anchor=tk.CENTER)
        self.tree.column("activity", width=110, anchor=tk.CENTER)
        self.tree.column("status", width=150, anchor=tk.CENTER)
        self.tree.column("recommendation", width=200, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Empty-state hint.
        self.hint_label = tk.Label(
            root,
            text=(
                "Run a Live Spectrum scan first, then press Start Analysis "
                "to analyze the collected measurements."
            ),
            fg="#666666", bg=COLOR_WORKSPACE_BG,
            font=("Segoe UI", 9, "italic"),
        )
        self.hint_label.pack(anchor=tk.W, pady=(8, 0))

    def _make_card(self, parent, title: str, value: str) -> tk.Frame:
        card = tk.Frame(parent, bg="#ffffff", relief=tk.RAISED, borderwidth=1)
        tk.Label(
            card, text=title, bg="#ffffff", fg="#666666",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor=tk.W, padx=14, pady=(10, 2))
        lbl = tk.Label(
            card, text=value, bg="#ffffff", fg="#333333",
            font=("Segoe UI", 20, "bold"),
        )
        lbl.pack(anchor=tk.W, padx=14, pady=(0, 10))
        return card

    def _set_card_value(self, card: tk.Frame, value: str) -> None:
        # The value label is the second child (index 1) of the card frame.
        value_lbl = card.winfo_children()[1]
        value_lbl.config(text=value)

    # ------------------------------------------------------------------ public API
    def get_blocked_channels(self) -> Set[int]:
        """Return blocked channels live from MainWindow's Blocker page.

        Blocked channels are excluded from recommendations but remain visible
        in the results table.
        """
        return self.main_window.get_blocked_channels()

    def refresh_from_data(self) -> None:
        """Re-run analysis against the latest SpectrumData (main thread)."""
        if self._analyzing:
            return
        blocked = self.get_blocked_channels()
        result = run_analysis(self.spectrum_data, self._config, blocked)
        self._display_result(result)

    # ------------------------------------------------------------------ analysis
    def _on_start_analysis(self) -> None:
        if self._analyzing:
            return
        # Analysis does NOT start a scanner — it only reads existing data.
        if self.spectrum_data.get_scan_count() == 0:
            messagebox.showinfo(
                "No scan data",
                "No scan measurements have been collected yet. "
                "Run a Live Spectrum scan first, then start analysis.",
            )
            return

        self._analyzing = True
        self.btn_analyze.configure(state=tk.DISABLED)
        self.status_var.set("Analyzing scan data...")
        self.freshness_var.set("")

        # Analysis is fast (in-memory dict read) — run on main thread.
        try:
            blocked = self.get_blocked_channels()
            result = run_analysis(self.spectrum_data, self._config, blocked)
            self._display_result(result)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Analysis error", f"Analysis failed: {e}")
            self.status_var.set("Analysis failed.")
        finally:
            self._analyzing = False
            self.btn_analyze.configure(state=tk.NORMAL)

    def _display_result(self, result: AnalysisResult) -> None:
        self._result = result

        # Update status text.
        if result.empty:
            self.status_var.set("No scan data available.")
            self.freshness_var.set("")
        elif result.stale:
            self.status_var.set(
                f"Analysis complete (stale data — {result.scan_count} scan cycle(s))."
            )
            self.freshness_var.set("WARNING: scan data may be stale.")
        else:
            self.status_var.set(
                f"Analysis complete — {result.channels_analyzed} channel(s) "
                f"analyzed, {result.scan_count} scan cycle(s)."
            )
            self.freshness_var.set("")

        # Update summary cards.
        self._set_card_value(
            self.card_scanned, str(result.channels_analyzed)
        )
        if result.busiest_channel is not None:
            busiest_txt = f"Ch {result.busiest_channel}"
            if result.busiest_activity is not None:
                busiest_txt += f" ({result.busiest_activity:.1f}%)"
        else:
            busiest_txt = "—"
        self._set_card_value(self.card_busiest, busiest_txt)
        self._set_card_value(
            self.card_average, f"{result.average_activity:.1f}%"
        )
        self._set_card_value(
            self.card_recommended, str(len(result.recommended_channels))
        )

        # Draw chart.
        self._draw_chart(result)

        # Populate results table.
        self._populate_table(result)

        # Show/hide hint.
        self.hint_label.pack_forget() if not result.empty else None
        if result.empty:
            self.hint_label.pack(anchor=tk.W, pady=(8, 0))

    # ------------------------------------------------------------------ chart
    def _draw_chart(self, result: AnalysisResult) -> None:
        ax = self.canvas.axes
        ax.clear()
        ax.set_xlabel("Channel (nRF24L01+)")
        ax.set_ylabel("Activity (%)")
        ax.set_ylim(0, 100)
        ax.set_xlim(CHANNEL_MIN - 0.5, CHANNEL_MAX + 0.5)
        ax.grid(True, alpha=0.3)
        ax.set_title("Channel Activity Comparison — Analysis")

        channels = [e.channel for e in result.entries]
        activities = [
            (e.activity_percentage if e.activity_percentage is not None else 0.0)
            for e in result.entries
        ]
        colours = []
        for e in result.entries:
            if e.blocked:
                colours.append("#9400d3")  # dark violet for blocked
            elif e.status == "Heavy Load":
                colours.append("#ef5350")
            elif e.status == "Busy":
                colours.append("#ffa726")
            elif e.status == "Moderate":
                colours.append("#ffca28")
            elif e.status == "Clear":
                colours.append("#66bb6a")
            else:
                colours.append("#9e9e9e")

        if any(a > 0 for a in activities):
            ax.bar(channels, activities, color=colours, width=0.8,
                   edgecolor="white", linewidth=0.5)

        # Threshold reference lines.
        thr = self._config.thresholds
        for val, label, colour in [
            (thr.clear_max, "Clear ≤ 24%", "green"),
            (thr.moderate_max, "Moderate ≤ 49%", "orange"),
            (thr.busy_max, "Busy ≤ 74%", "red"),
        ]:
            ax.axhline(y=val, color=colour, linestyle=":", alpha=0.5, linewidth=1)

        self.canvas.figure.tight_layout()
        self.canvas.draw()

    def _draw_placeholder_chart(self) -> None:
        ax = self.canvas.axes
        ax.clear()
        ax.set_title("Channel Activity Comparison — Analysis")
        ax.set_xlabel("Channel (nRF24L01+)")
        ax.set_ylabel("Activity (%)")
        ax.set_ylim(0, 100)
        ax.set_xlim(CHANNEL_MIN - 0.5, CHANNEL_MAX + 0.5)
        ax.grid(True, alpha=0.3)
        ax.text(
            0.5, 0.5,
            "No analysis data\nPress Start Analysis to populate results",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=11, color="#94a3b8",
        )
        self.canvas.draw()

    # ------------------------------------------------------------------ table
    def _populate_table(self, result: AnalysisResult) -> None:
        # Clear existing rows.
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        for entry in result.entries:
            activity_str = (
                f"{entry.activity_percentage:.1f}%"
                if entry.activity_percentage is not None else "N/A"
            )
            tag = entry.status
            if entry.blocked:
                tag = "Blocked"

            values = (
                entry.channel,
                entry.frequency_mhz,
                activity_str,
                entry.status,
                entry.recommendation,
            )
            self.tree.insert(
                "", tk.END, values=values, tags=(tag,),
            )

        # Row tag colours.
        for tag, colour in STATUS_COLOURS.items():
            self.tree.tag_configure(tag, background=colour)
