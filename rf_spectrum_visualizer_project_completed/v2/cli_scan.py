"""Headless CLI spectrum scanner with Unicode bar graphs."""
import argparse
import sys
import time
import signal
import threading
from typing import Optional, List
import logging

from config import RadioConfig, CLIConfig
from hardware_radio import RadioFactory, RadioInterface
from scanner import SpectrumData, ScannerThread, create_scanner_system
from mitigation import MitigationEngine, MitigationConfig

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

BAR_CHARS = " ▁▂▃▄▅▆▇█"


class CLIScanner:
    """Headless terminal-based spectrum analyzer."""
    
    def __init__(
        self,
        radio: RadioInterface,
        spectrum_data: SpectrumData,
        scanner_thread: ScannerThread,
        cli_config: CLIConfig,
        threshold_db: float = -50.0,
        mitigate: bool = False,
        target_channels: Optional[List[int]] = None,
        mitigation_type: str = "carrier",
    ):
        self.radio = radio
        self.spectrum_data = spectrum_data
        self.scanner_thread = scanner_thread
        self.cli_config = cli_config
        self.threshold_db = threshold_db
        self.mitigate_enabled = mitigate
        self.target_channels = target_channels or []
        self.mitigation_type = mitigation_type
        
        self.mitigation_engine: Optional[MitigationEngine] = None
        self._running = threading.Event()
        self._last_render = 0.0
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.stop()
        sys.exit(0)
    
    def start(self):
        """Start scanning and mitigation."""
        self._running.set()
        self.scanner_thread.start()
        
        if self.mitigate_enabled and self.target_channels:
            mit_config = MitigationConfig(
                default_threshold_db=self.threshold_db,
                default_target_channels=self.target_channels,
                default_type=self.mitigation_type,
            )
            self.mitigation_engine = MitigationEngine(
                self.radio, self.spectrum_data, mit_config
            )
            self.mitigation_engine.arm()
            self.mitigation_engine.start_monitoring()
            print(f"Mitigation ARMED on channels {self.target_channels} "
                  f"(threshold: {self.threshold_db} dBm, type: {self.mitigation_type})",
                  file=sys.stderr)
        
        self._render_loop()
    
    def stop(self):
        """Stop scanning."""
        self._running.clear()
        self.scanner_thread.stop()
        if self.mitigation_engine:
            self.mitigation_engine.stop_monitoring()
        self.radio.cleanup()
        print("\nStopped.", file=sys.stderr)
    
    def _render_loop(self):
        """Main rendering loop."""
        try:
            while self._running.is_set():
                now = time.monotonic()
                if now - self._last_render >= self.cli_config.render_interval:
                    self._render_sweep()
                    self._last_render = now
                time.sleep(0.02)
        except KeyboardInterrupt:
            pass
    
    def _render_sweep(self):
        """Render one spectrum sweep as Unicode bars."""
        current = self.spectrum_data.get_current_sweep()
        peak = self.spectrum_data.get_peak_hold()
        sweeps_per_sec = self.spectrum_data.get_sweeps_per_sec()
        
        # Clear screen and home cursor
        sys.stdout.write("\033[2J\033[H")
        
        lines = []
        lines.append(f"2.4 GHz ISM Spectrum | {sweeps_per_sec:.1f} sweeps/s | "
                     f"Thresh: {self.threshold_db} dBm | "
                     f"{'MITIGATION ARMED' if self.mitigate_enabled else 'Mitigation OFF'}")
        lines.append("=" * 80)
        
        for ch in range(0, 126, 2):
            db_current = current[ch]
            db_peak = peak[ch]
            freq = 2400 + ch
            
            bar_current = self._db_to_bar(db_current)
            bar_peak = self._db_to_bar(db_peak)
            
            wifi_marker = ""
            if ch in [1, 6, 11]:
                wifi_marker = " ★WiFi"
            
            marker = " ▶" if ch in self.target_channels else ""
            mitigating = ""
            if self.mitigation_engine and self.mitigation_engine.last_mitigation_ms_ago >= 0:
                if self.mitigation_engine.last_mitigation_ms_ago < 1000:
                    if ch in self.target_channels:
                        mitigating = " ⚡MITIGATING"
            
            lines.append(
                f"Ch{ch:3d} ({freq:4d}MHz): {bar_current} {db_current:6.1f}  "
                f"Peak: {bar_peak} {db_peak:6.1f}{wifi_marker}{marker}{mitigating}"
            )
        
        if self.mitigation_engine:
            status = self.mitigation_engine.get_status()
            lines.append("-" * 80)
            lines.append(f"Mitigation: Armed={status['armed']} "
                         f"Last={status['last_mitigation_ms_ago']}ms ago "
                         f"Targets={status['target_channels']}")
        
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()
    
    def _db_to_bar(self, db: float) -> str:
        """Convert dBm value to Unicode bar graph."""
        cfg = self.cli_config
        if db <= cfg.db_min:
            return BAR_CHARS[0] * cfg.bar_width
        if db >= cfg.db_max:
            return BAR_CHARS[-1] * cfg.bar_width
        
        normalized = (db - cfg.db_min) / (cfg.db_max - cfg.db_min)
        idx = int(normalized * (len(BAR_CHARS) - 1))
        char = BAR_CHARS[idx]
        return char * cfg.bar_width


def parse_channels(arg: str) -> List[int]:
    """Parse comma-separated channel list with ranges."""
    channels = []
    for part in arg.split(","):
        part = part.strip()
        if "-" in part:
            start, end = map(int, part.split("-"))
            channels.extend(range(start, end + 1))
        else:
            channels.append(int(part))
    return [c for c in channels if 0 <= c <= 125]


def main():
    parser = argparse.ArgumentParser(
        description="2.4 GHz ISM Band Spectrum Analyzer v2 (CLI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --sim                          # Simulation mode
  %(prog)s --hw                           # Hardware mode
  %(prog)s --hw --mitigate -t 1,6,11 --threshold -45  # With mitigation
  %(prog)s --sim -t 0-125                 # Scan all channels
        """
    )
    
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--hw", action="store_true", help="Use hardware nRF24L01+")
    mode_group.add_argument("--sim", action="store_true", help="Use simulation mode")
    
    parser.add_argument("--mitigate", action="store_true", help="Enable active mitigation")
    parser.add_argument("-t", "--targets", type=str, default="1,6,11",
                        help="Target channels (comma-separated, ranges ok)")
    parser.add_argument("--threshold", type=float, default=-50.0,
                        help="Mitigation trigger threshold in dBm (default: -50)")
    parser.add_argument("--type", choices=["carrier", "noise"], default="carrier",
                        help="Mitigation type: carrier wave or packet noise")
    parser.add_argument("--dwell", type=int, default=130,
                        help="Dwell time per channel in microseconds (default: 130)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    
    target_channels = parse_channels(args.targets)
    
    # Configuration
    radio_config = RadioConfig(dwell_time_us=args.dwell)
    cli_config = CLIConfig()
    
    # Create system
    if args.hw:
        print("Initializing hardware nRF24L01+...", file=sys.stderr)
        radio, success = RadioFactory.create_hardware(radio_config)
        if not success:
            print(f"ERROR: {radio.last_error}", file=sys.stderr)
            sys.exit(1)
        print("Hardware ready.", file=sys.stderr)
    else:
        from sim_radio import SimRadio
        radio = SimRadio(radio_config)
        radio.initialize()
        print("Simulation mode active.", file=sys.stderr)
    
    # Create scanner system
    if args.hw:
        # For hardware, we need to create components separately
        spectrum_data = SpectrumData()
        scanner_thread = ScannerThread(radio, spectrum_data, radio_config, 
                                        dwell_time_us=args.dwell)
    else:
        # Use factory for simulation
        radio, spectrum_data, scanner_thread = create_scanner_system(
            force_hardware=False,
            radio_config=radio_config,
        )
    
    scanner = CLIScanner(
        radio=radio,
        spectrum_data=spectrum_data,
        scanner_thread=scanner_thread,
        cli_config=cli_config,
        threshold_db=args.threshold,
        mitigate=args.mitigate,
        target_channels=target_channels,
        mitigation_type=args.type,
    )
    
    print(f"Starting sweep (dwell: {args.dwell}µs)... Press Ctrl+C to stop", file=sys.stderr)
    if args.mitigate:
        print(f"Mitigation targets: {target_channels}", file=sys.stderr)
    
    try:
        scanner.start()
    except KeyboardInterrupt:
        pass
    finally:
        scanner.stop()


if __name__ == "__main__":
    main()