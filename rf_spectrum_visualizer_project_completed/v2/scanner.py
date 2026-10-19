"""Thread-safe spectrum data container and high-speed scanner thread."""
import time
import threading
import numpy as np
from typing import Optional, Callable, List, Deque
from dataclasses import dataclass, field
from collections import deque

from config import ScannerConfig, RadioConfig
from hardware_radio import RadioInterface, HardwareRadio, RadioFactory

logger = logging.getLogger(__name__)


@dataclass
class SpectrumData:
    """Thread-safe container for spectrum analysis data."""
    config: ScannerConfig = field(default_factory=ScannerConfig)
    
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)
    _current_sweep: np.ndarray = field(init=False)
    _peak_hold: np.ndarray = field(init=False)
    _rolling_avg: np.ndarray = field(init=False)
    _waterfall: Deque[np.ndarray] = field(init=False)
    _sweep_count: int = field(default=0, init=False)
    _last_sweep_time: float = field(default=0.0, init=False)
    _sweeps_per_sec: float = field(default=0.0, init=False)
    _callbacks: List[Callable[[np.ndarray], None]] = field(default_factory=list, init=False)
    
    def __post_init__(self):
        n = self.config.num_channels
        self._current_sweep = np.full(n, -100.0, dtype=np.float32)
        self._peak_hold = np.full(n, -100.0, dtype=np.float32)
        self._rolling_avg = np.full(n, -100.0, dtype=np.float32)
        self._waterfall = deque(maxlen=self.config.waterfall_depth)
        for _ in range(self.config.waterfall_depth):
            self._waterfall.append(np.full(n, -100.0, dtype=np.float32))
    
    def register_callback(self, callback: Callable[[np.ndarray], None]):
        """Register a callback for sweep updates."""
        with self._lock:
            self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[np.ndarray], None]):
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def update_sweep(self, sweep_data: np.ndarray):
        """Update with new sweep data, compute rolling avg and peak hold."""
        if sweep_data.shape != (self.config.num_channels,):
            logger.warning(f"Invalid sweep shape: {sweep_data.shape}")
            return
        
        current_time = time.monotonic()
        
        with self._lock:
            # Exponential moving average
            alpha = self.config.rolling_alpha
            self._rolling_avg = (1 - alpha) * self._rolling_avg + alpha * sweep_data
            
            # Peak hold with decay
            decay = self.config.peak_decay
            self._peak_hold = np.maximum(self._peak_hold * decay, sweep_data)
            
            # Current sweep
            self._current_sweep[:] = sweep_data
            
            # Waterfall history
            self._waterfall.append(sweep_data.copy())
            
            # Sweep rate calculation
            self._sweep_count += 1
            if self._last_sweep_time > 0:
                dt = current_time - self._last_sweep_time
                if dt > 0:
                    inst_rate = 1.0 / dt
                    self._sweeps_per_sec = 0.9 * self._sweeps_per_sec + 0.1 * inst_rate
            self._last_sweep_time = current_time
            
            # Notify callbacks
            sweep_copy = sweep_data.copy()
            callbacks = list(self._callbacks)
        
        # Call callbacks outside lock
        for cb in callbacks:
            try:
                cb(sweep_copy)
            except Exception as e:
                logger.error(f"Sweep callback error: {e}")
    
    def get_current_sweep(self) -> np.ndarray:
        with self._lock:
            return self._current_sweep.copy()
    
    def get_peak_hold(self) -> np.ndarray:
        with self._lock:
            return self._peak_hold.copy()
    
    def get_rolling_avg(self) -> np.ndarray:
        with self._lock:
            return self._rolling_avg.copy()
    
    def get_waterfall(self) -> np.ndarray:
        with self._lock:
            if not self._waterfall:
                return np.zeros((self.config.waterfall_depth, self.config.num_channels), dtype=np.float32)
            return np.array(list(self._waterfall), dtype=np.float32)
    
    def get_sweeps_per_sec(self) -> float:
        with self._lock:
            return self._sweeps_per_sec
    
    def get_sweep_count(self) -> int:
        with self._lock:
            return self._sweep_count
    
    def reset_peak_hold(self):
        with self._lock:
            self._peak_hold.fill(-100.0)
    
    def set_peak_decay(self, decay: float):
        with self._lock:
            self.config.peak_decay = max(0.9, min(0.999, decay))
    
    def set_rolling_alpha(self, alpha: float):
        with self._lock:
            self.config.rolling_alpha = max(0.01, min(0.5, alpha))
    
    def get_stats(self) -> dict:
        with self._lock:
            return {
                "sweep_count": self._sweep_count,
                "sweeps_per_sec": self._sweeps_per_sec,
                "waterfall_depth": len(self._waterfall),
                "peak_decay": self.config.peak_decay,
                "rolling_alpha": self.config.rolling_alpha,
            }


class ScannerThread(threading.Thread):
    """High-speed background scanner sweeping all channels."""
    
    def __init__(
        self,
        radio: RadioInterface,
        spectrum_data: SpectrumData,
        radio_config: RadioConfig,
        channel_order: Optional[List[int]] = None,
        dwell_time_us: Optional[int] = None,
    ):
        super().__init__(daemon=True, name="RFScanner")
        self.radio = radio
        self.spectrum_data = spectrum_data
        self.radio_config = radio_config
        self._dwell_time_us = dwell_time_us or radio_config.dwell_time_us
        self._channel_order = channel_order or list(range(radio_config.channel_min, 
                                                            radio_config.channel_max + 1))
        self._running = threading.Event()
        self._paused = threading.Event()
        self._lock = threading.Lock()
        self._sweep_buffer = np.zeros(radio_config.channel_max - radio_config.channel_min + 1, 
                                       dtype=np.float32)
        self._error_count = 0
        self._max_errors = 100
    
    @property
    def dwell_time_us(self) -> int:
        with self._lock:
            return self._dwell_time_us
    
    @dwell_time_us.setter
    def dwell_time_us(self, value: int):
        with self._lock:
            self._dwell_time_us = max(10, min(10000, value))
    
    def run(self):
        """Main scanning loop."""
        self._running.set()
        self._paused.clear()
        self._error_count = 0
        
        while self._running.is_set():
            if self._paused.is_set():
                time.sleep(0.01)
                continue
            
            sweep_start = time.monotonic()
            sweep_success = True
            
            for idx, channel in enumerate(self._channel_order):
                if not self._running.is_set() or self._paused.is_set():
                    break
                
                try:
                    rpd_val = self.radio.get_rpd_value(channel)
                    power_db = (rpd_val / 255.0) * 60.0 - 100.0
                    self._sweep_buffer[idx] = power_db
                except Exception as e:
                    logger.debug(f"Channel {channel} read failed: {e}")
                    self._sweep_buffer[idx] = -100.0
                    sweep_success = False
                    self._error_count += 1
                
                dwell = self._dwell_time_us
                if dwell > 0:
                    time.sleep(dwell / 1_000_000.0)
            
            if sweep_success:
                self._error_count = 0
            elif self._error_count >= self._max_errors:
                logger.error("Too many consecutive scan errors, stopping")
                self._running.clear()
                break
            
            self.spectrum_data.update_sweep(self._sweep_buffer.copy())
            
            # Adaptive timing to maintain consistent sweep rate
            elapsed = time.monotonic() - sweep_start
            expected = len(self._channel_order) * (self._dwell_time_us / 1_000_000.0)
            if elapsed < expected:
                time.sleep(expected - elapsed)
    
    def stop(self, timeout: float = 2.0):
        """Stop the scanner thread."""
        self._running.clear()
        self.join(timeout=timeout)
    
    def pause(self):
        """Pause scanning."""
        self._paused.set()
    
    def resume(self):
        """Resume scanning."""
        self._paused.clear()
    
    def set_channel_order(self, order: List[int]):
        """Change channel scanning order."""
        with self._lock:
            expected = set(range(self.radio_config.channel_min, 
                                 self.radio_config.channel_max + 1))
            if set(order) == expected:
                self._channel_order = order
    
    def is_running(self) -> bool:
        return self._running.is_set()
    
    def is_paused(self) -> bool:
        return self._paused.is_set()


def create_scanner_system(
    force_hardware: bool = False,
    radio_config: Optional[RadioConfig] = None,
    scanner_config: Optional[ScannerConfig] = None,
) -> tuple[RadioInterface, SpectrumData, ScannerThread]:
    """Factory to create complete scanner system."""
    radio_config = radio_config or RadioConfig()
    scanner_config = scanner_config or ScannerConfig()
    
    # Create radio with fallback
    radio = RadioFactory.create_with_fallback(radio_config, force_hardware)
    
    # Create spectrum data
    spectrum_data = SpectrumData(scanner_config)
    
    # Create scanner thread
    scanner = ScannerThread(
        radio=radio,
        spectrum_data=spectrum_data,
        radio_config=radio_config,
    )
    
    return radio, spectrum_data, scanner