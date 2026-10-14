import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import threading
import time
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from hardware_radio import HardwareRadio
from sim_radio import SimRadio
from scanner import SpectrumData, ScannerThread
from mitigation import MitigationEngine, MitigationEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

WIFI_CHANNELS = {1: 2412, 6: 2437, 11: 2462}
CHANNELS = list(range(126))
FREQS = [2400 + c for c in CHANNELS]


class RFVisualizerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("2.4 GHz ISM Band Spectrum Visualizer & Mitigation")
        self.root.geometry("1200x900")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.radio = None
        self.spectrum_data = SpectrumData()
        self.scanner_thread: Optional[ScannerThread] = None
        self.mitigation_engine: Optional[MitigationEngine] = None
        
        self._running = False
        self._update_job = None
        self._sim_mode = True
        self._armed = False
        
        self._build_ui()
        self._init_plots()
        self._start_simulation()
    
    def _build_ui(self):
        """Construct the main UI layout."""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        control_frame = ttk.LabelFrame(main_frame, text="Controls")
        control_frame.pack(fill=tk.X, pady=(0, 5))
        self._build_control_panel(control_frame)
        
        plot_frame = ttk.Frame(main_frame)
        plot_frame.pack(fill=tk.BOTH, expand=True)
        self._build_plots(plot_frame)
        
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        self._build_status_bar(status_frame)
    
    def _build_control_panel(self, parent):
        """Build control panel with mode, thresholds, and mitigation controls."""
        row = 0
        
        ttk.Label(parent, text="Mode:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        self.mode_var = tk.StringVar(value="Simulation")
        mode_combo = ttk.Combobox(parent, textvariable=self.mode_var, 
                                   values=["Simulation", "Hardware"], state="readonly", width=12)
        mode_combo.grid(row=row, column=1, padx=5, pady=5)
        mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)
        
        ttk.Label(parent, text="Sweep Speed:").grid(row=row, column=2, padx=5, pady=5, sticky=tk.W)
        self.dwell_var = tk.IntVar(value=130)
        dwell_scale = ttk.Scale(parent, from_=50, to=2000, variable=self.dwell_var, 
                                 orient=tk.HORIZONTAL, length=150, command=self._on_dwell_change)
        dwell_scale.grid(row=row, column=3, padx=5, pady=5)
        self.dwell_label = ttk.Label(parent, text="130 µs")
        self.dwell_label.grid(row=row, column=4, padx=5, pady=5)
        
        ttk.Label(parent, text="Peak Decay:").grid(row=row, column=5, padx=5, pady=5, sticky=tk.W)
        self.decay_var = tk.DoubleVar(value=0.995)
        decay_scale = ttk.Scale(parent, from_=0.90, to=0.999, variable=self.decay_var,
                                 orient=tk.HORIZONTAL, length=150, command=self._on_decay_change)
        decay_scale.grid(row=row, column=6, padx=5, pady=5)
        self.decay_label = ttk.Label(parent, text="0.995")
        self.decay_label.grid(row=row, column=7, padx=5, pady=5)
        
        row = 1
        ttk.Label(parent, text="Mitigation Threshold (dBm):").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        self.threshold_var = tk.DoubleVar(value=-50.0)
        thresh_scale = ttk.Scale(parent, from_=-90, to=-10, variable=self.threshold_var,
                                  orient=tk.HORIZONTAL, length=200, command=self._on_threshold_change)
        thresh_scale.grid(row=row, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)
        self.threshold_label = ttk.Label(parent, text="-50 dBm")
        self.threshold_label.grid(row=row, column=3, padx=5, pady=5)
        
        ttk.Label(parent, text="Target Channels:").grid(row=row, column=4, padx=5, pady=5, sticky=tk.W)
        self.target_text = tk.Text(parent, height=1, width=30)
        self.target_text.grid(row=row, column=5, columnspan=3, padx=5, pady=5, sticky=tk.W)
        self.target_text.insert("1.0", "1,6,11")
        
        row = 2
        self.arm_btn = tk.Button(parent, text="ARM MITIGATION", bg="green", fg="white",
                                  font=("Arial", 12, "bold"), width=18, command=self._toggle_arm)
        self.arm_btn.grid(row=row, column=0, padx=10, pady=10)
        
        self.mit_type_var = tk.StringVar(value="carrier")
        ttk.Radiobutton(parent, text="Carrier Wave", variable=self.mit_type_var, value="carrier",
                         command=self._on_mit_type_change).grid(row=row, column=1, padx=5, pady=5)
        ttk.Radiobutton(parent, text="Packet Noise", variable=self.mit_type_var, value="noise",
                         command=self._on_mit_type_change).grid(row=row, column=2, padx=5, pady=5)
        
        ttk.Button(parent, text="Manual Trigger", command=self._manual_trigger).grid(row=row, column=3, padx=5, pady=5)
        ttk.Button(parent, text="Reset Peak Hold", command=self._reset_peak_hold).grid(row=row, column=4, padx=5, pady=5)
        ttk.Button(parent, text="Export CSV", command=self._export_csv).grid(row=row, column=5, padx=5, pady=5)
        ttk.Button(parent, text="Export PNG", command=self._export_png).grid(row=row, column=6, padx=5, pady=5)
        ttk.Button(parent, text="View Audit Log", command=self._view_audit_log).grid(row=row, column=7, padx=5, pady=5)
        
        parent.columnconfigure(3, weight=1)
    
    def _build_plots(self, parent):
        """Build matplotlib plots embedded in Tkinter."""
        self.fig = Figure(figsize=(12, 8), dpi=100)
        self.fig.patch.set_facecolor('#1e1e1e')
        
        self.ax_spectrum = self.fig.add_subplot(2, 1, 1, facecolor='#2d2d2d')
        self.ax_waterfall = self.fig.add_subplot(2, 1, 2, facecolor='#2d2d2d')
        
        self.fig.subplots_adjust(hspace=0.35, left=0.07, right=0.98, top=0.95, bottom=0.08)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect('button_press_event', self._on_plot_click)
        
        self._init_spectrum_plot()
        self._init_waterfall_plot()
    
    def _init_spectrum_plot(self):
        """Initialize spectrum plot."""
        ax = self.ax_spectrum
        ax.set_xlim(0, 125)
        ax.set_ylim(-110, -20)
        ax.set_xlabel("Channel (0-125)", color='white')
        ax.set_ylabel("Power (dBm)", color='white')
        ax.set_title("Real-time Spectrum with Peak Hold", color='white', fontsize=12)
        ax.grid(True, alpha=0.3, color='gray')
        ax.tick_params(colors='white')
        for spine in ax.spines.values():
            spine.set_color('gray')
        
        self.line_current, = ax.plot(CHANNELS, np.full(126, -100), 
                                      color='#00ff88', linewidth=1, label='Current')
        self.line_peak, = ax.plot(CHANNELS, np.full(126, -100),
                                   color='#ffaa00', linewidth=1, linestyle='--', label='Peak Hold')
        self.line_avg, = ax.plot(CHANNELS, np.full(126, -100),
                                  color='#4488ff', linewidth=0.8, alpha=0.7, label='Rolling Avg')
        
        for ch, freq in WIFI_CHANNELS.items():
            ch_idx = freq - 2400
            ax.axvline(ch_idx, color='#ff4444', alpha=0.5, linestyle=':', linewidth=1)
            ax.text(ch_idx, -25, f"Wi-Fi {ch}", rotation=90, va='bottom', ha='right',
                    color='#ff8888', fontsize=8, alpha=0.8)
        
        ax.legend(loc='upper right', facecolor='#2d2d2d', edgecolor='gray', labelcolor='white')
    
    def _init_waterfall_plot(self):
        """Initialize waterfall plot."""
        ax = self.ax_waterfall
        ax.set_xlim(0, 125)
        ax.set_ylim(0, 200)
        ax.set_xlabel("Channel (0-125)", color='white')
        ax.set_ylabel("Time (sweeps ago)", color='white')
        ax.set_title("RF Waterfall History", color='white', fontsize=12)
        ax.tick_params(colors='white')
        for spine in ax.spines.values():
            spine.set_color('gray')
        
        self.waterfall_data = np.zeros((200, 126), dtype=np.float32)
        self.waterfall_img = ax.imshow(
            self.waterfall_data,
            aspect='auto',
            extent=[0, 125, 200, 0],
            cmap='jet',
            vmin=-100,
            vmax=-20,
            interpolation='nearest'
        )
        
        for ch, freq in WIFI_CHANNELS.items():
            ch_idx = freq - 2400
            ax.axvline(ch_idx, color='white', alpha=0.3, linestyle=':', linewidth=0.5)
        
        self.cbar = self.fig.colorbar(self.waterfall_img, ax=ax, label='Power (dBm)')
        self.cbar.ax.yaxis.label.set_color('white')
        self.cbar.ax.tick_params(colors='white')
    
    def _build_status_bar(self, parent):
        """Build status bar with sweep rate and system info."""
        self.status_var = tk.StringVar(value="Initializing...")
        status_label = ttk.Label(parent, textvariable=self.status_var, font=("Consolas", 10))
        status_label.pack(side=tk.LEFT, padx=10)
        
        self.sweep_rate_var = tk.StringVar(value="0 sweeps/s")
        ttk.Label(parent, textvariable=self.sweep_rate_var, font=("Consolas", 10)).pack(side=tk.RIGHT, padx=10)
        
        self.mit_status_var = tk.StringVar(value="DISARMED")
        self.mit_status_label = ttk.Label(parent, textvariable=self.mit_status_var, 
                                           font=("Consolas", 10, "bold"), foreground="green")
        self.mit_status_label.pack(side=tk.RIGHT, padx=20)
    
    def _init_plots(self):
        """Initialize plot data."""
        self._update_plots()
    
    def _start_simulation(self):
        """Start with simulation mode."""
        self._sim_mode = True
        self.radio = SimRadio()
        self.radio.initialize()
        
        self.scanner_thread = ScannerThread(
            self.radio, self.spectrum_data, dwell_time_us=130,
            callback=self._on_sweep_complete
        )
        self.scanner_thread.start()
        
        self.mitigation_engine = MitigationEngine(
            self.radio, self.spectrum_data,
            event_callback=self._on_mitigation_event
        )
        
        self._running = True
        self._update_loop()
    
    def _on_mode_change(self, event=None):
        """Handle mode switch between simulation and hardware."""
        new_sim = self.mode_var.get() == "Simulation"
        if new_sim == self._sim_mode:
            return
            
        self._stop_scanner()
        
        if new_sim:
            self.radio = SimRadio()
            if not self.radio.initialize():
                messagebox.showerror("Error", "Failed to initialize simulation")
                self.mode_var.set("Hardware")
                return
        else:
            self.radio = HardwareRadio()
            if not self.radio.initialize():
                messagebox.showerror("Hardware Error", 
                    "Failed to initialize nRF24L01+ hardware.\n"
                    "Check SPI wiring and pyrf24 installation.\n"
                    "Falling back to simulation mode.")
                self.mode_var.set("Simulation")
                self.radio = SimRadio()
                self.radio.initialize()
        
        self._start_scanner()
        logger.info(f"Switched to {'simulation' if self._sim_mode else 'hardware'} mode")
    
    def _start_scanner(self):
        """Start scanner thread with current radio."""
        self.spectrum_data = SpectrumData()
        self.scanner_thread = ScannerThread(
            self.radio, self.spectrum_data, 
            dwell_time_us=self.dwell_var.get(),
            callback=self._on_sweep_complete
        )
        self.scanner_thread.start()
        
        if self.mitigation_engine:
            self.mitigation_engine.stop_monitoring()
        self.mitigation_engine = MitigationEngine(
            self.radio, self.spectrum_data,
            event_callback=self._on_mitigation_event
        )
        if self._armed:
            self.mitigation_engine.arm()
            self.mitigation_engine.start_monitoring()
    
    def _stop_scanner(self):
        """Stop scanner and mitigation."""
        self._running = False
        if self.scanner_thread:
            self.scanner_thread.stop()
            self.scanner_thread = None
        if self.mitigation_engine:
            self.mitigation_engine.stop_monitoring()
            self.mitigation_engine = None
        if self.radio:
            self.radio.cleanup()
            self.radio = None
    
    def _on_sweep_complete(self, sweep_data: np.ndarray):
        """Callback when sweep completes."""
        pass
    
    def _on_mitigation_event(self, event: MitigationEvent):
        """Callback for mitigation events."""
        self.root.after(0, lambda: self._flash_mitigation_alert(event))
    
    def _flash_mitigation_alert(self, event: MitigationEvent):
        """Flash alert on mitigation trigger."""
        original_bg = self.arm_btn.cget('bg')
        self.arm_btn.config(bg='red')
        self.root.after(200, lambda: self.arm_btn.config(bg=original_bg))
    
    def _update_loop(self):
        """Main UI update loop."""
        if not self._running:
            return
        
        self._update_plots()
        self._update_status()
        
        self._update_job = self.root.after(50, self._update_loop)
    
    def _update_plots(self):
        """Update matplotlib plots with latest data."""
        current = self.spectrum_data.get_current_sweep()
        peak = self.spectrum_data.get_peak_hold()
        avg = self.spectrum_data.get_rolling_avg()
        waterfall = self.spectrum_data.get_waterfall()
        
        self.line_current.set_ydata(current)
        self.line_peak.set_ydata(peak)
        self.line_avg.set_ydata(avg)
        
        if waterfall.shape[0] > 0:
            self.waterfall_data[:waterfall.shape[0], :] = waterfall
            self.waterfall_img.set_data(self.waterfall_data)
        
        self.canvas.draw_idle()
    
    def _update_status(self):
        """Update status bar."""
        if self.scanner_thread:
            rate = self.spectrum_data.get_sweeps_per_sec()
            count = self.spectrum_data.get_sweep_count()
            self.sweep_rate_var.set(f"{rate:.1f} sweeps/s  |  Total: {count}")
        
        mode_str = "SIM" if self._sim_mode else "HW"
        armed_str = "ARMED" if self._armed else "DISARMED"
        self.status_var.set(f"Mode: {mode_str}  |  Mitigation: {armed_str}")
        
        if self._armed:
            self.mit_status_var.set("⚠ ARMED ⚠")
            self.mit_status_label.config(foreground="red")
        else:
            self.mit_status_var.set("DISARMED")
            self.mit_status_label.config(foreground="green")
    
    def _on_dwell_change(self, val):
        dwell = int(float(val))
        self.dwell_label.config(text=f"{dwell} µs")
        if self.scanner_thread:
            self.scanner_thread.set_dwell_time(dwell)
    
    def _on_decay_change(self, val):
        decay = float(val)
        self.decay_label.config(text=f"{decay:.3f}")
        self.spectrum_data.set_peak_decay(decay)
    
    def _on_threshold_change(self, val):
        thresh = float(val)
        self.threshold_label.config(text=f"{thresh:.0f} dBm")
        if self.mitigation_engine:
            self.mitigation_engine.set_threshold(thresh)
    
    def _on_mit_type_change(self):
        if self.mitigation_engine:
            self.mitigation_engine.set_mitigation_type(self.mit_type_var.get())
    
    def _toggle_arm(self):
        """Toggle mitigation armed state."""
        if not self.mitigation_engine:
            return
            
        self._armed = not self._armed
        if self._armed:
            try:
                targets = [int(c.strip()) for c in self.target_text.get("1.0", tk.END).split(",") if c.strip()]
                self.mitigation_engine.set_target_channels(targets)
                self.mitigation_engine.set_threshold(self.threshold_var.get())
                self.mitigation_engine.set_mitigation_type(self.mit_type_var.get())
                self.mitigation_engine.arm()
                self.mitigation_engine.start_monitoring()
                self.arm_btn.config(text="DISARM MITIGATION", bg="red")
            except ValueError:
                messagebox.showerror("Error", "Invalid channel list")
                self._armed = False
        else:
            self.mitigation_engine.disarm()
            self.mitigation_engine.stop_monitoring()
            self.arm_btn.config(text="ARM MITIGATION", bg="green")
    
    def _manual_trigger(self):
        """Manually trigger mitigation on selected channel."""
        if not self.mitigation_engine or not self._armed:
            messagebox.showwarning("Not Armed", "Mitigation must be armed first")
            return
        
        try:
            targets = [int(c.strip()) for c in self.target_text.get("1.0", tk.END).split(",") if c.strip()]
            if not targets:
                return
            channel = targets[0]
            self.mitigation_engine.manual_trigger(channel)
        except ValueError:
            messagebox.showerror("Error", "Invalid channel")
    
    def _reset_peak_hold(self):
        self.spectrum_data.reset_peak_hold()
    
    def _on_plot_click(self, event):
        """Handle plot click for channel selection."""
        if event.inaxes == self.ax_spectrum and event.xdata is not None:
            channel = int(round(event.xdata))
            if 0 <= channel <= 125:
                self.target_text.delete("1.0", tk.END)
                self.target_text.insert("1.0", str(channel))
    
    def _export_csv(self):
        """Export current spectrum data to CSV."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"spectrum_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if not filename:
            return
        
        try:
            current = self.spectrum_data.get_current_sweep()
            peak = self.spectrum_data.get_peak_hold()
            avg = self.spectrum_data.get_rolling_avg()
            
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Channel", "Frequency_MHz", "Current_dBm", "Peak_Hold_dBm", "Rolling_Avg_dBm"])
                for i in range(126):
                    writer.writerow([i, 2400 + i, f"{current[i]:.2f}", f"{peak[i]:.2f}", f"{avg[i]:.2f}"])
            
            messagebox.showinfo("Success", f"Exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
    
    def _export_png(self):
        """Export current plots to PNG."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialfile=f"spectrum_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        if not filename:
            return
        
        try:
            self.fig.savefig(filename, dpi=150, facecolor=self.fig.get_facecolor())
            messagebox.showinfo("Success", f"Exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
    
    def _view_audit_log(self):
        """Open audit log viewer window."""
        if not self.mitigation_engine:
            return
        
        events = self.mitigation_engine.get_recent_events(100)
        
        log_window = tk.Toplevel(self.root)
        log_window.title("Mitigation Audit Log")
        log_window.geometry("800x400")
        
        text = tk.Text(log_window, font=("Consolas", 9))
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(text, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scrollbar.set)
        
        text.insert(tk.END, "Timestamp,Channel,Freq,Peak,Duration,Type,Triggered\n")
        for e in reversed(events):
            text.insert(tk.END, 
                f"{e.timestamp.isoformat()},Ch{e.channel},{e.frequency_mhz:.1f}MHz,"
                f"{e.peak_intensity_db:.1f}dBm,{e.duration_ms}ms,{e.mitigation_type},{e.triggered}\n")
        
        text.config(state=tk.DISABLED)
    
    def _on_close(self):
        """Handle window close."""
        self._running = False
        if self._update_job:
            self.root.after_cancel(self._update_job)
        self._stop_scanner()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = RFVisualizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()