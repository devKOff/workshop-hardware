"""Command-line interface for RF Spectrum Visualizer v6."""

import argparse
import sys
import time
import json
import signal
import logging
from typing import Optional, List, TextIO
from pathlib import Path

from .config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, BlocklistConfig, StorageConfig, SimConfig, HardwareConfig
from .scanner import ScannerThread, SpectrumData, ChannelObservation
from .sim_radio import SimRadio, ScenarioType
from .hardware_radio import HardwareRadio, check_hardware_availability, run_hardware_diagnostic
from .blocklist_manager import BlocklistManager
from .channel_selector import ChannelSelector
from .report_generator import ReportGenerator
from .channel_utils import validate_channel, parse_channel_input, format_channel
from .exceptions import (
    RFSystemError,
    HardwareError,
    ScannerError,
    InvalidChannelError,
    BlocklistError,
)
from .logging_config import setup_logging, get_logger

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
        lines.append("=" * 70)
        lines.append("         2.4 GHz RF SPECTRUM VISUALIZER v6 - CLI SCANNER")
        lines.append("=" * 70)
        lines.append(f"Backend: {backend.upper()}")
        lines.append("Measurement: Repeated nRF24L01+ RPD observations")
        lines.append(f"Scan range: Channels {self._config.channel.start_channel}-{self._config.channel.end_channel}")
        lines.append(f"Window: {self._config.scan.measurement_window:.1f}s per channel, "
                     f"Interval: {self._config.scan.sampling_interval*1000:.0f}ms")
        lines.append(f"Scans completed: {scan_count}")
        lines.append(f"Status: {'SCANNING' if scan_count == 0 else 'UPDATING'}")
        lines.append("-" * 70)
        return lines
    
    def render_channel(self, obs: ChannelObservation, blocked: bool = False) -> str:
        ch = obs.channel
        freq = obs.frequency_mhz
        
        blocked_marker = " [BLOCKED]" if blocked else ""
        
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
        
        return f"Ch {ch:3d} ({freq:4d} MHz) {bar} {pct_str:>5} ({status}){data_flag}{error_flag}{blocked_marker}"
    
    def render_footer(self, channel_count: int) -> List[str]:
        lines = []
        lines.append("-" * 70)
        lines.append(f"Channels scanned: {channel_count}")
        lines.append(f"Results: {'Complete' if channel_count > 0 else 'Pending'}")
        lines.append("=" * 70)
        return lines
    
    def update(self, spectrum_data: SpectrumData, backend: str, scan_count: int, blocklist: BlocklistManager) -> None:
        """Update the display with current data."""
        channels = spectrum_data.get_channels_in_range()
        observations = spectrum_data.get_all_observations()
        
        lines = self.render_header(backend, scan_count)
        
        for ch in channels:
            obs = observations.get(ch)
            blocked = blocklist.is_blocked(ch)
            if obs:
                lines.append(self.render_channel(obs, blocked))
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
    
    blocklist_config = BlocklistConfig(
        file_path=args.blocklist_file,
    )
    
    storage_config = StorageConfig(
        log_path=args.log_path,
        export_dir=args.export_dir,
    )
    
    sim_config = SimConfig(
        seed=args.seed,
        deterministic=not args.no_deterministic,
    )
    
    hardware_config = HardwareConfig(
        ce_pin=args.ce_pin,
        csn_pin=args.csn_pin,
    )
    
    return AppConfig(
        channel=channel_config,
        scan=scan_config,
        thresholds=thresholds,
        blocklist=blocklist_config,
        storage=storage_config,
        sim=sim_config,
        hardware=hardware_config,
        default_backend=args.backend,
    )


def run_scan_mode(config: AppConfig, args: argparse.Namespace) -> int:
    """Run continuous scan mode."""
    display = CLIDisplay(config, use_ascii=args.format == "ascii")
    spectrum_data = SpectrumData(config)
    blocklist = BlocklistManager(config.blocklist)
    channel_selector = ChannelSelector(config.channel, config.thresholds, blocklist)
    
    if config.default_backend == "hardware":
        radio = HardwareRadio(config.channel, config.scan, config.hardware)
        if not radio.is_available():
            print("ERROR: Hardware backend not available (pyrf24 not installed or SPI unavailable)", file=sys.stderr)
            return 1
        try:
            radio.initialize()
        except HardwareError as e:
            print(f"ERROR: Failed to initialize hardware: {e}", file=sys.stderr)
            return 1
    else:
        radio = SimRadio(config.channel, config.scan, config.sim, scenario=ScenarioType(args.scenario))
        radio.initialize()
    
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
            
            if args.format in ("table", "ascii"):
                display.update(spectrum_data, config.default_backend, spectrum_data.get_scan_count(), blocklist)
            
            current_time = time.time()
            if args.format == "json" and current_time - last_export_time >= export_interval:
                report_gen = ReportGenerator(config, spectrum_data, blocklist, channel_selector)
                report_gen.export_json(sys.stdout)
                last_export_time = current_time
    
    except KeyboardInterrupt:
        pass
    finally:
        scanner.shutdown()
        
        if args.format in ("table", "ascii"):
            print()
        
        if args.format == "json":
            report_gen = ReportGenerator(config, spectrum_data, blocklist, channel_selector)
            report_gen.export_json(sys.stdout)
        elif args.format == "csv":
            report_gen = ReportGenerator(config, spectrum_data, blocklist, channel_selector)
            report_gen.export_csv(sys.stdout)
    
    return 0


def run_single_scan(config: AppConfig, args: argparse.Namespace) -> int:
    """Run a single scan pass and exit."""
    spectrum_data = SpectrumData(config)
    blocklist = BlocklistManager(config.blocklist)
    channel_selector = ChannelSelector(config.channel, config.thresholds, blocklist)
    
    if config.default_backend == "hardware":
        radio = HardwareRadio(config.channel, config.scan, config.hardware)
        if not radio.is_available():
            print("ERROR: Hardware backend not available", file=sys.stderr)
            return 1
        radio.initialize()
    else:
        radio = SimRadio(config.channel, config.scan, config.sim, scenario=ScenarioType(args.scenario))
        radio.initialize()
    
    print(f"Scanning channels {config.channel.start_channel}-{config.channel.end_channel}...")
    
    for channel in config.channel.channel_range():
        try:
            valid, positive, negative = radio.scan_channel(
                channel,
                config.scan.measurement_window,
                config.scan.sampling_interval,
            )
            
            if valid >= config.scan.min_valid_samples:
                activity = (positive / valid) * 100.0
                data_sufficient = True
                error = None
            else:
                activity = None
                data_sufficient = False
                error = f"Insufficient samples: {valid}/{config.scan.min_valid_samples}"
            
            status = config.thresholds.classify(activity)
            if not data_sufficient:
                status = "INSUFFICIENT DATA"
            
            blocked = blocklist.is_blocked(channel)
            
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=channel,
                frequency_mhz=2400 + channel,
                backend=config.default_backend,
                valid_samples=valid,
                rpd_positive=positive,
                rpd_negative=negative,
                activity_percentage=activity,
                status=status,
                data_sufficient=data_sufficient,
                measurement_window=config.scan.measurement_window,
                sampling_interval=config.scan.sampling_interval,
                error=error,
            )
            
            spectrum_data.update_observation(obs)
            
        except Exception as e:
            logger.error(f"Error scanning channel {channel}: {e}")
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=channel,
                frequency_mhz=2400 + channel,
                backend=config.default_backend,
                valid_samples=0,
                rpd_positive=0,
                rpd_negative=0,
                activity_percentage=None,
                status="SENSOR_ERROR",
                data_sufficient=False,
                measurement_window=config.scan.measurement_window,
                sampling_interval=config.scan.sampling_interval,
                error=str(e),
            )
            spectrum_data.update_observation(obs)
    
    radio.cleanup()
    
    display = CLIDisplay(config, use_ascii=args.format == "ascii")
    display.update(spectrum_data, config.default_backend, 1, blocklist)
    
    if args.format == "json":
        report_gen = ReportGenerator(config, spectrum_data, blocklist, channel_selector)
        report_gen.export_json(sys.stdout)
    elif args.format == "csv":
        report_gen = ReportGenerator(config, spectrum_data, blocklist, channel_selector)
        report_gen.export_csv(sys.stdout)
    
    return 0


def cmd_block(args: argparse.Namespace, config: AppConfig) -> int:
    """Block a channel."""
    try:
        channel = parse_channel_input(args.channel)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    
    blocklist = BlocklistManager(config.blocklist)
    
    try:
        entry = blocklist.block_channel(channel, args.reason)
        print(f"Blocked {format_channel(channel)} - {entry.reason}")
        return 0
    except (InvalidChannelError, BlocklistError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def cmd_unblock(args: argparse.Namespace, config: AppConfig) -> int:
    """Unblock a channel."""
    try:
        channel = parse_channel_input(args.channel)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    
    blocklist = BlocklistManager(config.blocklist)
    
    try:
        if blocklist.unblock_channel(channel):
            print(f"Unblocked {format_channel(channel)}")
        else:
            print(f"{format_channel(channel)} was not blocked")
        return 0
    except (InvalidChannelError, BlocklistError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def cmd_blocklist(args: argparse.Namespace, config: AppConfig) -> int:
    """Show blocklist."""
    blocklist = BlocklistManager(config.blocklist)
    entries = blocklist.get_blocked_entries()
    
    if not entries:
        print("Blocklist is empty")
        return 0
    
    print("BLOCKED CHANNELS:")
    print("-" * 60)
    for entry in entries:
        print(f"  {format_channel(entry.channel)}  Blocked: {entry.blocked_at}  Reason: {entry.reason}")
    
    print(f"\nTotal: {len(entries)} channels blocked")
    return 0


def cmd_channel(args: argparse.Namespace, config: AppConfig) -> int:
    """Check a specific channel."""
    try:
        channel = parse_channel_input(args.channel)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    
    blocklist = BlocklistManager(config.blocklist)
    blocked = blocklist.is_blocked(channel)
    entry = blocklist.get_entry(channel)
    
    print(f"Channel: {format_channel(channel)}")
    print(f"Blocked: {'YES' if blocked else 'NO'}")
    if entry:
        print(f"Blocked at: {entry.blocked_at}")
        print(f"Reason: {entry.reason}")
    
    return 0


def cmd_channels(args: argparse.Namespace, config: AppConfig) -> int:
    """List all channels with block status."""
    blocklist = BlocklistManager(config.blocklist)
    
    print("ALL CHANNELS (0-125):")
    print("-" * 60)
    for ch in range(126):
        blocked = blocklist.is_blocked(ch)
        marker = " [BLOCKED]" if blocked else ""
        print(f"  {format_channel(ch)}{marker}")
    
    return 0


def cmd_recommend(args: argparse.Namespace, config: AppConfig) -> int:
    """Get channel recommendations."""
    spectrum_data = SpectrumData(config)
    blocklist = BlocklistManager(config.blocklist)
    channel_selector = ChannelSelector(config.channel, config.thresholds, blocklist)
    
    if config.default_backend == "hardware":
        radio = HardwareRadio(config.channel, config.scan, config.hardware)
        if not radio.is_available():
            print("ERROR: Hardware backend not available", file=sys.stderr)
            return 1
        radio.initialize()
    else:
        radio = SimRadio(config.channel, config.scan, config.sim, scenario=ScenarioType(args.scenario))
        radio.initialize()
    
    print("Scanning for recommendations...")
    for channel in config.channel.channel_range():
        try:
            valid, positive, negative = radio.scan_channel(
                channel,
                config.scan.measurement_window,
                config.scan.sampling_interval,
            )
            
            if valid >= config.scan.min_valid_samples:
                activity = (positive / valid) * 100.0
                data_sufficient = True
            else:
                activity = None
                data_sufficient = False
            
            status = config.thresholds.classify(activity)
            if not data_sufficient:
                status = "INSUFFICIENT DATA"
            
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=channel,
                frequency_mhz=2400 + channel,
                backend=config.default_backend,
                valid_samples=valid,
                rpd_positive=positive,
                rpd_negative=negative,
                activity_percentage=activity,
                status=status,
                data_sufficient=data_sufficient,
                measurement_window=config.scan.measurement_window,
                sampling_interval=config.scan.sampling_interval,
                error=None,
            )
            spectrum_data.update_observation(obs)
        except Exception:
            pass
    
    radio.cleanup()
    
    recommendations = channel_selector.get_recommendations(
        spectrum_data.get_all_observations(),
        count=args.count
    )
    
    if not recommendations:
        print("NO ELIGIBLE CHANNELS - all channels blocked or have high activity")
        return 0
    
    print(f"TOP {len(recommendations)} RECOMMENDATIONS:")
    print("-" * 60)
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {format_channel(rec.channel)}  Activity: {rec.activity_percentage:.1f}%  Status: {rec.status}")
    
    return 0


def cmd_export(args: argparse.Namespace, config: AppConfig) -> int:
    """Export scan data."""
    spectrum_data = SpectrumData(config)
    blocklist = BlocklistManager(config.blocklist)
    channel_selector = ChannelSelector(config.channel, config.thresholds, blocklist)
    report_gen = ReportGenerator(config, spectrum_data, blocklist, channel_selector)
    
    if config.default_backend == "hardware":
        radio = HardwareRadio(config.channel, config.scan, config.hardware)
        if not radio.is_available():
            print("ERROR: Hardware backend not available", file=sys.stderr)
            return 1
        radio.initialize()
    else:
        radio = SimRadio(config.channel, config.scan, config.sim, scenario=ScenarioType(args.scenario))
        radio.initialize()
    
    print("Scanning...")
    for channel in config.channel.channel_range():
        try:
            valid, positive, negative = radio.scan_channel(
                channel,
                config.scan.measurement_window,
                config.scan.sampling_interval,
            )
            
            if valid >= config.scan.min_valid_samples:
                activity = (positive / valid) * 100.0
                data_sufficient = True
            else:
                activity = None
                data_sufficient = False
            
            status = config.thresholds.classify(activity)
            if not data_sufficient:
                status = "INSUFFICIENT DATA"
            
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=channel,
                frequency_mhz=2400 + channel,
                backend=config.default_backend,
                valid_samples=valid,
                rpd_positive=positive,
                rpd_negative=negative,
                activity_percentage=activity,
                status=status,
                data_sufficient=data_sufficient,
                measurement_window=config.scan.measurement_window,
                sampling_interval=config.scan.sampling_interval,
                error=None,
            )
            spectrum_data.update_observation(obs)
        except Exception:
            pass
    
    radio.cleanup()
    
    if args.format == "json":
        if args.output:
            path = report_gen.export_json_file(args.output)
            print(f"Exported JSON: {path}")
        else:
            report_gen.export_json(sys.stdout)
    elif args.format == "csv":
        if args.output:
            path = report_gen.export_csv_file(args.output)
            print(f"Exported CSV: {path}")
        else:
            report_gen.export_csv(sys.stdout)
    elif args.format == "all":
        results = report_gen.export_all_formats(args.output)
        for fmt, path in results.items():
            print(f"Exported {fmt.upper()}: {path}")
    
    return 0


def cmd_diagnostic(args: argparse.Namespace) -> int:
    """Run hardware diagnostic."""
    print("RF Spectrum Visualizer v6 - Hardware Diagnostic")
    print("=" * 50)
    
    result = check_hardware_availability()
    
    print(f"Platform: {result['platform']}")
    print(f"pyrf24 installed: {result['pyrf24_installed']}")
    if result['pyrf24_version']:
        print(f"pyrf24 version: {result['pyrf24_version']}")
    
    print(f"SPI devices: {result['spi_devices'] or 'None found'}")
    print(f"GPIO access: {result['gpio_access']}")
    
    if result['errors']:
        print("\nErrors:")
        for err in result['errors']:
            print(f"  - {err}")
    
    if args.test_hardware and result['pyrf24_installed'] and result['spi_devices']:
        print("\nAttempting hardware initialization (read-only)...")
        try:
            config = AppConfig()
            success, msg = run_hardware_diagnostic()
            print(msg)
            return 0 if success else 1
        except Exception as e:
            print(f"Hardware test FAILED: {e}")
            return 1
    else:
        print("\nHardware test SKIPPED (missing dependencies or --test-hardware not specified)")
        return 0


def cmd_simulate(args: argparse.Namespace, config: AppConfig) -> int:
    """Run deterministic simulation scenario."""
    print(f"SIMULATION MODE - Scenario: {args.scenario}")
    print("=" * 50)
    
    radio = SimRadio(config.channel, config.scan, config.sim, scenario=ScenarioType(args.scenario))
    radio.initialize()
    
    print(f"Seed: {config.sim.seed}")
    print(f"Deterministic: {config.sim.deterministic}")
    print()
    
    for channel in config.channel.channel_range():
        valid, positive, negative = radio.scan_channel(
            channel,
            config.scan.measurement_window,
            config.scan.sampling_interval,
        )
        
        if valid >= config.scan.min_valid_samples:
            activity = (positive / valid) * 100.0
        else:
            activity = None
        
        status = config.thresholds.classify(activity)
        if activity is None:
            status = "INSUFFICIENT DATA"
        
        bar_width = 30
        if activity is not None:
            filled = int(activity / 100 * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            pct_str = f"{activity:.1f}%"
        else:
            bar = "?" * bar_width
            pct_str = "N/A"
        
        print(f"Ch {channel:3d} ({2400+channel:4d} MHz) [{bar}] {pct_str:>6} ({status})")
    
    radio.cleanup()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RF Spectrum Visualizer v6 - nRF24L01+ RF Spectrum Analyzer",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Global arguments
    parser.add_argument("--backend", choices=["sim", "hardware"], default="sim", help="Backend to use")
    parser.add_argument("--start-channel", type=int, default=0, help="Start channel (0-125)")
    parser.add_argument("--end-channel", type=int, default=125, help="End channel (0-125)")
    parser.add_argument("--window", type=float, default=1.0, help="Measurement window per channel (seconds)")
    parser.add_argument("--interval", type=float, default=0.01, help="Sampling interval (seconds)")
    parser.add_argument("--min-samples", type=int, default=10, help="Minimum valid samples")
    parser.add_argument("--clear-max", type=int, default=24, help="Clear status max percentage")
    parser.add_argument("--moderate-max", type=int, default=49, help="Moderate status max percentage")
    parser.add_argument("--busy-max", type=int, default=74, help="Busy status max percentage")
    parser.add_argument("--heavy-min", type=int, default=75, help="Heavy load status min percentage")
    parser.add_argument("--persistent-threshold", type=float, default=75.0, help="Persistent activity threshold")
    parser.add_argument("--hysteresis", type=float, default=5.0, help="Hysteresis for alert clearing")
    parser.add_argument("--blocklist-file", default="v6/blocklist.json", help="Blocklist JSON file path")
    parser.add_argument("--log-path", default="v6/logs/countermeasures.jsonl", help="Log file path")
    parser.add_argument("--export-dir", default="v6/exports", help="Export directory")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for simulation")
    parser.add_argument("--no-deterministic", action="store_true", help="Disable deterministic simulation")
    parser.add_argument("--ce-pin", type=int, default=25, help="CE GPIO pin")
    parser.add_argument("--csn-pin", type=int, default=0, help="CSN SPI chip select (0 or 1)")
    parser.add_argument("--scenario", choices=[s.value for s in ScenarioType], default="mixed", help="Simulation scenario")
    parser.add_argument("--verbose", "-v", action="count", default=0, help="Increase verbosity")
    
    # scan command
    scan_parser = subparsers.add_parser("scan", help="Continuous scanning")
    scan_parser.add_argument("--format", choices=["table", "ascii", "json", "csv"], default="table", help="Output format")
    scan_parser.add_argument("--single", action="store_true", help="Single scan pass then exit")
    
    # block command
    block_parser = subparsers.add_parser("block", help="Block a channel")
    block_parser.add_argument("channel", help="Channel to block (e.g., 122, 'Ch 122', '2522 MHz')")
    block_parser.add_argument("--reason", default="User blocked", help="Reason for blocking")
    
    # unblock command
    unblock_parser = subparsers.add_parser("unblock", help="Unblock a channel")
    unblock_parser.add_argument("channel", help="Channel to unblock")
    
    # blocklist command
    subparsers.add_parser("blocklist", help="Show blocklist")
    
    # channel command
    channel_parser = subparsers.add_parser("channel", help="Check channel status")
    channel_parser.add_argument("channel", help="Channel to check")
    
    # channels command
    subparsers.add_parser("channels", help="List all channels")
    
    # recommend command
    recommend_parser = subparsers.add_parser("recommend", help="Get channel recommendations")
    recommend_parser.add_argument("--count", type=int, default=5, help="Number of recommendations")
    
    # export command
    export_parser = subparsers.add_parser("export", help="Export scan data")
    export_parser.add_argument("--format", choices=["json", "csv", "all"], default="json", help="Export format")
    export_parser.add_argument("--output", help="Output filename (without extension for 'all')")
    
    # diagnostic command
    diag_parser = subparsers.add_parser("diagnostic", help="Run hardware diagnostic")
    diag_parser.add_argument("--test-hardware", action="store_true", help="Test actual hardware init")
    
    # simulate command
    sim_parser = subparsers.add_parser("simulate", help="Run deterministic simulation scenario")
    
    # help
    subparsers.add_parser("help", help="Show help")
    
    args = parser.parse_args()
    
    log_level = logging.WARNING
    if args.verbose == 1:
        log_level = logging.INFO
    elif args.verbose >= 2:
        log_level = logging.DEBUG
    
    setup_logging(log_path=args.log_path, level=log_level)
    
    if args.command is None or args.command == "help":
        parser.print_help()
        return 0
    
    config = create_config_from_args(args)
    
    command_map = {
        "scan": lambda: run_scan_mode(config, args) if not args.single else run_single_scan(config, args),
        "block": lambda: cmd_block(args, config),
        "unblock": lambda: cmd_unblock(args, config),
        "blocklist": lambda: cmd_blocklist(args, config),
        "channel": lambda: cmd_channel(args, config),
        "channels": lambda: cmd_channels(args, config),
        "recommend": lambda: cmd_recommend(args, config),
        "export": lambda: cmd_export(args, config),
        "diagnostic": lambda: cmd_diagnostic(args),
        "simulate": lambda: cmd_simulate(args, config),
        "help": lambda: (parser.print_help(), 0)[1],
    }
    
    if args.command not in command_map:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1
    
    try:
        return command_map[args.command]()
    except RFSystemError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if args.verbose >= 2:
            import traceback
            traceback.print_exc()
        return 1
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}", file=sys.stderr)
        if args.verbose >= 1:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
