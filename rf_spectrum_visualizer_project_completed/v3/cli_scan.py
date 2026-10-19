"""Command-line interface for RF Spectrum Visualizer."""

import argparse
import sys
import time
import json
import csv
import signal
import logging
from typing import Optional, List, TextIO
from pathlib import Path

from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, MitigationConfig, StorageConfig
from scanner import ScannerThread, SpectrumData, ChannelObservation
from sim_radio import SimRadio
from hardware_radio import HardwareRadio, check_hardware_availability
from mitigation import MitigationEngine, MitigationState
from exceptions import RFVisualizerError, HardwareError, ScannerError
from logging_config import setup_logging, get_logger

logger = get_logger("rf_visualizer.cli")


class CLIDisplay:
    """Terminal display for channel scanning results."""
    
    ACTIVITY_BAR_WIDTH = 40
    ACTIVITY_CHARS = "█░"
    
    def __init__(self, config: AppConfig, use_ascii: bool = False):
        self._config = config
        self._use_ascii = use_ascii
        self._last_line_count = 0
        self._supports_ansi = self._check_ansi_support()
    
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
    
    def render_header(self, backend: str, scan_count: int) -> List[str]:
        lines = []
        lines.append("=" * 60)
        lines.append("          2.4 GHz RF ACTIVITY MONITOR")
        lines.append("=" * 60)
        lines.append(f"Backend: {backend.upper()}")
        lines.append("Measurement: Repeated nRF24L01+ RPD observations")
        lines.append(f"Scan range: Channels {self._config.channel.start_channel}-{self._config.channel.end_channel}")
        lines.append(f"Window: {self._config.scan.measurement_window:.1f}s per channel, "
                     f"Interval: {self._config.scan.sampling_interval*1000:.0f}ms")
        lines.append(f"Scans completed: {scan_count}")
        lines.append(f"Status: {'SCANNING' if scan_count == 0 else 'UPDATING'}")
        lines.append("-" * 60)
        return lines
    
    def render_channel(self, obs: ChannelObservation) -> str:
        ch = obs.channel
        freq = obs.frequency_mhz
        
        if obs.activity_percentage is None:
            pct_str = "N/A"
            bar = "[" + "?" * self.ACTIVITY_BAR_WIDTH + "]"
            status = obs.status
        else:
            pct = obs.activity_percentage
            pct_str = f"{pct:.0f}%"
            filled = int(pct / 100 * self.ACTIVITY_BAR_WIDTH)
            if self._use_ascii:
                bar = "[" + "#" * filled + "-" * (self.ACTIVITY_BAR_WIDTH - filled) + "]"
            else:
                bar = "[" + self.ACTIVITY_CHARS[0] * filled + self.ACTIVITY_CHARS[1] * (self.ACTIVITY_BAR_WIDTH - filled) + "]"
            status = obs.status
        
        data_flag = "" if obs.data_sufficient else " (insufficient data)"
        error_flag = f" [ERROR: {obs.error}]" if obs.error else ""
        
        return f"Ch {ch:3d} ({freq:4d} MHz) {bar} {pct_str:>5} ({status}){data_flag}{error_flag}"
    
    def render_footer(self, channel_count: int) -> List[str]:
        lines = []
        lines.append("-" * 60)
        lines.append(f"Channels scanned: {channel_count}")
        lines.append(f"Results: {'Complete' if channel_count > 0 else 'Pending'}")
        lines.append("=" * 60)
        return lines
    
    def update(self, spectrum_data: SpectrumData, backend: str, scan_count: int) -> None:
        """Update the display with current data."""
        channels = spectrum_data.get_channels_in_range()
        observations = spectrum_data.get_all_observations()
        
        lines = self.render_header(backend, scan_count)
        
        for ch in channels:
            obs = observations.get(ch)
            if obs:
                lines.append(self.render_channel(obs))
            else:
                lines.append(f"Ch {ch:3d} ({2400+ch:4d} MHz) [{'?' * self.ACTIVITY_BAR_WIDTH}]  N/A (Pending)")
        
        lines.extend(self.render_footer(len(channels)))
        
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
    )
    
    scan_config = ScanConfig(
        measurement_window=args.window,
        sampling_interval=args.interval,
        min_valid_samples=args.min_samples,
    )
    
    thresholds = ThresholdConfig(
        clear_max=args.clear_max,
        moderate_max=args.moderate_max,
        busy_max=args.busy_max,
        heavy_min=args.heavy_min,
    )
    
    mitigation_config = MitigationConfig(
        persistent_threshold=args.persistent_threshold,
        persistence_duration=args.persistence_duration,
        consecutive_windows=args.consecutive_windows,
        alert_cooldown=args.alert_cooldown,
        hysteresis=args.hysteresis,
        armed=args.mitigate,
    )
    
    storage_config = StorageConfig(
        log_path=args.log_path,
        export_dir=args.export_dir,
    )
    
    return AppConfig(
        channel=channel_config,
        scan=scan_config,
        thresholds=thresholds,
        mitigation=mitigation_config,
        storage=storage_config,
        default_backend=args.backend,
    )


def run_cli_scan(config: AppConfig, output_format: str = "table", sort_by: str = "channel") -> int:
    """Run CLI scan and display results."""
    display = CLIDisplay(config, use_ascii=output_format == "ascii")
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
        radio = SimRadio(config.channel, config.scan)
        radio.initialize()
    
    mitigation_engine = None
    if config.mitigation.armed:
        mitigation_engine = MitigationEngine(
            config.mitigation,
            config.thresholds,
            config.channel,
        )
        mitigation_engine.arm()
    
    scanner = ScannerThread(config, spectrum_data, radio)
    
    def signal_handler(sig, frame):
        print("\nShutting down...", file=sys.stderr)
        scanner.shutdown()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        scanner.start()
        
        last_export_time = 0
        export_interval = 5.0
        
        while scanner.is_running():
            time.sleep(0.5)
            
            if output_format in ("table", "ascii"):
                display.update(spectrum_data, config.default_backend, spectrum_data.get_scan_count())
            
            if mitigation_engine:
                all_obs = spectrum_data.get_all_observations()
                for obs in all_obs.values():
                    mitigation_engine.process_observation(obs, all_obs)
            
            current_time = time.time()
            if current_time - last_export_time >= export_interval and output_format == "json":
                export_json(spectrum_data, config, sys.stdout)
                last_export_time = current_time
    
    except KeyboardInterrupt:
        pass
    finally:
        scanner.shutdown()
        
        if output_format in ("table", "ascii"):
            print()
        
        if output_format == "json":
            export_json(spectrum_data, config, sys.stdout)
        elif output_format == "csv":
            export_csv(spectrum_data, config, sys.stdout)
    
    return 0


def export_json(spectrum_data: SpectrumData, config: AppConfig, output: TextIO) -> None:
    """Export observations as JSON Lines."""
    data = spectrum_data.export_all()
    result = {
        "config": {
            "backend": spectrum_data.get_backend(),
            "channel_range": [config.channel.start_channel, config.channel.end_channel],
            "measurement_window": config.scan.measurement_window,
            "sampling_interval": config.scan.sampling_interval,
            "thresholds": {
                "clear_max": config.thresholds.clear_max,
                "moderate_max": config.thresholds.moderate_max,
                "busy_max": config.thresholds.busy_max,
                "heavy_min": config.thresholds.heavy_min,
            },
        },
        "scan_count": spectrum_data.get_scan_count(),
        "observations": data,
    }
    json.dump(result, output, separators=(",", ":"))
    output.write("\n")
    output.flush()


def export_csv(spectrum_data: SpectrumData, config: AppConfig, output: TextIO) -> None:
    """Export observations as CSV."""
    observations = spectrum_data.export_all()
    if not observations:
        return
    
    fieldnames = [
        "timestamp", "channel", "frequency_mhz", "backend",
        "valid_samples", "rpd_positive", "rpd_negative",
        "activity_percentage", "status", "data_sufficient",
        "measurement_window", "sampling_interval", "error",
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for obs in observations:
        writer.writerow(obs)
    output.flush()


def export_files(spectrum_data: SpectrumData, config: AppConfig) -> None:
    """Export to files in export directory."""
    Path(config.storage.export_dir).mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backend = spectrum_data.get_backend()
    
    json_path = Path(config.storage.export_dir) / f"scan_{backend}_{timestamp}.json"
    with open(json_path, "w") as f:
        export_json(spectrum_data, config, f)
    print(f"Exported JSON: {json_path}")
    
    csv_path = Path(config.storage.export_dir) / f"scan_{backend}_{timestamp}.csv"
    with open(csv_path, "w", newline="") as f:
        export_csv(spectrum_data, config, f)
    print(f"Exported CSV: {csv_path}")


def run_diagnostic() -> int:
    """Run hardware diagnostic."""
    print("RF Spectrum Visualizer - Hardware Diagnostic")
    print("=" * 50)
    
    result = check_hardware_availability()
    
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="2.4 GHz RF Spectrum Visualizer - CLI Scanner",
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
        "--persistent-threshold", type=float, default=75.0,
        help="Persistent activity threshold"
    )
    parser.add_argument(
        "--persistence-duration", type=float, default=10.0,
        help="Persistence duration (seconds)"
    )
    parser.add_argument(
        "--consecutive-windows", type=int, default=3,
        help="Consecutive windows for persistent detection"
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
        "--mitigate", action="store_true",
        help="Enable mitigation alerts (ARMED mode)"
    )
    parser.add_argument(
        "--format", choices=["table", "ascii", "json", "csv"], default="table",
        help="Output format"
    )
    parser.add_argument(
        "--sort", choices=["channel", "activity", "status"], default="channel",
        help="Sort order (table format only)"
    )
    parser.add_argument(
        "--log-path", default="logs/countermeasures.jsonl",
        help="Log file path"
    )
    parser.add_argument(
        "--export-dir", default="exports",
        help="Export directory"
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=0,
        help="Increase verbosity"
    )
    parser.add_argument(
        "--diagnostic", action="store_true",
        help="Run hardware diagnostic and exit"
    )
    
    args = parser.parse_args()
    
    log_level = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
    
    setup_logging(log_path=args.log_path, level=log_level)
    
    if args.diagnostic:
        return run_diagnostic()
    
    config = create_config_from_args(args)
    
    return run_cli_scan(config, args.format, args.sort)


if __name__ == "__main__":
    sys.exit(main())