import time
import random
import threading
import math
from typing import List, Optional, Dict
from dataclasses import dataclass, field

from hardware_radio import HardwareRadio


@dataclass
class SignalSource:
    """Represents a simulated RF signal source."""
    center_channel: int
    bandwidth: int
    power_db: float
    signal_type: str
    hop_pattern: Optional[List[int]] = None
    hop_index: int = 0
    last_hop_time: float = 0
    hop_interval: float = 0.001


class SimRadio(HardwareRadio):
    """Mock radio simulating realistic 2.4 GHz ISM band traffic."""
    
    def __init__(self, ce_pin: int = 25, csn_pin: int = 8, spi_speed: int = 10_000_000):
        super().__init__(ce_pin, csn_pin, spi_speed)
        self._lock = threading.Lock()
        self._sources: List[SignalSource] = []
        self._noise_floor_db = -95.0
        self._initialized = False
        self._setup_default_sources()
        
    def _setup_default_sources(self):
        """Configure default Wi-Fi and Bluetooth-like sources."""
        wifi_channels = {
            1: 1,
            6: 6,
            11: 11,
        }
        
        for ch_num, channel in wifi_channels.items():
            self._sources.append(SignalSource(
                center_channel=channel,
                bandwidth=22,
                power_db=-40.0 + random.uniform(-5, 5),
                signal_type="wifi",
            ))
        
        bt_channels = list(range(0, 79))
        self._sources.append(SignalSource(
            center_channel=random.choice(bt_channels),
            bandwidth=1,
            power_db=-55.0 + random.uniform(-10, 10),
            signal_type="bluetooth",
            hop_pattern=bt_channels,
            hop_interval=0.000625,
        ))
        
        for _ in range(3):
            self._sources.append(SignalSource(
                center_channel=random.randint(0, 125),
                bandwidth=random.randint(1, 5),
                power_db=-70.0 + random.uniform(-15, 15),
                signal_type="interference",
            ))
    
    def initialize(self) -> bool:
        """Simulate hardware initialization."""
        with self._lock:
            self._initialized = True
            return True
    
    def set_channel(self, channel: int) -> bool:
        """Simulate channel switching with settling delay."""
        if not (0 <= channel <= 125):
            return False
        time.sleep(0.00013)
        return True
    
    def _calculate_signal_at_channel(self, channel: int) -> float:
        """Calculate combined signal power at a specific channel."""
        total_power_mw = 0.0
        current_time = time.monotonic()
        
        for source in self._sources:
            if source.signal_type == "bluetooth" and source.hop_pattern:
                if current_time - source.last_hop_time >= source.hop_interval:
                    source.hop_index = (source.hop_index + 1) % len(source.hop_pattern)
                    source.center_channel = source.hop_pattern[source.hop_index]
                    source.last_hop_time = current_time
            
            offset = abs(channel - source.center_channel)
            if offset <= source.bandwidth // 2:
                attenuation = 1.0 - (offset / (source.bandwidth / 2)) * 0.5
                power_mw = 10 ** (source.power_db / 10) * attenuation
                total_power_mw += power_mw
        
        noise_mw = 10 ** (self._noise_floor_db / 10)
        total_power_mw += noise_mw * random.uniform(0.8, 1.2)
        
        return 10 * math.log10(total_power_mw) if total_power_mw > 0 else self._noise_floor_db
    
    def test_carrier(self, channel: int) -> bool:
        """Simulate carrier detection based on signal strength."""
        if not self.set_channel(channel):
            return False
        power_db = self._calculate_signal_at_channel(channel)
        return power_db > -70.0
    
    def test_rpd(self, channel: int) -> bool:
        """Simulate RPD detection."""
        return self.test_carrier(channel)
    
    def get_rpd_value(self, channel: int) -> int:
        """Get simulated RPD value (0-255) from signal strength."""
        if not self.set_channel(channel):
            return 0
            
        power_db = self._calculate_signal_at_channel(channel)
        normalized = max(0, min(1, (power_db + 100) / 60))
        return int(normalized * 255)
    
    def transmit_carrier(self, channel: int, duration_ms: int = 100) -> bool:
        """Simulate carrier transmission."""
        if not self._initialized:
            return False
        time.sleep(duration_ms / 1000.0)
        return True
    
    def transmit_noise(self, channel: int, packets: int = 100) -> bool:
        """Simulate noise packet transmission."""
        if not self._initialized:
            return False
        time.sleep(packets * 0.0001)
        return True
    
    def add_source(self, source: SignalSource):
        """Add a custom signal source."""
        with self._lock:
            self._sources.append(source)
    
    def remove_source(self, index: int) -> bool:
        """Remove a signal source by index."""
        with self._lock:
            if 0 <= index < len(self._sources):
                self._sources.pop(index)
                return True
            return False
    
    def get_sources(self) -> List[SignalSource]:
        """Get list of active signal sources."""
        with self._lock:
            return list(self._sources)
    
    def cleanup(self):
        """Simulate cleanup."""
        self._initialized = False