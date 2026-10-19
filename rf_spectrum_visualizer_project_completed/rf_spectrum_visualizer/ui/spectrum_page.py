"""Spectrum page for RF Spectrum Visualizer - refined layout with modern components."""

import tkinter as tk
from tkinter import ttk
import time
from typing import Optional, Dict, Callable

from config import AppConfig
from analysis.selector import ChannelSelector
from mitigation.blocklist_manager import BlocklistManager
from services.data_service import DataService
from scanner.scanner_engine import SpectrumData
from scanner.scanner_engine import ChannelObservation

# Import new components
from ui.components import (
    WaterfallWidget, SpectrumWidget, ChannelTableWidget, 
    CollapsiblePanel
)


class SpectrumPage:
    """Spectrum page - refined layout with clean waterfall, spectrum, and channel table."""
    
    def __init__(
        self,
        parent: ttk.Frame,
        config: AppConfig,
        spectrum_data: SpectrumData,
        channel_selector: ChannelSelector,
        blocklist: BlocklistManager,
        data_service: DataService,
        get_waterfall_data: Callable[[float], list],
    ):
        self._config = config
        self._spectrum_data = spectrum_data
        self._channel_selector = channel_selector
        self._blocklist = blocklist
        self._data_service = data_service
        self._get_waterfall_data = get_waterfall_data
        
        self._create_ui(parent)
    
    @property
    def frame(self) -> ttk.Frame:
        return self._frame
    
    def _create_ui(self, parent: ttk.Frame) -> None:
        """Create the refined spectrum page UI."""
        self._frame = ttk.Frame(parent)
        self._frame.pack(fill=tk.BOTH, expand=True)
        
        # Main container with padding
        main_container = ttk.Frame(self._frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        
        # Create vertical paned window for resizable sections
        self._paned = ttk.PanedWindow(main_container, orient=tk.VERTICAL)
        self._paned.pack(fill=tk.BOTH, expand=True)
        
        # ===== TOP: Channel Table (collapsible) =====
        table_panel = CollapsiblePanel(self._paned, "Channel Activity (126 channels)", initially_open=True)
        self._paned.add(table_panel, weight=2)
        
        self._channel_table = ChannelTableWidget(
            table_panel.content, self._config, self._spectrum_data,
            self._channel_selector, self._blocklist, self._data_service
        )
        self._channel_table.frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== MIDDLE: Live Spectrum (collapsible) =====
        spectrum_panel = CollapsiblePanel(self._paned, "Live Spectrum", initially_open=True)
        self._paned.add(spectrum_panel, weight=2)
        
        self._spectrum_widget = SpectrumWidget(
            spectrum_panel.content, self._config, self._spectrum_data, self._blocklist
        )
        self._spectrum_widget.frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== BOTTOM: Waterfall (collapsible) =====
        waterfall_panel = CollapsiblePanel(self._paned, "Waterfall (Time vs Frequency)", initially_open=True)
        self._paned.add(waterfall_panel, weight=3)
        
        self._waterfall_widget = WaterfallWidget(
            waterfall_panel.content, self._config, self._spectrum_data, self._blocklist
        )
        self._waterfall_widget.frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== BOTTOM: Alerts & Diagnostics (collapsible, initially minimized) =====
        alerts_panel = CollapsiblePanel(self._paned, "Alerts & Diagnostics", initially_open=False)
        self._paned.add(alerts_panel, weight=0)
        
        self._create_alerts_panel(alerts_panel.content)
        
        # Log initial message
        self.log_message("RF Spectrum Visualizer ready. Select backend and press Start Scanning.")
    
    def _create_alerts_panel(self, parent: ttk.Frame) -> None:
        """Create compact alerts panel."""
        self._alerts_text = tk.Text(
            parent, height=5, wrap=tk.WORD, state=tk.DISABLED, 
            font=("Consolas", 8), bg="#fafafa", relief=tk.FLAT
        )
        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self._alerts_text.yview)
        self._alerts_text.configure(yscrollcommand=vsb.set)
        
        self._alerts_text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
    
    def update(self) -> None:
        """Update all widgets with current data."""
        observations = self._spectrum_data.get_all_observations()
        
        self._channel_table.update(observations)
        self._spectrum_widget.update(observations)
        self._waterfall_widget.update(observations)
    
    def refresh(self) -> None:
        """Full refresh of the page."""
        self.update()
    
    def log_message(self, message: str) -> None:
        """Log a message to the alerts panel."""
        timestamp = time.strftime("%H:%M:%S")
        self._alerts_text.config(state=tk.NORMAL)
        self._alerts_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self._alerts_text.see(tk.END)
        self._alerts_text.config(state=tk.DISABLED)
    
    def clear_history(self) -> None:
        """Clear all visual history."""
        self._spectrum_data.clear()
        self._waterfall_widget.clear()
        self._channel_selector.reset_peaks()
        self.update()
    
    def export_png(self, path: str) -> None:
        """Export spectrum graph as PNG."""
        self._spectrum_widget.export_png(path)
    
    def export_waterfall_png(self, path: str) -> None:
        """Export waterfall as PNG."""
        self._waterfall_widget.export_png(path)