"""Unit tests for configuration module."""

import pytest
from config import (
    ChannelConfig, ScanConfig, ThresholdConfig, AnomalyConfig,
    StorageConfig, GUIConfig, SimulationConfig, AppConfig,
    load_config_from_dict, DEFAULT_CONFIG
)


class TestChannelConfig:
    """Tests for ChannelConfig."""
    
    def test_default_range(self):
        config = ChannelConfig()
        assert config.start_channel == 0
        assert config.end_channel == 125
        assert config.channel_count == 126
        assert len(config.channel_range()) == 126
    
    def test_custom_range(self):
        config = ChannelConfig(start_channel=10, end_channel=20)
        assert config.channel_count == 11
        assert config.channel_range() == list(range(10, 21))
    
    def test_invalid_start_channel(self):
        with pytest.raises(ValueError):
            ChannelConfig(start_channel=-1)
        with pytest.raises(ValueError):
            ChannelConfig(start_channel=126)
    
    def test_invalid_end_channel(self):
        with pytest.raises(ValueError):
            ChannelConfig(end_channel=-1)
        with pytest.raises(ValueError):
            ChannelConfig(end_channel=126)
    
    def test_start_greater_than_end(self):
        with pytest.raises(ValueError):
            ChannelConfig(start_channel=50, end_channel=40)
    
    def test_channel_filter(self):
        config = ChannelConfig(channel_filter=[1, 5, 10, 50])
        assert config.channel_count == 4
        assert config.channel_range() == [1, 5, 10, 50]
    
    def test_invalid_filter_channel(self):
        with pytest.raises(ValueError):
            ChannelConfig(channel_filter=[0, 126])
    
    def test_frequency_conversion(self):
        config = ChannelConfig()
        assert config.channel_to_frequency(0) == 2400
        assert config.channel_to_frequency(12) == 2412
        assert config.channel_to_frequency(37) == 2437
        assert config.channel_to_frequency(62) == 2462
        assert config.channel_to_frequency(125) == 2525
        
        assert config.frequency_to_channel(2400) == 0
        assert config.frequency_to_channel(2412) == 12
        assert config.frequency_to_channel(2437) == 37
        assert config.frequency_to_channel(2462) == 62
        assert config.frequency_to_channel(2525) == 125
    
    def test_frequency_conversion_errors(self):
        config = ChannelConfig()
        with pytest.raises(ValueError):
            config.channel_to_frequency(-1)
        with pytest.raises(ValueError):
            config.channel_to_frequency(126)
        with pytest.raises(ValueError):
            config.frequency_to_channel(2399)
        with pytest.raises(ValueError):
            config.frequency_to_channel(2526)


class TestScanConfig:
    """Tests for ScanConfig."""
    
    def test_defaults(self):
        config = ScanConfig()
        assert config.measurement_window == 1.0
        assert config.sampling_interval == 0.01
        assert config.min_valid_samples == 10
    
    def test_expected_samples(self):
        config = ScanConfig(measurement_window=1.0, sampling_interval=0.01)
        assert config.expected_samples_per_channel == 100
    
    def test_invalid_measurement_window(self):
        with pytest.raises(ValueError):
            ScanConfig(measurement_window=0)
        with pytest.raises(ValueError):
            ScanConfig(measurement_window=-1)
    
    def test_invalid_sampling_interval(self):
        with pytest.raises(ValueError):
            ScanConfig(sampling_interval=0)
        with pytest.raises(ValueError):
            ScanConfig(sampling_interval=-0.01)
    
    def test_window_less_than_interval(self):
        with pytest.raises(ValueError):
            ScanConfig(measurement_window=0.005, sampling_interval=0.01)
    
    def test_scan_repetitions(self):
        config = ScanConfig(scan_repetitions=5)
        assert config.scan_repetitions == 5
    
    def test_negative_repetitions(self):
        with pytest.raises(ValueError):
            ScanConfig(scan_repetitions=-1)
    
    def test_estimated_scan_duration(self):
        config = ScanConfig(measurement_window=1.0)
        # 126 channels * 1.0s = 126s
        assert config.estimated_scan_duration == 126.0


class TestThresholdConfig:
    """Tests for ThresholdConfig."""
    
    def test_defaults(self):
        config = ThresholdConfig()
        assert config.clear_max == 24
        assert config.moderate_max == 49
        assert config.busy_max == 74
        assert config.heavy_min == 75
    
    def test_classify(self):
        config = ThresholdConfig()
        assert config.classify(None) == "INSUFFICIENT DATA"
        assert config.classify(0) == "CLEAR"
        assert config.classify(10) == "CLEAR"
        assert config.classify(24) == "CLEAR"
        assert config.classify(25) == "MODERATE"
        assert config.classify(49) == "MODERATE"
        assert config.classify(50) == "BUSY"
        assert config.classify(74) == "BUSY"
        assert config.classify(75) == "HEAVY LOAD"
        assert config.classify(100) == "HEAVY LOAD"
    
    def test_invalid_thresholds(self):
        with pytest.raises(ValueError):
            ThresholdConfig(clear_max=50, moderate_max=40)  # Not ordered
        with pytest.raises(ValueError):
            ThresholdConfig(clear_max=-1)
        with pytest.raises(ValueError):
            ThresholdConfig(heavy_min=101)
    
    def test_get_thresholds_dict(self):
        config = ThresholdConfig()
        d = config.get_thresholds_dict()
        assert d["CLEAR"] == 24
        assert d["MODERATE"] == 49
        assert d["BUSY"] == 74
        assert d["HEAVY LOAD"] == 75


class TestAnomalyConfig:
    """Tests for AnomalyConfig."""
    
    def test_defaults(self):
        config = AnomalyConfig()
        assert config.baseline_learning_scans == 10
        assert config.rolling_history_length == 100
        assert config.persistent_threshold == 75.0
        assert config.persistence_windows == 3
        assert config.spike_threshold == 30.0
        assert config.burst_threshold == 40.0
        assert config.change_threshold == 25.0
    
    def test_invalid_baseline_scans(self):
        with pytest.raises(ValueError):
            AnomalyConfig(baseline_learning_scans=0)
    
    def test_invalid_history_length(self):
        with pytest.raises(ValueError):
            AnomalyConfig(rolling_history_length=5)
    
    def test_invalid_thresholds(self):
        with pytest.raises(ValueError):
            AnomalyConfig(persistent_threshold=-1)
        with pytest.raises(ValueError):
            AnomalyConfig(persistent_threshold=101)
        with pytest.raises(ValueError):
            AnomalyConfig(spike_threshold=101)
        with pytest.raises(ValueError):
            AnomalyConfig(change_threshold=101)


class TestStorageConfig:
    """Tests for StorageConfig."""
    
    def test_defaults(self):
        config = StorageConfig()
        assert config.rolling_history_size == 100
        assert config.waterfall_history_size == 200
        assert config.anomaly_history_size == 500
    
    def test_invalid_sizes(self):
        with pytest.raises(ValueError):
            StorageConfig(rolling_history_size=0)
        with pytest.raises(ValueError):
            StorageConfig(waterfall_history_size=0)


class TestGUIConfig:
    """Tests for GUIConfig."""
    
    def test_defaults(self):
        config = GUIConfig()
        assert config.refresh_interval_ms == 500
        assert config.spectrum_max_channels == 126
    
    def test_invalid_refresh(self):
        with pytest.raises(ValueError):
            GUIConfig(refresh_interval_ms=50)


class TestSimulationConfig:
    """Tests for SimulationConfig."""
    
    def test_defaults(self):
        config = SimulationConfig()
        assert config.scenario == "default"
    
    def test_valid_scenarios(self):
        for scenario in [
            "default", "quiet", "moderate", "persistent_busy", "sudden_spike",
            "intermittent_bursts", "multiple_busy", "hopping_like", "sudden_reduction",
            "insufficient_samples", "sensor_failures", "invalid_channel"
        ]:
            config = SimulationConfig(scenario=scenario)
            assert config.scenario == scenario
    
    def test_invalid_scenario(self):
        with pytest.raises(ValueError):
            SimulationConfig(scenario="invalid")


class TestAppConfig:
    """Tests for AppConfig."""
    
    def test_defaults(self):
        config = AppConfig()
        assert config.default_backend == "sim"
        assert config.log_level == "INFO"
    
    def test_invalid_backend(self):
        with pytest.raises(ValueError):
            AppConfig(default_backend="invalid")
    
    def test_invalid_log_level(self):
        with pytest.raises(ValueError):
            AppConfig(log_level="INVALID")
    
    def test_to_dict(self):
        config = AppConfig()
        d = config.to_dict()
        assert "channel" in d
        assert "scan" in d
        assert "thresholds" in d
        assert "anomaly" in d
        assert "storage" in d
        assert "gui" in d
        assert "simulation" in d


class TestLoadConfigFromDict:
    """Tests for loading config from dictionary."""
    
    def test_load_partial_config(self):
        data = {
            "channel": {"start_channel": 10, "end_channel": 20},
            "scan": {"measurement_window": 2.0},
            "default_backend": "hardware",
        }
        config = load_config_from_dict(data)
        assert config.channel.start_channel == 10
        assert config.channel.end_channel == 20
        assert config.scan.measurement_window == 2.0
        assert config.default_backend == "hardware"
    
    def test_load_full_config(self):
        data = {
            "channel": {"start_channel": 0, "end_channel": 125},
            "scan": {"measurement_window": 1.0, "sampling_interval": 0.01},
            "thresholds": {"CLEAR": 20, "MODERATE": 40, "BUSY": 70, "HEAVY LOAD": 80},
            "anomaly": {"persistent_threshold": 80.0},
            "default_backend": "sim",
        }
        config = load_config_from_dict(data)
        assert config.thresholds.clear_max == 20
        assert config.anomaly.persistent_threshold == 80.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])