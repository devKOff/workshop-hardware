"""Centralized configuration for v2 RF Spectrum Analyzer."""
from dataclasses import dataclass, field
from typing import List, Optional
import os


@dataclass(frozen=True)
class RadioConfig:
    """Hardware radio configuration."""
    ce_pin: int = 25
    csn_pin: int = 8
    spi_speed_hz: int = 10_000_000
    spi_device: str = "/dev/spidev0.0"
    pa_level: str = "LOW"
    data_rate: str = "2MBPS"
    channel_min: int = 0
    channel_max: int = 125
    freq_base_mhz: int = 2400
    dwell_time_us: int = 130
    settling_time_us: int = 130


@dataclass(frozen=True)
class ScannerConfig:
    """Scanner configuration."""
    num_channels: int = 126
    waterfall_depth: int = 200
    rolling_alpha: float = 0.1
    peak_decay: float = 0.995
    sweep_callback_interval: float = 0.05


@dataclass(frozen=True)
class MitigationConfig:
    """Mitigation engine configuration."""
    min_interval_ms: int = 1000
    max_duration_ms: int = 5000
    default_threshold_db: float = -50.0
    default_target_channels: List[int] = field(default_factory=lambda: [1, 6, 11])
    default_type: str = "carrier"
    audit_log_path: str = "mitigation_audit.log"


@dataclass(frozen=True)
class GUIConfig:
    """GUI configuration."""
    window_title: str = "2.4 GHz ISM Band Spectrum Visualizer v2"
    window_width: int = 1200
    window_height: int = 900
    update_interval_ms: int = 50
    figure_dpi: int = 100
    spectrum_ylim: tuple = (-110, -20)
    waterfall_vlim: tuple = (-100, -20)


@dataclass(frozen=True)
class CLIConfig:
    """CLI configuration."""
    bar_width: int = 60
    db_min: int = -100
    db_max: int = -20
    render_interval: float = 0.1


class Config:
    """Runtime configuration manager."""
    
    def __init__(self):
        self.radio = RadioConfig()
        self.scanner = ScannerConfig()
        self.mitigation = MitigationConfig()
        self.gui = GUIConfig()
        self.cli = CLIConfig()
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()
        
        if ce := os.getenv("RF_CE_PIN"):
            config.radio = RadioConfig(ce_pin=int(ce))
        if csn := os.getenv("RF_CSN_PIN"):
            config.radio = RadioConfig(csn_pin=int(csn))
        if spi_dev := os.getenv("RF_SPI_DEVICE"):
            config.radio = RadioConfig(spi_device=spi_dev)
        if threshold := os.getenv("RF_MIT_THRESHOLD"):
            config.mitigation = MitigationConfig(default_threshold_db=float(threshold))
        
        return config