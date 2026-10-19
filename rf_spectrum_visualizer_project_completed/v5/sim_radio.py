"""Simulation backend for RF Spectrum Visualizer V5."""

import random
import time
import threading
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from config import ChannelConfig, ScanConfig, SimulationConfig
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
    PERSISTENT_HIGH = "persistent_high"
    SUDDEN_SPIKE = "sudden_spike"
    SUDDEN_REDUCTION = "sudden_reduction"


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
    spike_time: float = 0.0
    spike_duration: float = 1.0
    reduction_time: float = 0.0
    reduction_duration: float = 2.0
    _rng: Any = field(default_factory=lambda: random)
    _last_burst_time: float = 0.0
    _in_burst: bool = False
    _hop_index: int = 0
    _last_hop_time: float = 0.0
    _spike_active: bool = False
    _reduction_active: bool = False
    
    def get_rpd_probability(self, current_time: float) -> float:
        """Get current RPD probability for this channel."""
        if self._rng.random() < self.failure_rate:
            return -1.0
        
        prob = self.base_probability
        
        if self.pattern == ChannelPattern.BURST:
            if self._in_burst:
                if current_time - self._last_burst_time >= self.burst_duration:
                    self._in_burst = False
                else:
                    prob = 0.9
            elif self._rng.random() < self.burst_probability:
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
        
        elif self.pattern == ChannelPattern.PERSISTENT_HIGH:
            prob = 0.85 + 0.1 * random.random()
        
        elif self.pattern == ChannelPattern.SUDDEN_SPIKE:
            if not self._spike_active and current_time >= self.spike_time:
                self._spike_active = True
            if self._spike_active:
                if current_time - self.spike_time >= self.spike_duration:
                    self._spike_active = False
                else:
                    prob = 0.95
        
        elif self.pattern == ChannelPattern.SUDDEN_REDUCTION:
            if not self._reduction_active and current_time >= self.reduction_time:
                self._reduction_active = True
            if self._reduction_active:
                if current_time - self.reduction_time >= self.reduction_duration:
                    self._reduction_active = False
                else:
                    prob = 0.05
        
        return max(0.0, min(1.0, prob))


class SimRadio:
    """Simulated nRF24L01+ radio for testing and development."""
    
    SCENARIOS = {
        "default": "Default mixed environment with Wi-Fi-like channels",
        "quiet": "Quiet environment with minimal activity",
        "moderate": "Moderate activity across all channels",
        "persistent_busy": "One persistently busy channel (ch 50)",
        "sudden_spike": "Sudden activity spike on channel 30",
        "intermittent_bursts": "Intermittent bursts on multiple channels",
        "multiple_busy": "Several busy channels (Wi-Fi 1, 6, 11)",
        "hopping_like": "Hopping-like activity across channels",
        "sudden_reduction": "Sudden activity reduction on channel 40",
        "insufficient_samples": "Very short measurement windows",
        "sensor_failures": "Random sensor failures",
        "invalid_channel": "Invalid channel configuration test",
    }
    
    def __init__(
        self,
        channel_config: ChannelConfig,
        scan_config: ScanConfig,
        simulation_config: Optional[SimulationConfig] = None,
        seed: Optional[int] = None,
        channel_models: Optional[Dict[int, ChannelModel]] = None,
    ):
        self._channel_config = channel_config
        self._scan_config = scan_config
        self._simulation_config = simulation_config or SimulationConfig()
        self._rng = random.Random(seed or self._simulation_config.seed)
        self._current_channel = channel_config.start_channel
        self._initialized = False
        self._lock = threading.RLock()
        self._channel_models = channel_models or self._create_models()
        self._simulated_time = 0.0
    
    def _create_models(self) -> Dict[int, ChannelModel]:
        """Create channel models based on scenario."""
        scenario = self._simulation_config.scenario
        models = {}
        
        if scenario == "quiet":
            return self._create_quiet_models()
        elif scenario == "moderate":
            return self._create_moderate_models()
        elif scenario == "persistent_busy":
            return self._create_persistent_busy_models()
        elif scenario == "sudden_spike":
            return self._create_sudden_spike_models()
        elif scenario == "intermittent_bursts":
            return self._create_intermittent_bursts_models()
        elif scenario == "multiple_busy":
            return self._create_multiple_busy_models()
        elif scenario == "hopping_like":
            return self._create_hopping_like_models()
        elif scenario == "sudden_reduction":
            return self._create_sudden_reduction_models()
        elif scenario == "insufficient_samples":
            return self._create_insufficient_samples_models()
        elif scenario == "sensor_failures":
            return self._create_sensor_failure_models()
        elif scenario == "invalid_channel":
            return self._create_invalid_channel_models()
        else:
            return self._create_default_models()
    
    def _create_default_models(self) -> Dict[int, ChannelModel]:
        models = {}
        for ch in self._channel_config.channel_range():
            base_prob = 0.05 + 0.15 * self._rng.random()
            pattern = ChannelPattern.BACKGROUND
            
            if ch in (12, 37, 62):
                pattern = ChannelPattern.WIFI_LIKE
                base_prob = 0.6
            elif ch in (2, 3, 4, 5, 7, 8, 9, 10):
                pattern = ChannelPattern.LOW_ACTIVITY
                base_prob = 0.15
            elif ch in (38, 39, 40, 41, 42):
                pattern = ChannelPattern.LOW_ACTIVITY
                base_prob = 0.15
            elif ch in (63, 64, 65, 66, 67):
                pattern = ChannelPattern.LOW_ACTIVITY
                base_prob = 0.15
            elif ch in (76, 77, 78):
                pattern = ChannelPattern.HIGH_ACTIVITY
                base_prob = 0.4
            elif ch % 10 == 0:
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
                _rng=self._rng,
            )
        return models
    
    def _create_quiet_models(self) -> Dict[int, ChannelModel]:
        models = {}
        for ch in self._channel_config.channel_range():
            models[ch] = ChannelModel(
                channel=ch,
                base_probability=0.01 + 0.02 * self._rng.random(),
                pattern=ChannelPattern.BACKGROUND,
                failure_rate=0.0001,
                _rng=self._rng,
            )
        return models
    
    def _create_moderate_models(self) -> Dict[int, ChannelModel]:
        models = {}
        for ch in self._channel_config.channel_range():
            models[ch] = ChannelModel(
                channel=ch,
                base_probability=0.25 + 0.15 * self._rng.random(),
                pattern=ChannelPattern.BACKGROUND,
                failure_rate=0.0001,
                _rng=self._rng,
            )
        return models
    
    def _create_persistent_busy_models(self) -> Dict[int, ChannelModel]:
        models = self._create_quiet_models()
        busy_ch = 50
        if busy_ch in models:
            models[busy_ch] = ChannelModel(
                channel=busy_ch,
                base_probability=0.85,
                pattern=ChannelPattern.PERSISTENT_HIGH,
                _rng=self._rng,
            )
        return models
    
    def _create_sudden_spike_models(self) -> Dict[int, ChannelModel]:
        models = self._create_quiet_models()
        spike_ch = 30
        if spike_ch in models:
            models[spike_ch] = ChannelModel(
                channel=spike_ch,
                base_probability=0.05,
                pattern=ChannelPattern.SUDDEN_SPIKE,
                spike_time=5.0,
                spike_duration=2.0,
                _rng=self._rng,
            )
        return models
    
    def _create_intermittent_bursts_models(self) -> Dict[int, ChannelModel]:
        models = {}
        for ch in self._channel_config.channel_range():
            base_prob = 0.05 + 0.05 * self._rng.random()
            pattern = ChannelPattern.BACKGROUND
            burst_prob = 0.0
            
            if ch in (10, 25, 45, 60, 85, 100):
                pattern = ChannelPattern.BURST
                burst_prob = 0.1
                base_prob = 0.05
            
            models[ch] = ChannelModel(
                channel=ch,
                base_probability=base_prob,
                pattern=pattern,
                burst_probability=burst_prob,
                burst_duration=0.2 + 0.3 * self._rng.random(),
                _rng=self._rng,
            )
        return models
    
    def _create_multiple_busy_models(self) -> Dict[int, ChannelModel]:
        models = self._create_quiet_models()
        busy_channels = {12: 0.7, 37: 0.75, 62: 0.8, 76: 0.5, 77: 0.5}
        for ch, prob in busy_channels.items():
            if ch in models:
                models[ch] = ChannelModel(
                    channel=ch,
                    base_probability=prob,
                    pattern=ChannelPattern.HIGH_ACTIVITY,
                    _rng=self._rng,
                )
        return models
    
    def _create_hopping_like_models(self) -> Dict[int, ChannelModel]:
        models = {}
        hop_sequence = [5, 15, 25, 35, 45, 55, 65, 75, 85, 95]
        for ch in self._channel_config.channel_range():
            if ch in hop_sequence:
                models[ch] = ChannelModel(
                    channel=ch,
                    base_probability=0.1,
                    pattern=ChannelPattern.FREQUENCY_HOPPING,
                    hop_channels=hop_sequence,
                    hop_interval=0.5,
                    _rng=self._rng,
                )
            else:
                models[ch] = ChannelModel(
                    channel=ch,
                    base_probability=0.02,
                    pattern=ChannelPattern.BACKGROUND,
                    _rng=self._rng,
                )
        return models
    
    def _create_sudden_reduction_models(self) -> Dict[int, ChannelModel]:
        models = self._create_moderate_models()
        reduction_ch = 40
        if reduction_ch in models:
            models[reduction_ch] = ChannelModel(
                channel=reduction_ch,
                base_probability=0.5,
                pattern=ChannelPattern.SUDDEN_REDUCTION,
                reduction_time=3.0,
                reduction_duration=5.0,
                _rng=self._rng,
            )
        return models
    
    def _create_insufficient_samples_models(self) -> Dict[int, ChannelModel]:
        return self._create_quiet_models()
    
    def _create_sensor_failure_models(self) -> Dict[int, ChannelModel]:
        models = {}
        for ch in self._channel_config.channel_range():
            failure_rate = 0.1 if ch % 7 == 0 else 0.001
            models[ch] = ChannelModel(
                channel=ch,
                base_probability=0.1 + 0.1 * self._rng.random(),
                pattern=ChannelPattern.BACKGROUND,
                failure_rate=failure_rate,
                _rng=self._rng,
            )
        return models
    
    def _create_invalid_channel_models(self) -> Dict[int, ChannelModel]:
        return self._create_default_models()
    
    def initialize(self) -> bool:
        """Initialize the simulated radio."""
        with self._lock:
            self._initialized = True
            self._current_channel = self._channel_config.start_channel
            self._simulated_time = 0.0
            for model in self._channel_models.values():
                model._last_burst_time = 0.0
                model._in_burst = False
                model._hop_index = 0
                model._last_hop_time = 0.0
                model._spike_active = False
                model._reduction_active = False
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
                model._spike_active = False
                model._reduction_active = False
            self._simulated_time = 0.0
    
    @classmethod
    def get_available_scenarios(cls) -> Dict[str, str]:
        """Get available simulation scenarios."""
        return cls.SCENARIOS.copy()
    
    @classmethod
    def create_scenario(cls, scenario_name: str, channel_config: ChannelConfig, 
                        scan_config: ScanConfig, seed: Optional[int] = None) -> "SimRadio":
        """Create a SimRadio with a specific scenario."""
        sim_config = SimulationConfig(scenario=scenario_name, seed=seed)
        return cls(channel_config, scan_config, sim_config, seed)


def create_test_scenarios() -> Dict[str, Tuple[ChannelConfig, ScanConfig, Dict]]:
    """Create test scenarios with expected outcomes."""
    channel_config = ChannelConfig(start_channel=0, end_channel=125)
    scan_config = ScanConfig(measurement_window=1.0, sampling_interval=0.01)
    
    return {
        "quiet": (channel_config, scan_config, {"expected_heavy": 0, "expected_anomalies": 0}),
        "moderate": (channel_config, scan_config, {"expected_heavy": 0, "expected_anomalies": 0}),
        "persistent_busy": (channel_config, scan_config, {"expected_heavy": 1, "expected_anomalies": 1}),
        "sudden_spike": (channel_config, scan_config, {"expected_heavy": 0, "expected_anomalies": 1}),
        "intermittent_bursts": (channel_config, scan_config, {"expected_heavy": 0, "expected_anomalies": 5}),
        "multiple_busy": (channel_config, scan_config, {"expected_heavy": 5, "expected_anomalies": 3}),
        "hopping_like": (channel_config, scan_config, {"expected_heavy": 0, "expected_anomalies": 1}),
        "sudden_reduction": (channel_config, scan_config, {"expected_heavy": 0, "expected_anomalies": 1}),
        "insufficient_samples": (channel_config, ScanConfig(measurement_window=0.1, sampling_interval=0.01), {"expected_heavy": 0, "expected_anomalies": 0}),
        "sensor_failures": (channel_config, scan_config, {"expected_heavy": 0, "expected_anomalies": 0}),
    }