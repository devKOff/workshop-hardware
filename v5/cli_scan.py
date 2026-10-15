"""Command-line interface for RF Spectrum Visualizer V5."""

import argparse
import sys
import time
import json
import csv
import signal
import logging
from typing import Optional, List, TextIO
from pathlib import Path

from config import (
    AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, 
    AnomalyConfig, StorageConfig, GUIConfig, SimulationConfig
)
from scanner import ScannerThread, SpectrumData, ChannelObservation
from sim_radio import SimRadio
from hardware_radio import HardwareRadio, check_hardware_availability
from anomaly_detector import AnomalyDetector, Anomaly
from channel_classifier import ChannelClassifier, RecommendationEngine
from mitigation import MitigationEngine, MitigationState
from report_generator import ReportGenerator, export_spectrum_png
from exceptions import RFVisualizerError, HardwareError, ScannerError
from logging_config import setup_logging, get_logger

logger = get_logger("rf_visualizer.cli")


class CLIDisplay:
    """Terminal display for channel scanning results."""
    
    ACTIVITY_BAR_WIDTH = 50
    
    def __init__(self, config: AppConfig, use_ascii: bool = False):
        self._config = config
        self._use_ascii = use_ascii
        self._last_line_count = 0
        self._supports_ansi = self._check_ansi_support()
        self._show_all = True
        self._filter = "all"
        self._sort_by = "channel"
    
    def _check_ansi_support(self) -> bool:
        import os
        return sys.stdout.isatty() and os.getenv("TERM") != "dumb"
    
    def clear_screen(self) -> None:
        if self._supports_ansi:
            sys.stdout.write("\033[2J\033[H")
        else:
            sys.stdout.write("\n" * 5)
        sys.stdout.flush()
    
    def move_cursor_up(self, lines: int) -> None:
        if self._supports_ansi and lines > 0:
            sys.stdout.write(f"\033[{lines}A")
            sys.stdout.flush()
    
    def render_header(self, backend: str, scan_count: int, 
                      anomalies_count: int = 0) -> List[str]:
        lines = []
        lines.append("=" * 80)
        lines.append("          2.4 GHz RF ACTIVITY MONITOR - V5")
        lines.append("=" * 80)
        lines.append(f"Backend: {backend.upper()}")
        lines.append("Measurement: Repeated nRF24L01+ RPD observations")
        lines.append(f"Scan range: Channels {self._config.channel.start_channel}-{self._config.channel.end_channel}")
        lines.append(f"Window: {self._config.scan.measurement_window:.1f}s per channel, "
                     f"Interval: {self._config.scan.sampling_interval*1000:.0f}ms")
        lines.append(f"Scans completed: {scan_count}")
        if anomalies_count > 0:
            lines.append(f"Active anomalies: {anomalies_count}")
        lines.append(f"Filter: {self._filter.upper()} | Sort: {self._sort_by.upper()}")
        lines.append("-" * 80)
        return lines
    
    def make_activity_bar(self, pct: Optional[float]) -> str:
        if pct is None:
            return "[" + "?" * self.ACTIVITY_BAR_WIDTH + "]"
        filled = int(pct / 100 * self.ACTIVITY_BAR_WIDTH)
        if self._use_ascii:
            return "[" + "#" * filled + "-" * (self.ACTIVITY_BAR_WIDTH - filled) + "]"
        return "[" + "█" * filled + "░" * (self.ACTIVITY_BAR_WIDTH - filled) + "]"
    
    def render_channel(self, obs: ChannelObservation, show_anomaly: bool = False) -> str:
        ch = obs.channel
        freq = obs.frequency_mhz
        
        if obs.activity_percentage is None:
            pct_str = "  N/A"
            bar = self.make_activity_bar(None)
            status = obs.status
        else:
            pct = obs.activity_percentage
            pct_str = f"{pct:5.1f}%"
            bar = self.make_activity_bar(pct)
            status = obs.status
        
        data_flag = "" if obs.data_sufficient else " (insufficient data)"
        error_flag = f" [ERROR: {obs.error}]" if obs.error else ""
        
        anomaly_info = ""
        if show_anomaly and hasattr(obs, 'anomaly') and obs.anomaly:
            anomaly_info = f" [ANOMALY: {obs.anomaly}]"
        
        return (f"Ch {ch:3d} ({freq:4d} MHz) {bar} {pct_str} "
                f"({status}){data_flag}{error_flag}{anomaly_info}")
    
    def render_footer(self, channel_count: int, heavy_count: int, 
                      busy_count: int, insufficient_count: int) -> List[str]:
        lines = []
        lines.append("-" * 80)
        lines.append(f"Channels: {channel_count} | Heavy Load: {heavy_count} | "
                     f"Busy: {busy_count} | Insufficient: {insufficient_count}")
        lines.append("=" * 80)
        return lines
    
    def should_show(self, obs: ChannelObservation) -> bool:
        if self._filter == "all":
            return True
        elif self._filter == "heavy":
            return obs.activity_percentage is not None and obs.activity_percentage >= 75
        elif self._filter == "busy":
            return obs.activity_percentage is not None and obs.activity_percentage >= 50
        elif self._filter == "anomalies":
            return hasattr(obs, 'anomaly') and obs.anomaly is not None
        elif self._filter == "quiet":
            return obs.activity_percentage is not None and obs.activity_percentage <= 25
        elif self._filter == "insufficient":
            return not obs.data_sufficient and not obs.error
        elif self._filter == "errors":
            return obs.error is not None
        return True
    
    def sort_key(self, obs: ChannelObservation) -> tuple:
        if self._sort_by == "channel":
            return (obs.channel,)
        elif self._sort_by == "frequency":
            return (obs.frequency_mhz,)
        elif self._sort_by == "activity":
            return (-(obs.activity_percentage or -1), obs.channel)
        elif self._sort_by == "status":
            return (obs.status, obs.channel)
        return (obs.channel,)
    
    def update(self, spectrum_data: SpectrumData, backend: str, scan_count: int,
               anomaly_detector: Optional[AnomalyDetector] = None) -> None:
        """Update the display with current data."""
        channels = spectrum_data.get_channels_in_range()
        observations = spectrum_data.get_all_observations()
        
        active_anomalies = anomaly_detector.get_active_anomalies() if anomaly_detector else []
        anomaly_channels = {a.channel for a in active_anomalies}
        
        lines = self.render_header(backend, scan_count, len(active_anomalies))
        
        displayed = []
        for ch in channels:
            obs = observations.get(ch)
            if obs:
                if self._filter == "anomalies" and ch not in anomaly_channels:
                    continue
                if hasattr(obs, 'anomaly'):
                    obs.anomaly = ch in anomaly_channels
                if self.should_show(obs):
                    displayed.append(obs)
            else:
                dummy = ChannelObservation(
                    timestamp=time.time(),
                    channel=ch,
                    frequency_mhz=2400 + ch,
                    backend=backend,
                    valid_samples=0,
                    rpd_positive=0,
                    rpd_negative=0,
                    activity_percentage=None,
                    status="NOT_SCANNED",
                    data_sufficient=False,
                    measurement_window=self._config.scan.measurement_window,
                    sampling_interval=self._config.scan.sampling_interval,
                    error="Channel not scanned",
                )
                if self.should_show(dummy):
                    displayed.append(dummy)
        
        displayed.sort(key=self.sort_key)
        
        for obs in displayed:
            lines.append(self.render_channel(obs, show_anomaly=True))
        
        heavy = sum(1 for o in observations.values() 
                   if o.activity_percentage is not None and o.activity_percentage >= 75 and o.data_sufficient)
        busy = sum(1 for o in observations.values() 
                  if o.activity_percentage is not None and o.activity_percentage >= 50 and o.data_sufficient)
        insufficient = sum(1 for o in observations.values() if not o.data_sufficient and not o.error)
        
        lines.extend(self.render_footer(len(channels), heavy, busy, insufficient))
        
        if self._supports_ansi and self._last_line_count > 0:
            self.move_cursor_up(self._last_line_count)
            for line in lines:
                sys.stdout.write("\033[2K" + line + "\n")
        else:
            for line in lines:
                print(line)
        
        self._last_line_count = len(lines)
        sys.stdout.flush()


def create_config_from_args(args: argparse.Namespace) -> AppConfig:
    """Create AppConfig from command line arguments."""
    channel_config = ChannelConfig(
        start_channel=args.start_channel,
        end_channel=args.end_channel,
        channel_filter=args.channels if args.channels else None,
    )
    
    scan_config = ScanConfig(
        measurement_window=args.window,
        sampling_interval=args.interval,
        min_valid_samples=args.min_samples,
        scan_repetitions=args.repetitions,
        retry_failed_channels=not args.no_retry,
        max_retries=args.max_retries,
    )
    
    thresholds = ThresholdConfig(
        clear_max=args.clear_max,
        moderate_max=args.moderate_max,
        busy_max=args.busy_max,
        heavy_min=args.heavy_min,
    )
    
    anomaly_config = AnomalyConfig(
        baseline_learning_scans=args.baseline_scans,
        rolling_history_length=args.history_length,
        persistent_threshold=args.persistent_threshold,
        persistence_windows=args.persistence_windows,
        spike_threshold=args.spike_threshold,
        burst_threshold=args.burst_threshold,
        change_threshold=args.change_threshold,
        alert_cooldown=args.alert_cooldown,
        hysteresis=args.hysteresis,
    )
    
    storage_config = StorageConfig(
        log_path=args.log_path,
        export_dir=args.export_dir,
    )
    
    gui_config = GUIConfig(
        refresh_interval_ms=args.refresh_interval,
    )
    
    sim_config = SimulationConfig(
        seed=args.seed,
        scenario=args.scenario,
    )
    
    return AppConfig(
        channel=channel_config,
        scan=scan_config,
        thresholds=thresholds,
        anomaly=anomaly_config,
        storage=storage_config,
        gui=gui_config,
        simulation=sim_config,
        default_backend=args.backend,
        log_level=args.log_level,
    )


def run_cli_scan(config: AppConfig, output_format: str = "table", 
                 continuous: bool = False, filter_type: str = "all",
                 sort_by: str = "channel") -> int:
    """Run CLI scan and display results."""
    display = CLIDisplay(config, use_ascii=output_format == "ascii")
    display._filter = filter_type
    display._sort_by = sort_by
    
    spectrum_data = SpectrumData(config)
    
    if config.default_backend == "hardware":
        radio = HardwareRadio(config.channel, config.scan)
        if not radio.is_available():
            print("ERROR: Hardware backend not available (pyrf24 not installed)", file=sys.stderr)
            return 1
        try:
            radio.initialize()
        except HardwareError as e:
            print(f"ERROR: Failed to initialize hardware: {e}", file=sys.stderr)
            return 1
    else:
        radio = SimRadio(config.channel, config.scan, 
                        seed=config.simulation.seed,
                        channel_models=None)
        radio.initialize()
    
    anomaly_detector = AnomalyDetector(config.anomaly, config.thresholds, config.channel)
    mitigation_engine = MitigationEngine(
        config.anomaly,
        config.thresholds,
        config.channel,
        anomaly_detector=anomaly_detector,
    )
    if config.anomaly is not None:
        mitigation_engine.arm()
    
    scanner = ScannerThread(config, spectrum_data, radio)
    
    def signal_handler(sig, frame):
        print("\nShutting down...", file=sys.stderr)
        scanner.shutdown()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        scanner.start()
        
        if output_format in ("table", "ascii"):
            while scanner.is_running():
                time.sleep(config.gui.refresh_interval_ms / 1000.0)
                display.update(spectrum_data, config.default_backend, 
                             spectrum_data.get_scan_count(), anomaly_detector)
        
        elif output_format == "json":
            while scanner.is_running():
                time.sleep(1.0)
                report_gen = ReportGenerator(config, spectrum_data, anomaly_detector)
                report_gen.export_json(sys.stdout)
        
        elif output_format == "csv":
            report_gen = ReportGenerator(config, spectrum_data, anomaly_detector)
            while scanner.is_running():
                time.sleep(1.0)
                # Wait for first scan to complete
                if spectrum_data.get_scan_count() > 0:
                    report_gen.export_csv(sys.stdout)
                    break
        
        if not continuous:
            time.sleep(0.5)
            scanner.shutdown()
        
        if output_format in ("table", "ascii"):
            print()
            report_gen = ReportGenerator(config, spectrum_data, anomaly_detector)
            print(report_gen.generate_summary_text())
        
        if output_format == "json":
            report_gen = ReportGenerator(config, spectrum_data, anomaly_detector)
            report_gen.export_json(sys.stdout)
        elif output_format == "csv":
            report_gen = ReportGenerator(config, spectrum_data, anomaly_detector)
            report_gen.export_csv(sys.stdout)
    
    except KeyboardInterrupt:
        pass
    finally:
        scanner.shutdown()
        radio.cleanup()
    
    return 0


def run_single_scan(config: AppConfig) -> int:
    """Run a single complete scan and exit."""
    # Ensure we only run one scan
    config.scan.scan_repetitions = 1
    
    spectrum_data = SpectrumData(config)
    
    if config.default_backend == "hardware":
        radio = HardwareRadio(config.channel, config.scan)
        if not radio.is_available():
            print("ERROR: Hardware backend not available", file=sys.stderr)
            return 1
        try:
            radio.initialize()
        except HardwareError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
    else:
        radio = SimRadio(config.channel, config.scan, seed=config.simulation.seed)
        radio.initialize()
    
    anomaly_detector = AnomalyDetector(config.anomaly, config.thresholds, config.channel)
    
    scanner = ScannerThread(config, spectrum_data, radio)
    
    print(f"Starting single scan ({config.default_backend} backend)...", file=sys.stderr)
    scanner.start()
    
    while scanner.is_running():
        time.sleep(0.1)
    
    scanner.shutdown()
    radio.cleanup()
    
    report_gen = ReportGenerator(config, spectrum_data, anomaly_detector)
    print(report_gen.generate_summary_text())
    
    if config.storage.export_dir:
        paths = report_gen.save_reports()
        print(f"\nReports saved:")
        for fmt, path in paths.items():
            print(f"  {fmt}: {path}")
    
    return 0


def run_diagnostic() -> int:
    """Run hardware diagnostic."""
    print("RF Spectrum Visualizer V5 - Hardware Diagnostic")
    print("=" * 50)
    
    result = check_hardware_availability()
    
    print(f"Python: {sys.version.split()[0]}")
    print(f"pyrf24 installed: {result['pyrf24_installed']}")
    if result['pyrf24_version']:
        print(f"pyrf24 version: {result['pyrf24_version']}")
    
    print(f"SPI devices: {result['spi_devices'] or 'None found'}")
    print(f"GPIO access: {result['gpio_access']}")
    
    if result['errors']:
        print("\nErrors:")
        for err in result['errors']:
            print(f"  - {err}")
    
    if result['pyrf24_installed'] and result['spi_devices']:
        print("\nAttempting hardware initialization (read-only)...")
        try:
            config = AppConfig()
            radio = HardwareRadio(config.channel, config.scan)
            radio.initialize()
            info = radio.get_info()
            print(f"Radio initialized: {info}")
            radio.cleanup()
            print("Hardware test PASSED")
            return 0
        except Exception as e:
            print(f"Hardware test FAILED: {e}")
            return 1
    else:
        print("\nHardware test SKIPPED (missing dependencies)")
        return 0


def run_simulation_test(scenario: str) -> int:
    """Run a simulation test scenario."""
    print(f"Running simulation scenario: {scenario}")
    print("=" * 50)
    
    config = AppConfig()
    config.simulation.scenario = scenario
    config.default_backend = "sim"
    config.scan.measurement_window = 1.0
    config.scan.sampling_interval = 0.01
    
    return run_single_scan(config)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RF Spectrum Visualizer V5 - 2.4 GHz ISM Band Monitor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    parser.add_argument(
        "--backend", choices=["sim", "hardware"], default="sim",
        help="Backend to use for scanning"
    )
    parser.add_argument(
        "--start-channel", type=int, default=0,
        help="Start channel (0-125)"
    )
    parser.add_argument(
        "--end-channel", type=int, default=125,
        help="End channel (0-125)"
    )
    parser.add_argument(
        "--channels", type=int, nargs="+",
        help="Specific channels to scan (overrides range)"
    )
    parser.add_argument(
        "--window", type=float, default=1.0,
        help="Measurement window per channel (seconds)"
    )
    parser.add_argument(
        "--interval", type=float, default=0.01,
        help="Sampling interval (seconds)"
    )
    parser.add_argument(
        "--min-samples", type=int, default=10,
        help="Minimum valid samples for activity calculation"
    )
    parser.add_argument(
        "--repetitions", type=int, default=0,
        help="Number of scan repetitions (0 = continuous)"
    )
    parser.add_argument(
        "--no-retry", action="store_true",
        help="Disable retry on failed channels"
    )
    parser.add_argument(
        "--max-retries", type=int, default=2,
        help="Maximum retries for failed channels"
    )
    parser.add_argument(
        "--clear-max", type=int, default=24,
        help="Clear status max percentage"
    )
    parser.add_argument(
        "--moderate-max", type=int, default=49,
        help="Moderate status max percentage"
    )
    parser.add_argument(
        "--busy-max", type=int, default=74,
        help="Busy status max percentage"
    )
    parser.add_argument(
        "--heavy-min", type=int, default=75,
        help="Heavy load status min percentage"
    )
    parser.add_argument(
        "--baseline-scans", type=int, default=10,
        help="Baseline learning scans"
    )
    parser.add_argument(
        "--history-length", type=int, default=100,
        help="Rolling history length"
    )
    parser.add_argument(
        "--persistent-threshold", type=float, default=75.0,
        help="Persistent activity threshold"
    )
    parser.add_argument(
        "--persistence-windows", type=int, default=3,
        help="Consecutive windows for persistent detection"
    )
    parser.add_argument(
        "--spike-threshold", type=float, default=30.0,
        help="Sudden spike threshold"
    )
    parser.add_argument(
        "--burst-threshold", type=float, default=40.0,
        help="Burst detection threshold"
    )
    parser.add_argument(
        "--change-threshold", type=float, default=25.0,
        help="Unusual change threshold"
    )
    parser.add_argument(
        "--alert-cooldown", type=float, default=30.0,
        help="Alert cooldown (seconds)"
    )
    parser.add_argument(
        "--hysteresis", type=float, default=5.0,
        help="Hysteresis for alert clearing"
    )
    parser.add_argument(
        "--format", choices=["table", "ascii", "json", "csv"], default="table",
        help="Output format"
    )
    parser.add_argument(
        "--sort", choices=["channel", "frequency", "activity", "status"], default="channel",
        help="Sort order"
    )
    parser.add_argument(
        "--filter", choices=["all", "heavy", "busy", "anomalies", "quiet", "insufficient", "errors"], 
        default="all",
        help="Filter channels to display"
    )
    parser.add_argument(
        "--continuous", action="store_true",
        help="Run continuous scans until interrupted"
    )
    parser.add_argument(
        "--single-scan", action="store_true",
        help="Run single scan and exit"
    )
    parser.add_argument(
        "--log-path", default="logs/anomalies.jsonl",
        help="Log file path"
    )
    parser.add_argument(
        "--export-dir", default="exports",
        help="Export directory"
    )
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO",
        help="Log level"
    )
    parser.add_argument(
        "--refresh-interval", type=int, default=500,
        help="GUI refresh interval (ms)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for simulation"
    )
    parser.add_argument(
        "--scenario", choices=[
            "default", "quiet", "moderate", "persistent_busy", "sudden_spike",
            "intermittent_bursts", "multiple_busy", "hopping_like", "sudden_reduction",
            "insufficient_samples", "sensor_failures", "invalid_channel"
        ], default="default",
        help="Simulation scenario"
    )
    parser.add_argument(
        "--diagnostic", action="store_true",
        help="Run hardware diagnostic and exit"
    )
    parser.add_argument(
        "--test-scenario", choices=[
            "default", "quiet", "moderate", "persistent_busy", "sudden_spike",
            "intermittent_bursts", "multiple_busy", "hopping_like", "sudden_reduction",
            "insufficient_samples", "sensor_failures", "invalid_channel"
        ],
        help="Run simulation test scenario and exit"
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=0,
        help="Increase verbosity"
    )
    
    args = parser.parse_args()
    
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, args.log_level)
    
    setup_logging(log_path=args.log_path, level=log_level)
    
    if args.diagnostic:
        return run_diagnostic()
    
    if args.test_scenario:
        return run_simulation_test(args.test_scenario)
    
    config = create_config_from_args(args)
    
    if args.single_scan:
        return run_single_scan(config)
    
    return run_cli_scan(config, args.format, args.continuous, args.filter, args.sort)


if __name__ == "__main__":
    sys.exit(main())