# rf_spectrum_visualizer.gui.pages.live_spectrum - Live Spectrum Page
# Empty spectrum chart, channel table, and Start/Stop Scan buttons

import customtkinter as ctk
from tk import Frame, Label, Button, Entry, messagebox, ttk
from rf_spectrum_visualizer.config import (
    validate_channel,
    get_frequency_mhz,
    get_channel_label,
    RF_CHANNEL_MIN,
    RF_CHANNEL_MAX,
)
from rf_spectrum_visualizer.gui.theme import (
    get_table_header_style,
    get_table_row_style,
    get_crimon_accent_style,
    get_font,
)


class LiveSpectrumPage(Frame):
    """Live Spectrum page with chart placeholder, channel table, and scan controls."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **get_workspace_style())
        self.scan_running = False

        # --- Spectrum Chart Placeholder ---
        self.chart_frame = Label(
            self,
            text="Spectrum Chart Placeholder\n(Axes: Frequency (MHz) vs Power dBm)",
            font=get_font(FONT_SIZE_LARGE),
            foreground=COLOR_TEXT_DARK,
            background=COLOR_WHITE,
            relief="flat",
            width=40,
            height=15,
        )
        self.chart_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # --- Channel Table ---
        self.channel_table_label = Label(
            self,
            text="Channel Table",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_NAVY_SIDEBAR,
            background=COLOR_WHITE,
        )
        self.channel_table_label.pack(anchor="w", padx=20)

        # Create a simple treeview for channel table
        self.table = ttk.Treeview(self, columns=("channel", "frequency", "status"), show="headings", height=6)
        self.table.pack(fill="x", padx=20, pady=5)

        # Define headings
        self.table.heading("channel", text="Channel")
        self.table.heading("frequency", text="Frequency (MHz)")
        self.table.heading("status", text="Status")

        # Set column widths
        self.table.column("channel", width=100, anchor=CENTER)
        self.table.column("frequency", width=150, anchor=CENTER)
        self.table.column("status", width=150, anchor=CENTER)

        # Populate sample channels (0, 11, 25, 50, 75, 100, 125)
        self._populate_channel_table()

        # --- Start/Stop Scan Buttons ---
        self.button_frame = Frame(self, background=COLOR_WHITE)
        self.button_frame.pack(fill="x", padx=20, pady=15)

        self.start_btn = Button(
            self.button_frame,
            text="Start Scan",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_WHITE,
            background=COLOR_CRIMON_ACCENT,
            activeforeground=COLOR_CRIMON_ACCENT,
            activebackground=COLOR_WHITE,
            cursor="hand2",
            relief="flat",
            command=self._on_start_scan,
        )
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = Button(
            self.button_frame,
            text="Stop Scan",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_WHITE,
            background="#505050",
            state="disabled",
            activeforeground="#505050",
            activebackground=COLOR_WHITE,
            cursor="hand2",
            relief="flat",
            command=self._on_stop_scan,
        )
        self.stop_btn.pack(side="left", padx=10)

    def _populate_channel_table(self):
        """Populate the channel table with valid channels 0–125."""
        # Clear existing items
        for item in self.table.get_children():
            self.table.delete(item)

        # Add channels at intervals for readability
        step = 20
        for ch in range(RF_CHANNEL_MIN, RF_CHANNEL_MAX + 1, step):
            freq = get_frequency_mhz(ch)
            label = get_channel_label(ch)
            self.table.insert("", "end", values=(ch, f"{freq} MHz", label))

        # Also add a few intermediate channels
        for ch in [11, 36, 61, 86, 111]:
            if ch not in range(RF_CHANNEL_MIN, RF_CHANNEL_MAX + 1, step):
                freq = get_frequency_mhz(ch)
                label = get_channel_label(ch)
                self.table.insert("", "end", values=(ch, f"{freq} MHz", label))

    def _on_start_scan(self):
        """Handle Start Scan button click."""
        if not validate_channel(DEFAULT_CHANNEL):
            messagebox.showerror("Invalid Channel", f"Channel {DEFAULT_CHANNEL} is out of range [0, 125]")
            return
        self.scan_running = True
        self.start_btn.configure(state="disabled", background="#505050")
        self.stop_btn.configure(state="normal", background=COLOR_CRIMON_ACCENT)
        self.chart_frame.configure(text="Scanning... (live updates pending backend)")
        # TODO: Integrate real RF scanning here

    def _on_stop_scan(self):
        """Handle Stop Scan button click."""
        self.scan_running = False
        self.start_btn.configure(state="normal", background=COLOR_CRIMON_ACCENT)
        self.stop_btn.configure(state="disabled", background="#505050")
        self.chart_frame.configure(text="Spectrum Chart Placeholder\n(Axes: Frequency (MHz) vs Power dBm)")