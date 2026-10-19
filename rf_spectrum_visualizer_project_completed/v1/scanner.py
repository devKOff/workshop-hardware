import time
import threading
import numpy as np
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class SpectrumData:
    """Thread-safe container for spectrum analysis data."""
    num_channels: int = 126
    waterfall_depth: int = 200
    
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)
    _current_sweep: np.ndarray = field(default_factory=lambda: np.zeros(126, dtype=np.float32), init=False)
    _peak_hold: np.ndarray = field(default_factory=lambda: np.zeros(126, dtype=np.float32), init=False)
    _rolling_avg: np.ndarray = field(default_factory=lambda: np.zeros(126, dtype=np.float32), init=False)
    _waterfall: deque = field(default_factory=lambda: deque(maxlen=200), init=False)
    _sweep_count: int = field(default=0, init=False)
    _last_sweep_time: float = field(default=0.0, init=False)
    _sweeps_per_sec: float = field(default=0.0, init=False)
    _alpha: float = field(default=0.1, init=False)
    _peak_decay: float = field(default=0.995, init=False)
    
    def __post_init__(self):
        self._waterfall = deque(maxlen=self.waterfall_depth)
        for _ in range(self.waterfall_depth):
            self._waterfall.append(np.zeros(self.num_channels, dtype=np.float32))
    
    def update_sweep(self, sweep_data: np.ndarray):
        """Update with new sweep data, compute rolling avg and peak hold."""
        if sweep_data.shape != (self.num_channels,):
            logger.warning(f"Invalid sweep shape: {sweep_data.shape}")
            return
            
        with self._lock:
            current_time = time.monotonic()
            
            self._rolling_avg = (1 - self._alpha) * self._rolling_avg + self._alpha * sweep_data
            
            self._peak_hold = np.maximum(self._peak_hold * self._peak_decay, sweep_data)
            
            self._current_sweep[:] = sweep_data
            self._waterfall.append(sweep_data.copy())
            
            self._sweep_count += 1
            if self._last_sweep_time > 0:
                dt = current_time - self._last_sweep_time
                if dt > 0:
                    self._sweeps_per_sec = 0.9 * self._sweeps_per_sec + 0.1 * (1.0 / dt)
            self._last_sweep_time = current_time
    
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
            if len(self._waterfall) == 0:
                return np.zeros((self.waterfall_depth, self.num_channels), dtype=np.float32)
            return np.array(list(self._waterfall), dtype=np.float32)
    
    def get_sweeps_per_sec(self) -> float:
        with self._lock:
            return self._sweeps_per_sec
    
    def get_sweep_count(self) -> int:
        with self._lock:
            return self._sweep_count
    
    def reset_peak_hold(self):
        with self._lock:
            self._peak_hold.fill(0)
    
    def set_peak_decay(self, decay: float):
        with self._lock:
            self._peak_decay = max(0.9, min(0.999, decay))
    
    def set_rolling_alpha(self, alpha: float):
        with self._lock:
            self._alpha = max(0.01, min(0.5, alpha))


class ScannerThread(threading.Thread):
    """High-speed background scanner sweeping all 126 channels."""
    
    def __init__(
        self,
        radio,
        spectrum_data: SpectrumData,
        channel_order: Optional[List[int]] = None,
        dwell_time_us: int = 130,
        callback: Optional[Callable[[np.ndarray], None]] = None
    ):
        super().__init__(daemon=True)
        self.radio = radio
        self.spectrum_data = spectrum_data
        self.dwell_time_us = dwell_time_us
        self.callback = callback
        self._running = threading.Event()
        self._paused = threading.Event()
        self._channel_order = channel_order or list(range(126))
        self._lock = threading.Lock()
        
    def run(self):
        """Main scanning loop."""
        self._running.set()
        self._paused.clear()
        sweep_buffer = np.zeros(126, dtype=np.float32)
        
        while self._running.is_set():
            if self._paused.is_set():
                time.sleep(0.01)
                continue
                
            sweep_start = time.monotonic()
            
            for idx, channel in enumerate(self._channel_order):
                if not self._running.is_set() or self._paused.is_set():
                    break
                    
                rpd_val = self.radio.get_rpd_value(channel)
                power_db = (rpd_val / 255.0) * 60.0 - 100.0
                sweep_buffer[idx] = power_db
                
                if self.dwell_time_us > 0:
                    time.sleep(self.dwell_time_us / 1_000_000.0)
            
            self.spectrum_data.update_sweep(sweep_buffer)
            
            if self.callback:
                try:
                    self.callback(sweep_buffer.copy())
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            
            elapsed = time.monotonic() - sweep_start
            target_sweep_time = 126 * (self.dwell_time_us / 1_000_000.0)
            if elapsed < target_sweep_time:
                time.sleep(target_sweep_time - elapsed)
    
    def stop(self):
        """Stop the scanner thread."""
        self._running.clear()
        self.join(timeout=2.0)
    
    def pause(self):
        """Pause scanning."""
        self._paused.set()
    
    def resume(self):
        """Resume scanning."""
        self._paused.clear()
    
    def set_channel_order(self, order: List[int]):
        """Change channel scanning order."""
        with self._lock:
            if len(order) == 126 and set(order) == set(range(126)):
                self._channel_order = order
    
    def set_dwell_time(self, dwell_us: int):
        """Update dwell time per channel."""
        with self._lock:
            self.dwell_time_us = max(10, min(10000, dwell_us))
    
    def is_running(self) -> bool:
        return self._running.is_set()
    
    def is_paused(self) -> bool:
        return self._paused.is_set()