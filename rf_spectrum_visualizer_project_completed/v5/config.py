"""Configuration module for RF Spectrum Visualizer V5.

Provides validated configuration dataclasses for all application settings.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path


@dataclass
class ChannelConfig:
    """Channel scanning configuration."""
    start_channel: int = 0
    end_channel: int = 125
    channel_filter: Optional[List[int]] = None
    
    def __post_init__(self):
        if not (0 <= self.start_channel <= 125):
            raise ValueError("start_channel must be between 0 and 125")
        if not (0 <= self.end_channel <= 125):
            raise ValueError("end_channel must be between 0 and 125")
        if self.start_channel > self.end_channel:
            raise ValueError("start_channel must be <= end_channel")
        if self.channel_filter is not None:
            for ch in self.channel_filter:
                if not (0 <= ch <= 125):
                    raise ValueError(f"Channel filter contains invalid channel: {ch}")
    
    @property
    def channel_count(self) -> int:
        if self.channel_filter:
            return len(self.channel_filter)
        return self.end_channel - self.start_channel + 1
    
    def channel_range(self) -> List[int]:
        if self.channel_filter:
            return sorted(self.channel_filter)
        return list(range(self.start_channel, self.end_channel + 1))
    
    def channel_to_frequency(self, channel: int) -> int:
        if not (0 <= channel <= 125):
            raise ValueError(f"Channel {channel} out of range 0-125")
        return 2400 + channel
    
    def frequency_to_channel(self, frequency_mhz: int) -> int:
        channel = frequency_mhz - 2400
        if not (0 <= channel <= 125):
            raise ValueError(f"Frequency {frequency_mhz} MHz out of range 2400-2525 MHz")
        return channel


@dataclass
class ScanConfig:
    """Scanning timing configuration."""
    measurement_window: float = 1.0
    sampling_interval: float = 0.01
    min_valid_samples: int = 10
    scan_repetitions: int = 0
    retry_failed_channels: bool = True
    max_retries: int = 2
    
    def __post_init__(self):
        if self.measurement_window <= 0:
            raise ValueError("measurement_window must be positive")
        if self.sampling_interval <= 0:
            raise ValueError("sampling_interval must be positive")
        if self.min_valid_samples < 1:
            raise ValueError("min_valid_samples must be >= 1")
        if self.scan_repetitions < 0:
            raise ValueError("scan_repetitions must be >= 0")
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.measurement_window < self.sampling_interval:
            raise ValueError("measurement_window must be >= sampling_interval")
    
    @property
    def expected_samples_per_channel(self) -> int:
        return max(1, int(self.measurement_window / self.sampling_interval))
    
    @property
    def estimated_scan_duration(self) -> float:
        channels = 126
        return channels * self.measurement_window * (1 + self.scan_repetitions)


@dataclass
class ThresholdConfig:
    """Activity classification thresholds."""
    clear_max: int = 24
    moderate_max: int = 49
    busy_max: int = 74
    heavy_min: int = 75
    
    def __post_init__(self):
        if not (0 <= self.clear_max < self.moderate_max < self.busy_max < self.heavy_min <= 100):
            raise ValueError(
                "Thresholds must be ordered: 0 <= clear < moderate < busy < heavy <= 100"
            )
    
    def classify(self, percentage: Optional[float]) -> str:
        if percentage is None:
            return "INSUFFICIENT DATA"
        if percentage <= self.clear_max:
            return "CLEAR"
        if percentage <= self.moderate_max:
            return "MODERATE"
        if percentage <= self.busy_max:
            return "BUSY"
        return "HEAVY LOAD"
    
    def get_thresholds_dict(self) -> Dict[str, int]:
        return {
            "CLEAR": self.clear_max,
            "MODERATE": self.moderate_max,
            "BUSY": self.busy_max,
            "HEAVY LOAD": self.heavy_min,
        }


@dataclass
class AnomalyConfig:
    """Anomaly detection configuration."""
    baseline_learning_scans: int = 10
    rolling_history_length: int = 100
    persistent_threshold: float = 75.0
    persistence_windows: int = 3
    spike_threshold: float = 30.0
    spike_window: int = 1
    burst_threshold: float = 40.0
    burst_min_windows: int = 2
    burst_max_gap: int = 3
    change_threshold: float = 25.0
    hopping_min_channels: int = 3
    hopping_max_interval: int = 5
    insufficient_baseline_windows: int = 3
    alert_cooldown: float = 30.0
    hysteresis: float = 5.0
    
    def __post_init__(self):
        if self.baseline_learning_scans < 1:
            raise ValueError("baseline_learning_scans must be >= 1")
        if self.rolling_history_length < 10:
            raise ValueError("rolling_history_length must be >= 10")
        if not (0 <= self.persistent_threshold <= 100):
            raise ValueError("persistent_threshold must be 0-100")
        if self.persistence_windows < 1:
            raise ValueError("persistence_windows must be >= 1")
        if not (0 <= self.spike_threshold <= 100):
            raise ValueError("spike_threshold must be 0-100")
        if self.spike_window < 1:
            raise ValueError("spike_window must be >= 1")
        if not (0 <= self.burst_threshold <= 100):
            raise ValueError("burst_threshold must be 0-100")
        if self.burst_min_windows < 1:
            raise ValueError("burst_min_windows must be >= 1")
        if self.burst_max_gap < 0:
            raise ValueError("burst_max_gap must be >= 0")
        if not (0 <= self.change_threshold <= 100):
            raise ValueError("change_threshold must be 0-100")
        if self.hopping_min_channels < 2:
            raise ValueError("hopping_min_channels must be >= 2")
        if self.hopping_max_interval < 1:
            raise ValueError("hopping_max_interval must be >= 1")
        if self.insufficient_baseline_windows < 1:
            raise ValueError("insufficient_baseline_windows must be >= 1")
        if self.alert_cooldown < 0:
            raise ValueError("alert_cooldown must be >= 0")
        if not (0 <= self.hysteresis <= 50):
            raise ValueError("hysteresis must be 0-50")


@dataclass
class StorageConfig:
    """Data storage configuration."""
    rolling_history_size: int = 100
    waterfall_history_size: int = 200
    anomaly_history_size: int = 500
    log_path: str = "logs/anomalies.jsonl"
    export_dir: str = "exports"
    export_on_scan_complete: bool = False
    
    def __post_init__(self):
        if self.rolling_history_size < 1:
            raise ValueError("rolling_history_size must be >= 1")
        if self.waterfall_history_size < 1:
            raise ValueError("waterfall_history_size must be >= 1")
        if self.anomaly_history_size < 1:
            raise ValueError("anomaly_history_size must be >= 1")
        Path(self.export_dir).mkdir(parents=True, exist_ok=True)
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)


@dataclass
class GUIConfig:
    """GUI configuration."""
    refresh_interval_ms: int = 500
    spectrum_max_channels: int = 126
    waterfall_time_window: float = 60.0
    show_wifi_overlay: bool = True
    auto_scroll_alerts: bool = True
    table_font_size: int = 9
    
    def __post_init__(self):
        if self.refresh_interval_ms < 100:
            raise ValueError("refresh_interval_ms must be >= 100")
        if self.spectrum_max_channels < 1:
            raise ValueError("spectrum_max_channels must be >= 1")
        if self.waterfall_time_window <= 0:
            raise ValueError("waterfall_time_window must be positive")


@dataclass
class SimulationConfig:
    """Simulation backend configuration."""
    seed: Optional[int] = None
    scenario: str = "default"
    custom_models: Optional[Dict[int, Dict[str, Any]]] = None
    
    def __post_init__(self):
        valid_scenarios = [
            "default", "quiet", "moderate", "persistent_busy", "sudden_spike",
            "intermittent_bursts", "multiple_busy", "hopping_like", "sudden_reduction",
            "insufficient_samples", "sensor_failures", "invalid_channel"
        ]
        if self.scenario not in valid_scenarios:
            raise ValueError(f"Invalid scenario: {self.scenario}. Valid: {valid_scenarios}")


@dataclass
class AppConfig:
    """Main application configuration."""
    channel: ChannelConfig = field(default_factory=ChannelConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    gui: GUIConfig = field(default_factory=GUIConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    default_backend: str = "sim"
    log_level: str = "INFO"
    
    def __post_init__(self):
        if self.default_backend not in ("hardware", "sim"):
            raise ValueError("default_backend must be 'hardware' or 'sim'")
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(f"log_level must be one of {valid_log_levels}")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": {
                "start_channel": self.channel.start_channel,
                "end_channel": self.channel.end_channel,
                "channel_filter": self.channel.channel_filter,
            },
            "scan": {
                "measurement_window": self.scan.measurement_window,
                "sampling_interval": self.scan.sampling_interval,
                "min_valid_samples": self.scan.min_valid_samples,
                "scan_repetitions": self.scan.scan_repetitions,
                "retry_failed_channels": self.scan.retry_failed_channels,
                "max_retries": self.scan.max_retries,
            },
            "thresholds": self.thresholds.get_thresholds_dict(),
            "anomaly": {
                "baseline_learning_scans": self.anomaly.baseline_learning_scans,
                "rolling_history_length": self.anomaly.rolling_history_length,
                "persistent_threshold": self.anomaly.persistent_threshold,
                "persistence_windows": self.anomaly.persistence_windows,
                "spike_threshold": self.anomaly.spike_threshold,
                "burst_threshold": self.anomaly.burst_threshold,
                "change_threshold": self.anomaly.change_threshold,
            },
            "storage": {
                "rolling_history_size": self.storage.rolling_history_size,
                "waterfall_history_size": self.storage.waterfall_history_size,
                "anomaly_history_size": self.storage.anomaly_history_size,
                "log_path": self.storage.log_path,
                "export_dir": self.storage.export_dir,
            },
            "gui": {
                "refresh_interval_ms": self.gui.refresh_interval_ms,
                "spectrum_max_channels": self.gui.spectrum_max_channels,
                "waterfall_time_window": self.gui.waterfall_time_window,
            },
            "simulation": {
                "seed": self.simulation.seed,
                "scenario": self.simulation.scenario,
            },
            "default_backend": self.default_backend,
            "log_level": self.log_level,
        }


DEFAULT_CONFIG = AppConfig()


def load_config_from_dict(data: Dict[str, Any]) -> AppConfig:
    """Create AppConfig from dictionary."""
    channel = ChannelConfig(
        start_channel=data.get("channel", {}).get("start_channel", 0),
        end_channel=data.get("channel", {}).get("end_channel", 125),
        channel_filter=data.get("channel", {}).get("channel_filter"),
    )
    
    scan = ScanConfig(
        measurement_window=data.get("scan", {}).get("measurement_window", 1.0),
        sampling_interval=data.get("scan", {}).get("sampling_interval", 0.01),
        min_valid_samples=data.get("scan", {}).get("min_valid_samples", 10),
        scan_repetitions=data.get("scan", {}).get("scan_repetitions", 0),
        retry_failed_channels=data.get("scan", {}).get("retry_failed_channels", True),
        max_retries=data.get("scan", {}).get("max_retries", 2),
    )
    
    thresholds_data = data.get("thresholds", {})
    thresholds = ThresholdConfig(
        clear_max=thresholds_data.get("CLEAR", 24),
        moderate_max=thresholds_data.get("MODERATE", 49),
        busy_max=thresholds_data.get("BUSY", 74),
        heavy_min=thresholds_data.get("HEAVY LOAD", 75),
    )
    
    anomaly_data = data.get("anomaly", {})
    anomaly = AnomalyConfig(
        baseline_learning_scans=anomaly_data.get("baseline_learning_scans", 10),
        rolling_history_length=anomaly_data.get("rolling_history_length", 100),
        persistent_threshold=anomaly_data.get("persistent_threshold", 75.0),
        persistence_windows=anomaly_data.get("persistence_windows", 3),
        spike_threshold=anomaly_data.get("spike_threshold", 30.0),
        burst_threshold=anomaly_data.get("burst_threshold", 40.0),
        change_threshold=anomaly_data.get("change_threshold", 25.0),
    )
    
    storage_data = data.get("storage", {})
    storage = StorageConfig(
        rolling_history_size=storage_data.get("rolling_history_size", 100),
        waterfall_history_size=storage_data.get("waterfall_history_size", 200),
        anomaly_history_size=storage_data.get("anomaly_history_size", 500),
        log_path=storage_data.get("log_path", "logs/anomalies.jsonl"),
        export_dir=storage_data.get("export_dir", "exports"),
    )
    
    gui_data = data.get("gui", {})
    gui = GUIConfig(
        refresh_interval_ms=gui_data.get("refresh_interval_ms", 500),
        spectrum_max_channels=gui_data.get("spectrum_max_channels", 126),
        waterfall_time_window=gui_data.get("waterfall_time_window", 60.0),
    )
    
    sim_data = data.get("simulation", {})
    simulation = SimulationConfig(
        seed=sim_data.get("seed"),
        scenario=sim_data.get("scenario", "default"),
    )
    
    return AppConfig(
        channel=channel,
        scan=scan,
        thresholds=thresholds,
        anomaly=anomaly,
        storage=storage,
        gui=gui,
        simulation=simulation,
        default_backend=data.get("default_backend", "sim"),
        log_level=data.get("log_level", "INFO"),
    )