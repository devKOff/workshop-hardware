# rf_spectrum_visualizer.gui.pages.start_analysis - Start Analysis Page
# Summary cards, chart placeholder, and results table

import customtkinter as ctk
from tk import Frame, Label, Button, ttk
from rf_spectrum_visualizer.config import get_frequency_mhz, validate_channel, DEFAULT_CHANNEL
from rf_spectrum_visualizer.gui.theme import (
    get_card_style,
    get_table_header_style,
    get_table_row_style,
    get_font,
    COLOR_CRIMON_ACCENT,
    COLOR_CRIMON_LIGHT,
    COLOR_WHITE,
    COLOR_TEXT_DARK,
    COLOR_NAVY_SIDEBAR,
)


class StartAnalysisPage(Frame):
    """Start Analysis page with summary cards, chart placeholder, and results table."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **get_workspace_style())

        # --- Summary Cards Frame ---
        self.cards_frame = LabelFrame(
            self,
            text="Summary",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_NAVY_SIDEBAR,
            background=COLOR_WHITE,
        )
        self.cards_frame.pack(fill="x", padx=20, pady=10)

        # Card 1: Total Channels
        self.channels_card = LabelFrame(
            self.cards_frame,
            text="Total Channels",
            font=get_font(FONT_SIZE_SMALL, FONT_WEIGHT_BOLD),
            background=COLOR_WHITE,
        )
        self.channels_card.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        self.channels_value = Label(
            self.channels_card,
            text=str(RF_CHANNEL_MAX + 1),
            font=get_font(FONT_SIZE_LARGE, FONT_WEIGHT_BOLD),
            foreground=COLOR_CRIMON_ACCENT,
            background=COLOR_WHITE,
        )
        self.channels_value.pack(padx=5, pady=5)

        # Card 2: Validated Channels
        self.validated_card = LabelFrame(
            self.cards_frame,
            text="Validated",
            font=get_font(FONT_SIZE_SMALL, FONT_WEIGHT_BOLD),
            background=COLOR_WHITE,
        )
        self.validated_card.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.validated_value = Label(
            self.validated_card,
            text=f"{RF_CHANNEL_MAX + 1} (0–125)",
            font=get_font(FONT_SIZE_SMALL),
            foreground=COLOR_TEXT_DARK,
            background=COLOR_WHITE,
        )
        self.validated_value.pack(padx=5, pady=5)

        # Card 3: Default Channel
        self.default_card = LabelFrame(
            self.cards_frame,
            text="Default Channel",
            font=get_font(FONT_SIZE_SMALL, FONT_WEIGHT_BOLD),
            background=COLOR_WHITE,
        )
        self.default_card.grid(row=0, column=2, padx=10, pady=5, sticky="ew")
        self.default_value = Label(
            self.default_card,
            text=get_channel_label(DEFAULT_CHANNEL),
            font=get_font(FONT_SIZE_SMALL),
            foreground=COLOR_TEXT_DARK,
            background=COLOR_WHITE,
        )
        self.default_value.pack(padx=5, pady=5)

        # Configure columns
        self.cards_frame.columnconfigure(0, weight=1)
        self.cards_frame.columnconfigure(1, weight=1)
        self.cards_frame.columnconfigure(2, weight=1)

        # --- Chart Placeholder ---
        self.chart_placeholder = Label(
            self,
            text="Analysis Chart Placeholder\n(Visualization: Frequency vs Power Spectral Density)",
            font=get_font(FONT_SIZE_LARGE),
            foreground=COLOR_TEXT_DARK,
            background=COLOR_WHITE,
            relief="flat",
            width=40,
            height=10,
        )
        self.chart_placeholder.pack(pady=20, padx=20, fill="both", expand=True)

        # --- Results Table ---
        self.results_label = Label(
            self,
            text="Analysis Results",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_NAVY_SIDEBAR,
            background=COLOR_WHITE,
        )
        self.results_label.pack(anchor="w", padx=20)

        # Treeview for results
        self.results_table = ttk.Treeview(self, columns=("channel", "frequency", "peak_power"), show="headings", height=6)
        self.results_table.pack(fill="x", padx=20, pady=5)

        self.results_table.heading("channel", text="Channel")
        self.results_table.heading("frequency", text="Frequency (MHz)")
        self.results_table.heading("peak_power", text="Peak Power (dBm)")

        self.results_table.column("channel", width=100, anchor=CENTER)
        self.results_table.column("frequency", width=150, anchor=CENTER)
        self.results_table.column("peak_power", width=150, anchor=CENTER)

        # Populate sample results
        self._populate_results_table()

        # --- Placeholder Button ---
        self.placeholder_btn = Button(
            self,
            text="Run Full Analysis",
            font=get_font(FONT_SIZE_DEFAULT, FONT_WEIGHT_BOLD),
            foreground=COLOR_WHITE,
            background=COLOR_CRIMON_ACCENT,
            activeforeground=COLOR_CRIMON_ACCENT,
            activebackground=COLOR_WHITE,
            cursor="hand2",
            relief="flat",
            command=self._on_run_analysis,
        )
        self.placeholder_btn.pack(pady=15)

    def _populate_results_table(self):
        """Populate the results table with sample channel data."""
        for item in self.results_table.get_children():
            self.results_table.delete(item)

        # Add sample results for a few channels
        sample_channels = [1, 6, 11, 25, 50, 75, 100, 125]
        for ch in sample_channels:
            if validate_channel(ch):
                freq = get_frequency_mhz(ch)
                # Placeholder power values
                self.results_table.insert("", "end", values=(ch, f"{freq} MHz", "-95.2'))

    def _on_run_analysis(self):
        """Handle Run Full Analysis button click."""
        self.chart_placeholder.configure(text="Analysis running... (backend integration pending)")
        # TODO: Integrate real analysis algorithms here