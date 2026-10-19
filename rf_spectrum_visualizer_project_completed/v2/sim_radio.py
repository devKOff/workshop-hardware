"""Simulation radio with realistic 2.4 GHz ISM traffic patterns."""
import time
import random
import threading
import math
from typing import List, Optional, Dict
from dataclasses import dataclass, field

from config import RadioConfig
from hardware_radio import RadioInterface


@dataclass
class SignalSource:
    """Simulated RF signal source."""
    center_channel: int
    bandwidth: int
    power_db: float
    signal_type: str
    hop_pattern: Optional[List[int]] = None
    hop_index: int = 0
    last_hop_time: float = 0
    hop_interval: float = 0.001
    active: bool = True


class SimRadio(RadioInterface):
    """Mock radio simulating realistic 2.4 GHz ISM band traffic."""
    
    def __init__(self, config: Optional[RadioConfig] = None):
        self._config = config or RadioConfig()
        self._lock = threading.RLock()
        self._sources: List[SignalSource] = []
        self._noise_floor_db = -95.0
        self._initialized = False
        self._current_channel = 0
        self._setup_default_sources()
    
    def _setup_default_sources(self):
        """Configure default Wi-Fi and Bluetooth-like sources."""
        # Wi-Fi channels (1, 6, 11) - 22 MHz bandwidth
        wifi_config = [
            (1, -40.0), (6, -42.0), (11, -38.0)
        ]
        for ch, power in wifi_config:
            self._sources.append(SignalSource(
                center_channel=ch,
                bandwidth=22,
                power_db=power + random.uniform(-3, 3),
                signal_type="wifi",
            ))
        
        # Bluetooth-like frequency hopping (79 channels, 1 MHz each)
        bt_channels = list(range(0, 79))
        self._sources.append(SignalSource(
            center_channel=random.choice(bt_channels),
            bandwidth=1,
            power_db=-55.0 + random.uniform(-8, 8),
            signal_type="bluetooth",
            hop_pattern=bt_channels,
            hop_interval=0.000625,  # 625 µs per hop
        ))
        
        # Random interference sources
        for _ in range(3):
            self._sources.append(SignalSource(
                center_channel=random.randint(0, 125),
                bandwidth=random.randint(1, 5),
                power_db=-70.0 + random.uniform(-10, 10),
                signal_type="interference",
            ))
    
    def initialize(self) -> bool:
        with self._lock:
            self._initialized = True
            return True
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    def set_channel(self, channel: int) -> bool:
        if not (0 <= channel <= 125):
            return False
        with self._lock:
            self._current_channel = channel
        time.sleep(0.00013)
        return True
    
    def _calculate_signal_at_channel(self, channel: int) -> float:
        """Calculate combined signal power at a specific channel."""
        total_power_mw = 0.0
        current_time = time.monotonic()
        
        with self._lock:
            sources = list(self._sources)
        
        for source in sources:
            if not source.active:
                continue
            
            # Handle frequency hopping
            if source.signal_type == "bluetooth" and source.hop_pattern:
                if current_time - source.last_hop_time >= source.hop_interval:
                    source.hop_index = (source.hop_index + 1) % len(source.hop_pattern)
                    source.center_channel = source.hop_pattern[source.hop_index]
                    source.last_hop_time = current_time
            
            # Calculate signal contribution at this channel
            offset = abs(channel - source.center_channel)
            if offset <= source.bandwidth // 2:
                # Triangular attenuation
                attenuation = 1.0 - (offset / (source.bandwidth / 2)) * 0.5
                power_mw = 10 ** (source.power_db / 10) * attenuation
                total_power_mw += power_mw
        
        # Add noise floor with small variation
        noise_mw = 10 ** (self._noise_floor_db / 10)
        total_power_mw += noise_mw * random.uniform(0.85, 1.15)
        
        return 10 * math.log10(total_power_mw) if total_power_mw > 0 else self._noise_floor_db
    
    def get_rpd_value(self, channel: int) -> int:
        """Get simulated RPD value (0-255)."""
        self.set_channel(channel)
        power_db = self._calculate_signal_at_channel(channel)
        normalized = max(0.0, min(1.0, (power_db + 100) / 60.0))
        return int(normalized * 255)
    
    def get_rpd_db(self, channel: int) -> float:
        """Get signal strength in dBm."""
        self.set_channel(channel)
        return self._calculate_signal_at_channel(channel)
    
    def test_carrier(self, channel: int) -> bool:
        return self.get_rpd_db(channel) > -70.0
    
    def test_rpd(self, channel: int) -> bool:
        return self.test_carrier(channel)
    
    def transmit_carrier(self, channel: int, duration_ms: int = 100) -> bool:
        if not self._initialized:
            return False
        time.sleep(duration_ms / 1000.0)
        return True
    
    def transmit_noise(self, channel: int, packets: int = 100) -> bool:
        if not self._initialized:
            return False
        time.sleep(packets * 0.0001)
        return True
    
    def cleanup(self):
        self._initialized = False
    
    # Simulation control methods
    
    def add_source(self, source: SignalSource):
        with self._lock:
            self._sources.append(source)
    
    def remove_source(self, index: int) -> bool:
        with self._lock:
            if 0 <= index < len(self._sources):
                self._sources.pop(index)
                return True
            return False
    
    def get_sources(self) -> List[SignalSource]:
        with self._lock:
            return list(self._sources)
    
    def set_noise_floor(self, db: float):
        with self._lock:
            self._noise_floor_db = max(-120.0, min(-50.0, db))
    
    def enable_source(self, index: int, enabled: bool) -> bool:
        with self._lock:
            if 0 <= index < len(self._sources):
                self._sources[index].active = enabled
                return True
            return False
    
    def __enter__(self):
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False