"""Main window for RF Spectrum Visualizer - refined three-section tabbed interface."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import time
from pathlib import Path

from config import AppConfig
from services.data_service import DataService
from services.persistence_service import PersistenceService
from mitigation.blocklist_manager import BlocklistManager
from analysis.selector import ChannelSelector
from scanner.scanner_engine import SpectrumData
from radio import SimRadio, HardwareRadio, check_hardware_availability
from exports.report_generator import ReportGenerator
from ui.spectrum_page import SpectrumPage
from ui.analysis_page import AnalysisPage
from ui.blocker_page import BlockerPage
from exceptions import HardwareError, ScannerError

# Import new UI components
from ui.components import (
    ExportDropdown, ControlGroup, StatusBar, CollapsiblePanel
)


logger = logging.getLogger("rf_visualizer.gui")


class MainWindow:
    """Main application window with refined three tabs: Spectrum, Analysis, Blocker."""
    
    def __init__(self, config: AppConfig):
        self._config = config
        self._root = tk.Tk()
        self._root.title("RF Spectrum Visualizer — 2.4 GHz ISM Band")
        self._root.geometry("1400x900")
        self._root.minsize(1100, 700)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Configure style
        self._configure_styles()
        
        # Core services
        self._persistence = PersistenceService()
        self._blocklist = BlocklistManager(config.blocklist)
        self._spectrum_data = SpectrumData(config)
        self._data_service = DataService(config, self._blocklist)
        self._channel_selector = ChannelSelector(config.channel, config.thresholds, self._blocklist)
        self._report_gen = ReportGenerator(config, self._spectrum_data, self._blocklist, self._channel_selector)
        
        # Scanner state
        self._scanner = None
        self._radio = None
        self._running = False
        self._refresh_job = None
        
        # Setup logging
        self._setup_logging()
        
        # Build UI
        self._build_ui()
        self._update_ui_state()
        self._blocker_page.refresh_blocklist()
    
    def _configure_styles(self) -> None:
        """Configure modern ttk styles."""
        style = ttk.Style()
        
        # Try to use a modern theme
        available = style.theme_names()
        if 'vista' in available:
            style.theme_use('vista')
        elif 'clam' in available:
            style.theme_use('clam')
        elif 'alt' in available:
            style.theme_use('alt')
        
        # Custom styles
        style.configure("Export.TMenubutton", 
                       font=("Segoe UI", 9), padding=(12, 6))
        style.configure("Control.TLabel", font=("Segoe UI", 9))
        style.configure("Control.TSpinbox", font=("Segoe UI", 9))
        style.configure("Toolbar.TFrame", background="#f5f5f5")
        style.configure("Status.TLabel", font=("Segoe UI", 9))
        style.configure("Mode.TLabel", font=("Segoe UI", 9, "bold"), foreground="#1976d2")
        style.configure("Title.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Card.TFrame", relief=tk.FLAT, borderwidth=1)
    
    def _setup_logging(self) -> None:
        from logging_config import setup_logging
        setup_logging(
            log_path=self._config.storage.log_path,
            level=logging.INFO,
            console_level=logging.WARNING,
        )
    
    def _build_ui(self) -> None:
        """Build the refined main UI layout."""
        self._create_menu()
        self._create_refined_toolbar()
        self._create_notebook()
        self._create_status_bar()
    
    def _create_menu(self) -> None:
        menubar = tk.Menu(self._root)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Export All Formats...", command=self._export_all_formats, accelerator="Ctrl+E")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Clear History", command=self._clear_history, accelerator="Ctrl+Shift+C")
        view_menu.add_command(label="Reset Peak Tracking", command=self._reset_peaks)
        menubar.add_cascade(label="View", menu=view_menu)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Hardware Diagnostic", command=self._run_diagnostic)
        tools_menu.add_command(label="Run Simulation Scenario", command=self._run_simulation_dialog)
        tools_menu.add_command(label="Settings...", command=self._show_settings, accelerator="Ctrl+,")
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self._root.config(menu=menubar)
        
        # Bind accelerators
        self._root.bind_all("<Control-e>", lambda e: self._export_all_formats())
        self._root.bind_all("<Control-q>", lambda e: self._on_close())
        self._root.bind_all("<Control-Shift-C>", lambda e: self._clear_history())
        self._root.bind_all("<Control-comma>", lambda e: self._show_settings())
    
    def _create_refined_toolbar(self) -> None:
        """Create refined toolbar with grouped controls and export dropdown."""
        # Main toolbar container with subtle background
        toolbar_container = ttk.Frame(self._root, style="Toolbar.TFrame")
        toolbar_container.pack(fill=tk.X, padx=0, pady=0)
        
        # Primary toolbar - scanning controls
        primary_toolbar = ttk.Frame(toolbar_container)
        primary_toolbar.pack(fill=tk.X, padx=8, pady=6)
        
        # --- Backend & Scan Control Group ---
        scan_group = ControlGroup(primary_toolbar, "Scan Control")
        scan_group.pack(side=tk.LEFT, padx=(0, 8))
        
        # Backend selector
        ttk.Label(scan_group, text="Backend:", style="Control.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self._backend_var = tk.StringVar(value=self._config.default_backend)
        backend_combo = ttk.Combobox(
            scan_group, textvariable=self._backend_var,
            values=["sim", "hardware"], width=10, state="readonly",
            font=("Segoe UI", 9)
        )
        backend_combo.pack(side=tk.LEFT, padx=(0, 8))
        backend_combo.bind("<<ComboboxSelected>>", self._on_backend_change)
        
        # Start/Stop buttons
        self._start_btn = ttk.Button(scan_group, text="▶ Start", command=self._start_scanning, style="Accent.TButton")
        self._start_btn.pack(side=tk.LEFT, padx=(0, 4))
        
        self._stop_btn = ttk.Button(scan_group, text="■ Stop", command=self._stop_scanning, state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT, padx=(0, 4))
        
        # --- Channel Range Group ---
        ch_group = ControlGroup(primary_toolbar, "Channel Range")
        ch_group.pack(side=tk.LEFT, padx=(0, 8))
        
        ttk.Label(ch_group, text="Start:", style="Control.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self._start_ch_var = tk.IntVar(value=self._config.channel.start_channel)
        ttk.Spinbox(ch_group, from_=0, to=125, textvariable=self._start_ch_var, width=5, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        ttk.Label(ch_group, text="End:", style="Control.TLabel").pack(side=tk.LEFT, padx=(8, 4))
        self._end_ch_var = tk.IntVar(value=self._config.channel.end_channel)
        ttk.Spinbox(ch_group, from_=0, to=125, textvariable=self._end_ch_var, width=5, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        # --- Timing Group ---
        timing_group = ControlGroup(primary_toolbar, "Timing")
        timing_group.pack(side=tk.LEFT, padx=(0, 8))
        
        ttk.Label(timing_group, text="Window (s):", style="Control.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self._window_var = tk.DoubleVar(value=self._config.scan.measurement_window)
        ttk.Spinbox(timing_group, from_=0.1, to=10.0, increment=0.1, textvariable=self._window_var, width=6, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        ttk.Label(timing_group, text="Interval (ms):", style="Control.TLabel").pack(side=tk.LEFT, padx=(8, 4))
        self._interval_var = tk.DoubleVar(value=self._config.scan.sampling_interval * 1000)
        ttk.Spinbox(timing_group, from_=1, to=1000, increment=1, textvariable=self._interval_var, width=7, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        # --- Export Dropdown (replaces 4 buttons) ---
        export_group = ControlGroup(primary_toolbar, "Export")
        export_group.pack(side=tk.LEFT, padx=(0, 8))
        
        export_commands = {
            "Export All Formats...": self._export_all_formats,
            "Export JSON": self._export_json,
            "Export CSV": self._export_csv,
            "Export PNG (Spectrum)": lambda: self._export_png("spectrum"),
            "Export PNG (Waterfall)": lambda: self._export_png("waterfall"),
            "export_all": self._export_all_formats,
        }
        self._export_dropdown = ExportDropdown(export_group, export_commands)
        export_group.add_widget(self._export_dropdown)
        
        # Secondary toolbar - status & mode
        secondary_toolbar = ttk.Frame(toolbar_container)
        secondary_toolbar.pack(fill=tk.X, padx=8, pady=(0, 6))
        
        # Scan info
        self._scan_info_var = tk.StringVar(value="Scan count: 0 | Last update: —")
        ttk.Label(secondary_toolbar, textvariable=self._scan_info_var, font=("Segoe UI", 8), foreground="#757575").pack(side=tk.LEFT, padx=4)
        
        # Mode indicator
        self._mode_indicator_var = tk.StringVar(value="● SIM")
        self._mode_label = ttk.Label(secondary_toolbar, textvariable=self._mode_indicator_var, font=("Segoe UI", 9, "bold"), foreground="#1976d2")
        self._mode_label.pack(side=tk.RIGHT, padx=12)
    
    def _create_notebook(self) -> None:
        """Create the three-tab notebook."""
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        # Create pages
        self._spectrum_page = SpectrumPage(
            self._notebook, self._config, self._spectrum_data, self._channel_selector,
            self._blocklist, self._data_service, self._get_waterfall_data
        )
        self._analysis_page = AnalysisPage(
            self._notebook, self._config, self._spectrum_data, self._channel_selector,
            self._blocklist, self._data_service
        )
        self._blocker_page = BlockerPage(
            self._notebook, self._config, self._blocklist, self._channel_selector,
            self._data_service, self._refresh_all_pages
        )
        
        # Add tabs with icons
        self._notebook.add(self._spectrum_page.frame, text="  Spectrum  ")
        self._notebook.add(self._analysis_page.frame, text="  Analysis  ")
        self._notebook.add(self._blocker_page.frame, text="  Blocker  ")
        
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _create_status_bar(self) -> None:
        """Create refined status bar."""
        self._status_bar = StatusBar(self._root)
        self._status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=0, pady=0)
    
    def _update_ui_state(self) -> None:
        """Update UI element states based on running state."""
        if self._running:
            self._start_btn.config(state=tk.DISABLED)
            self._stop_btn.config(state=tk.NORMAL)
            self._status_bar.set_status(f"Scanning... ({self._spectrum_data.get_backend().upper()})")
            self._mode_indicator_var.set(f"● {self._spectrum_data.get_backend().upper()}")
            if self._spectrum_data.get_backend() == "hardware":
                self._mode_label.config(foreground="#c62828")
            else:
                self._mode_label.config(foreground="#1976d2")
        else:
            self._start_btn.config(state=tk.NORMAL)
            self._stop_btn.config(state=tk.DISABLED)
            self._status_bar.set_status("Stopped")
            self._mode_indicator_var.set(f"● {self._config.default_backend.upper()}")
            self._mode_label.config(foreground="#757575")
    
    def _on_backend_change(self, event=None) -> None:
        if self._running:
            messagebox.showwarning("Cannot Change", "Stop scanning before changing backend")
            self._backend_var.set(self._config.default_backend)
            return
        self._config.default_backend = self._backend_var.get()
        self._persistence.update_backend(self._config.default_backend)
        logger.info(f"Backend changed to {self._config.default_backend}")
        self._update_ui_state()
    
    def _on_tab_changed(self, event=None) -> None:
        """Refresh the active tab when switched."""
        tab_id = self._notebook.index(self._notebook.select())
        if tab_id == 0:  # Spectrum
            self._spectrum_page.refresh()
        elif tab_id == 1:  # Analysis
            self._analysis_page.refresh()
        elif tab_id == 2:  # Blocker
            self._blocker_page.refresh()
    
    def _refresh_all_pages(self) -> None:
        """Refresh all three pages."""
        self._spectrum_page.refresh()
        self._analysis_page.refresh()
        self._blocker_page.refresh()
    
    def _start_scanning(self) -> None:
        if self._running:
            return
        
        try:
            self._config.channel.start_channel = self._start_ch_var.get()
            self._config.channel.end_channel = self._end_ch_var.get()
            self._config.scan.measurement_window = self._window_var.get()
            self._config.scan.sampling_interval = self._interval_var.get() / 1000.0
            
            self._persistence.update_channel_config(
                self._config.channel.start_channel,
                self._config.channel.end_channel
            )
            self._persistence.update_scan_config(
                self._config.scan.measurement_window,
                self._config.scan.sampling_interval,
                self._config.scan.min_valid_samples
            )
            
            if self._config.default_backend == "hardware":
                self._radio = HardwareRadio(self._config.channel, self._config.scan, self._config.hardware)
                if not self._radio.is_available():
                    messagebox.showerror("Hardware Unavailable", "pyrf24 not installed or SPI unavailable")
                    return
            else:
                self._radio = SimRadio(self._config.channel, self._config.scan, self._config.sim)
            
            from scanner.scanner_engine import ScannerThread
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
        
        self._spectrum_page.update()
        self._analysis_page.update()
        self._blocker_page.update()
        
        # Update scan info
        scan_count = self._spectrum_data.get_scan_count()
        last_update = self._spectrum_data.get_last_update()
        if last_update > 0:
            age = time.time() - last_update
            self._scan_info_var.set(f"Scan count: {scan_count} | Last update: {age:.1f}s ago")
        else:
            self._scan_info_var.set(f"Scan count: {scan_count} | Last update: —")
        
        self._schedule_refresh()
    
    def _on_observation(self, obs) -> None:
        pass
    
    def _on_scanner_error(self, error: Exception) -> None:
        self._log_message(f"Scanner error: {error}", "ERROR")
    
    def _on_scan_complete(self) -> None:
        pass
    
    def _get_waterfall_data(self, max_age: float = 60.0):
        return self._spectrum_data.get_waterfall_data(max_age=max_age)
    
    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
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
            defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export JSON"
        )
        if path:
            try:
                self._report_gen.export_json_file(path)
                messagebox.showinfo("Export", f"JSON exported to {path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def _export_all_formats(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension="", filetypes=[("All files", "*.*")],
            title="Export All Formats (base filename)"
        )
        if path:
            try:
                base_path = Path(path).with_suffix("")
                results = self._report_gen.export_all_formats(base_path.stem)
                msg = "Exported:\n" + "\n".join(f"  {fmt}: {p}" for fmt, p in results.items())
                messagebox.showinfo("Export", msg)
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def _export_png(self, plot_type: str) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title=f"Export {plot_type.capitalize()} PNG"
        )
        if path:
            try:
                if plot_type == "spectrum":
                    self._spectrum_page.export_png(path)
                else:
                    self._spectrum_page.export_waterfall_png(path)
                messagebox.showinfo("Export", f"PNG exported to {path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))
    
    def _clear_history(self) -> None:
        self._spectrum_data.clear()
        self._channel_selector.reset_peaks()
        self._refresh_all_pages()
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
        dialog.geometry("420x380")
        dialog.transient(self._root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Select scenario:", font=("Segoe UI", 10)).pack(pady=12)
        
        from radio.sim_radio import ScenarioType
        scenario_var = tk.StringVar(value="mixed")
        for scenario in ScenarioType:
            desc = SimRadio.SCENARIOS[scenario]['description']
            ttk.Radiobutton(dialog, text=f"{scenario.value}: {desc}", 
                           variable=scenario_var, value=scenario.value).pack(anchor=tk.W, padx=24, pady=3)
        
        def run_scenario():
            scenario = ScenarioType(scenario_var.get())
            dialog.destroy()
            self._run_simulation_scenario(scenario)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=16)
        ttk.Button(btn_frame, text="Run Scenario", command=run_scenario).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=6)
    
    def _run_simulation_scenario(self, scenario) -> None:
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
        self._refresh_all_pages()
        self._log_message(f"Simulation scenario {scenario.value} complete")
    
    def _show_settings(self) -> None:
        dialog = tk.Toplevel(self._root)
        dialog.title("Settings")
        dialog.geometry("520x520")
        dialog.transient(self._root)
        dialog.grab_set()
        
        nb = ttk.Notebook(dialog)
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        
        # Thresholds tab
        thresh_frame = ttk.Frame(nb)
        nb.add(thresh_frame, text="Thresholds")
        
        for i, (label, attr, default) in enumerate([
            ("Clear max (%):", "clear_max", 24),
            ("Moderate max (%):", "moderate_max", 49),
            ("Busy max (%):", "busy_max", 74),
            ("Heavy min (%):", "heavy_min", 75),
        ]):
            ttk.Label(thresh_frame, text=label, font=("Segoe UI", 9)).grid(row=i, column=0, padx=8, pady=8, sticky=tk.W)
            var = tk.IntVar(value=getattr(self._config.thresholds, attr, default))
            ttk.Spinbox(thresh_frame, from_=0, to=100, textvariable=var, width=10, font=("Segoe UI", 9)).grid(row=i, column=1, padx=8, pady=8)
            setattr(self._config.thresholds, f"_{attr}", var)
        
        # Mitigation tab
        mit_frame = ttk.Frame(nb)
        nb.add(mit_frame, text="Mitigation")
        
        ttk.Label(mit_frame, text="Persistent threshold (%):", font=("Segoe UI", 9)).grid(row=0, column=0, padx=8, pady=8, sticky=tk.W)
        persist_var = tk.DoubleVar(value=self._config.mitigation.persistent_threshold)
        ttk.Spinbox(mit_frame, from_=0, to=100, increment=0.1, textvariable=persist_var, width=10, font=("Segoe UI", 9)).grid(row=0, column=1, padx=8, pady=8)
        
        ttk.Label(mit_frame, text="Hysteresis (%):", font=("Segoe UI", 9)).grid(row=1, column=0, padx=8, pady=8, sticky=tk.W)
        hyst_var = tk.DoubleVar(value=self._config.mitigation.hysteresis)
        ttk.Spinbox(mit_frame, from_=0, to=50, increment=0.1, textvariable=hyst_var, width=10, font=("Segoe UI", 9)).grid(row=1, column=1, padx=8, pady=8)
        
        # Hardware tab
        hw_frame = ttk.Frame(nb)
        nb.add(hw_frame, text="Hardware")
        
        ttk.Label(hw_frame, text="CE Pin:", font=("Segoe UI", 9)).grid(row=0, column=0, padx=8, pady=8, sticky=tk.W)
        ce_var = tk.IntVar(value=self._config.hardware.ce_pin)
        ttk.Spinbox(hw_frame, from_=0, to=27, textvariable=ce_var, width=10, font=("Segoe UI", 9)).grid(row=0, column=1, padx=8, pady=8)
        
        ttk.Label(hw_frame, text="CSN Pin:", font=("Segoe UI", 9)).grid(row=1, column=0, padx=8, pady=8, sticky=tk.W)
        csn_var = tk.IntVar(value=self._config.hardware.csn_pin)
        ttk.Spinbox(hw_frame, from_=0, to=1, textvariable=csn_var, width=10, font=("Segoe UI", 9)).grid(row=1, column=1, padx=8, pady=8)
        
        ttk.Label(hw_frame, text="SPI Speed (Hz):", font=("Segoe UI", 9)).grid(row=2, column=0, padx=8, pady=8, sticky=tk.W)
        spi_var = tk.IntVar(value=self._config.hardware.spi_speed)
        ttk.Spinbox(hw_frame, from_=100000, to=16000000, increment=100000, textvariable=spi_var, width=15, font=("Segoe UI", 9)).grid(row=2, column=1, padx=8, pady=8)
        
        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=12, pady=12)
        
        def apply_settings():
            # Update thresholds
            for attr in ["clear_max", "moderate_max", "busy_max", "heavy_min"]:
                var = getattr(self._config.thresholds, f"_{attr}")
                setattr(self._config.thresholds, attr, var.get())
            
            self._config.mitigation.persistent_threshold = persist_var.get()
            self._config.mitigation.hysteresis = hyst_var.get()
            self._config.hardware.ce_pin = ce_var.get()
            self._config.hardware.csn_pin = csn_var.get()
            self._config.hardware.spi_speed = spi_var.get()
            
            self._persistence.save_config(self._config)
            self._channel_selector.persistent_threshold = self._config.mitigation.persistent_threshold
            self._channel_selector.hysteresis = self._config.mitigation.hysteresis
            self._refresh_all_pages()
            dialog.destroy()
        
        ttk.Button(btn_frame, text="Apply", command=apply_settings).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=6)
    
    def _show_about(self) -> None:
        messagebox.showinfo(
            "About RF Spectrum Visualizer",
            "RF Spectrum Visualizer\n"
            "2.4 GHz ISM Band Monitor for nRF24L01+\n\n"
            "Three Sections:\n"
            "  • Spectrum — Live spectrum display with waterfall\n"
            "  • Analysis — Channel rankings & recommendations\n"
            "  • Blocker — Software channel blocking & management\n\n"
            "Features:\n"
            "  • 126-channel scanning (0–125, freq = 2400 + channel)\n"
            "  • Persistent JSON blocklist\n"
            "  • Channel avoidance algorithm\n"
            "  • Deterministic simulation modes\n"
            "  • Hardware support (Raspberry Pi 3B+ + nRF24L01+)\n"
            "  • CSV/JSON/PNG export\n"
            "  • Real-time spectrum & waterfall\n\n"
            "IMPORTANT: 'BLOCKED IN SOFTWARE' prevents application\n"
            "selection only; it does NOT physically jam or block\n"
            "radio frequencies or disrupt external devices.\n\n"
            "Hardware: Raspberry Pi 3B+ + nRF24L01+\n"
            "Pins: CE=GPIO25, CSN=GPIO8 (SPI CE0)\n\n"
            "Note: nRF24L01+ is a narrowband transceiver.\n"
            "RPD observations are not calibrated power measurements."
        )
    
    def _log_message(self, message: str, level: str = "INFO") -> None:
        timestamp = time.strftime("%H:%M:%S")
        self._spectrum_page.log_message(f"[{timestamp}] {level}: {message}")
    
    def _on_close(self) -> None:
        self._stop_scanning()
        self._root.destroy()
    
    def run(self) -> None:
        self._root.mainloop()