"""Simulation backend for RF Spectrum Visualizer."""

import random
import time
import threading
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from config import ChannelConfig, ScanConfig
from exceptions import SimulationError


class ChannelPattern(Enum):
    """Predefined channel activity patterns."""
    BACKGROUND = "background"
    LOW_ACTIVITY = "low_activity"
    HIGH_ACTIVITY = "high_activity"
    BURST = "burst"
    FREQUENCY_HOPPING = "frequency_hopping"
    WIFI_LIKE = "wifi_like"
    SENSOR_FAILURE = "sensor_failure"


@dataclass
class ChannelModel:
    """Model for a single channel's activity behavior."""
    channel: int
    base_probability: float = 0.1
    pattern: ChannelPattern = ChannelPattern.BACKGROUND
    burst_probability: float = 0.0
    burst_duration: float = 0.5
    hop_channels: List[int] = field(default_factory=list)
    hop_interval: float = 0.1
    failure_rate: float = 0.0
    _last_burst_time: float = 0.0
    _in_burst: bool = False
    _hop_index: int = 0
    _last_hop_time: float = 0.0
    
    def get_rpd_probability(self, current_time: float) -> float:
        """Get current RPD probability for this channel."""
        if random.random() < self.failure_rate:
            return -1.0  # Indicates sensor failure
        
        prob = self.base_probability
        
        if self.pattern == ChannelPattern.BURST:
            if self._in_burst:
                if current_time - self._last_burst_time >= self.burst_duration:
                    self._in_burst = False
                else:
                    prob = 0.9
            elif random.random() < self.burst_probability:
                self._in_burst = True
                self._last_burst_time = current_time
                prob = 0.9
        
        elif self.pattern == ChannelPattern.FREQUENCY_HOPPING:
            if current_time - self._last_hop_time >= self.hop_interval:
                self._hop_index = (self._hop_index + 1) % len(self.hop_channels)
                self._last_hop_time = current_time
            if self.channel == self.hop_channels[self._hop_index]:
                prob = 0.8
        
        elif self.pattern == ChannelPattern.WIFI_LIKE:
            wifi_channels = {1: 12, 6: 37, 11: 62}
            if self.channel in wifi_channels.values():
                prob = 0.7 + 0.2 * random.random()
        
        return max(0.0, min(1.0, prob))


class SimRadio:
    """Simulated nRF24L01+ radio for testing and development."""
    
    def __init__(
        self,
        channel_config: ChannelConfig,
        scan_config: ScanConfig,
        seed: Optional[int] = None,
        channel_models: Optional[Dict[int, ChannelModel]] = None,
    ):
        self._channel_config = channel_config
        self._scan_config = scan_config
        self._rng = random.Random(seed)
        self._current_channel = channel_config.start_channel
        self._initialized = False
        self._lock = threading.RLock()
        self._channel_models = channel_models or self._create_default_models()
        self._simulated_time = 0.0
        
    def _create_default_models(self) -> Dict[int, ChannelModel]:
        """Create default channel models with realistic patterns."""
        models = {}
        for ch in self._channel_config.channel_range():
            base_prob = 0.05 + 0.1 * self._rng.random()
            pattern = ChannelPattern.BACKGROUND
            
            if ch in (12, 37, 62):  # Wi-Fi channels 1, 6, 11
                pattern = ChannelPattern.WIFI_LIKE
                base_prob = 0.6
            elif ch in (2, 3, 4, 5, 7, 8, 9, 10):  # Near Wi-Fi 1
                pattern = ChannelPattern.LOW_ACTIVITY
                base_prob = 0.15
            elif ch in (38, 39, 40, 41, 42):  # Near Wi-Fi 6
                pattern = ChannelPattern.LOW_ACTIVITY
                base_prob = 0.15
            elif ch in (63, 64, 65, 66, 67):  # Near Wi-Fi 11
                pattern = ChannelPattern.LOW_ACTIVITY
                base_prob = 0.15
            elif ch in (76, 77, 78):  # Common nRF24 channels
                pattern = ChannelPattern.HIGH_ACTIVITY
                base_prob = 0.4
            elif ch % 10 == 0:  # Some channels with bursts
                pattern = ChannelPattern.BURST
                base_prob = 0.1
            
            models[ch] = ChannelModel(
                channel=ch,
                base_probability=base_prob,
                pattern=pattern,
                burst_probability=0.02 if pattern == ChannelPattern.BURST else 0.0,
                burst_duration=0.3 + 0.5 * self._rng.random(),
                hop_channels=[ch, ch + 10, ch + 20] if pattern == ChannelPattern.FREQUENCY_HOPPING else [],
                hop_interval=0.2,
                failure_rate=0.001,
            )
        return models
    
    def initialize(self) -> bool:
        """Initialize the simulated radio."""
        with self._lock:
            self._initialized = True
            self._current_channel = self._channel_config.start_channel
            self._simulated_time = 0.0
            return True
    
    def is_initialized(self) -> bool:
        return self._initialized
    
    def set_channel(self, channel: int) -> None:
        """Set the current channel."""
        with self._lock:
            if not self._channel_config.start_channel <= channel <= self._channel_config.end_channel:
                raise SimulationError(f"Channel {channel} out of range")
            self._current_channel = channel
    
    def get_channel(self) -> int:
        """Get the current channel."""
        with self._lock:
            return self._current_channel
    
    def read_rpd(self) -> bool:
        """Read RPD (Received Power Detector) status."""
        with self._lock:
            if not self._initialized:
                raise SimulationError("Radio not initialized")
            
            model = self._channel_models.get(self._current_channel)
            if not model:
                return False
            
            prob = model.get_rpd_probability(self._simulated_time)
            if prob < 0:
                raise SimulationError(f"Sensor failure on channel {self._current_channel}")
            
            self._simulated_time += self._scan_config.sampling_interval
            return self._rng.random() < prob
    
    def scan_channel(
        self,
        channel: int,
        duration: Optional[float] = None,
        interval: Optional[float] = None,
    ) -> Tuple[int, int, int]:
        """
        Scan a channel for RPD activity.
        
        Returns:
            Tuple of (valid_samples, rpd_positive, rpd_negative)
        """
        with self._lock:
            if not self._initialized:
                raise SimulationError("Radio not initialized")
            
            duration = duration or self._scan_config.measurement_window
            interval = interval or self._scan_config.sampling_interval
            
            self.set_channel(channel)
            samples = int(duration / interval)
            valid = 0
            positive = 0
            negative = 0
            
            for _ in range(samples):
                try:
                    rpd = self.read_rpd()
                    valid += 1
                    if rpd:
                        positive += 1
                    else:
                        negative += 1
                except SimulationError:
                    pass
            
            return valid, positive, negative
    
    def cleanup(self) -> None:
        """Clean up resources."""
        with self._lock:
            self._initialized = False
    
    def get_channel_model(self, channel: int) -> Optional[ChannelModel]:
        """Get the channel model for inspection."""
        with self._lock:
            return self._channel_models.get(channel)
    
    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        with self._lock:
            self._rng.seed(seed)
            for model in self._channel_models.values():
                model._last_burst_time = 0.0
                model._in_burst = False
                model._hop_index = 0
                model._last_hop_time = 0.0
            self._simulated_time = 0.0