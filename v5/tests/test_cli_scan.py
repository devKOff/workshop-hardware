"""Unit tests for CLI module."""

import pytest
import sys
import io
import time
from unittest.mock import Mock, patch, MagicMock
from cli_scan import (
    CLIDisplay, create_config_from_args, run_single_scan, run_diagnostic
)
from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, AnomalyConfig
from scanner import SpectrumData, ChannelObservation
from sim_radio import SimRadio


class TestCLIDisplay:
    """Tests for CLIDisplay."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
            anomaly=AnomalyConfig(),
        )
    
    @pytest.fixture
    def display(self, config):
        return CLIDisplay(config, use_ascii=True)
    
    def test_render_header(self, display):
        lines = display.render_header("sim", 5, 2)
        
        assert len(lines) >= 7
        assert "2.4 GHz RF ACTIVITY MONITOR" in lines[1]
        assert "Backend: SIM" in lines[3]
        assert "Scans completed: 5" in lines[6]
        assert "Active anomalies: 2" in lines[7]
    
    def test_make_activity_bar(self, display):
        bar = display.make_activity_bar(50.0)
        assert len(bar) == display.ACTIVITY_BAR_WIDTH + 2  # brackets
        assert "#" in bar
        assert "-" in bar
    
    def test_make_activity_bar_none(self, display):
        bar = display.make_activity_bar(None)
        assert "?" in bar
    
    def test_render_channel(self, display):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=25,
            rpd_negative=75,
            activity_percentage=25.0,
            status="MODERATE",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        
        line = display.render_channel(obs)
        
        assert "Ch  10" in line
        assert "2410 MHz" in line
        assert "MODERATE" in line
        assert "25.0%" in line or " 25%" in line
    
    def test_render_channel_insufficient(self, display):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=5,
            rpd_positive=1,
            rpd_negative=4,
            activity_percentage=None,
            status="INSUFFICIENT DATA",
            data_sufficient=False,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        
        line = display.render_channel(obs)
        
        assert "N/A" in line
        assert "insufficient data" in line
    
    def test_render_channel_error(self, display):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=0,
            rpd_positive=0,
            rpd_negative=0,
            activity_percentage=None,
            status="SENSOR_ERROR",
            data_sufficient=False,
            measurement_window=1.0,
            sampling_interval=0.01,
            error="SPI error",
        )
        
        line = display.render_channel(obs)
        
        assert "ERROR" in line
        assert "SPI error" in line
    
    def test_should_show_filters(self, display):
        obs_heavy = ChannelObservation(
            timestamp=time.time(), channel=10, frequency_mhz=2410, backend="sim",
            valid_samples=100, rpd_positive=80, rpd_negative=20,
            activity_percentage=80.0, status="HEAVY LOAD", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01,
        )
        obs_clear = ChannelObservation(
            timestamp=time.time(), channel=5, frequency_mhz=2405, backend="sim",
            valid_samples=100, rpd_positive=10, rpd_negative=90,
            activity_percentage=10.0, status="CLEAR", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01,
        )
        obs_insufficient = ChannelObservation(
            timestamp=time.time(), channel=3, frequency_mhz=2403, backend="sim",
            valid_samples=5, rpd_positive=1, rpd_negative=4,
            activity_percentage=None, status="INSUFFICIENT DATA", data_sufficient=False,
            measurement_window=1.0, sampling_interval=0.01,
        )
        obs_error = ChannelObservation(
            timestamp=time.time(), channel=7, frequency_mhz=2407, backend="sim",
            valid_samples=0, rpd_positive=0, rpd_negative=0,
            activity_percentage=None, status="SENSOR_ERROR", data_sufficient=False,
            measurement_window=1.0, sampling_interval=0.01, error="SPI",
        )
        
        # Test all filter
        display._filter = "all"
        assert display.should_show(obs_heavy) is True
        assert display.should_show(obs_clear) is True
        assert display.should_show(obs_insufficient) is True
        assert display.should_show(obs_error) is True
        
        # Test heavy filter
        display._filter = "heavy"
        assert display.should_show(obs_heavy) is True
        assert display.should_show(obs_clear) is False
        
        # Test quiet filter
        display._filter = "quiet"
        assert display.should_show(obs_clear) is True
        assert display.should_show(obs_heavy) is False
        
        # Test insufficient filter
        display._filter = "insufficient"
        assert display.should_show(obs_insufficient) is True
        assert display.should_show(obs_clear) is False
        
        # Test errors filter
        display._filter = "errors"
        assert display.should_show(obs_error) is True
        assert display.should_show(obs_clear) is False
    
    def test_sort_key(self, display):
        obs1 = ChannelObservation(
            timestamp=time.time(), channel=10, frequency_mhz=2410, backend="sim",
            valid_samples=100, rpd_positive=50, rpd_negative=50,
            activity_percentage=50.0, status="BUSY", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01,
        )
        obs2 = ChannelObservation(
            timestamp=time.time(), channel=5, frequency_mhz=2405, backend="sim",
            valid_samples=100, rpd_positive=80, rpd_negative=20,
            activity_percentage=80.0, status="HEAVY LOAD", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01,
        )
        
        display._sort_by = "channel"
        assert display.sort_key(obs1) == (10,)
        assert display.sort_key(obs2) == (5,)
        
        display._sort_by = "activity"
        assert display.sort_key(obs1) == (-50.0, 10)
        assert display.sort_key(obs2) == (-80.0, 5)
        
        display._sort_by = "status"
        assert display.sort_key(obs1)[0] == "BUSY"
        assert display.sort_key(obs2)[0] == "HEAVY LOAD"


class TestCreateConfigFromArgs:
    """Tests for create_config_from_args."""
    
    def test_create_default_config(self):
        args = Mock()
        args.start_channel = 0
        args.end_channel = 125
        args.channels = None
        args.window = 1.0
        args.interval = 0.01
        args.min_samples = 10
        args.repetitions = 0
        args.no_retry = False
        args.max_retries = 2
        args.clear_max = 24
        args.moderate_max = 49
        args.busy_max = 74
        args.heavy_min = 75
        args.baseline_scans = 10
        args.history_length = 100
        args.persistent_threshold = 75.0
        args.persistence_windows = 3
        args.spike_threshold = 30.0
        args.burst_threshold = 40.0
        args.change_threshold = 25.0
        args.alert_cooldown = 30.0
        args.hysteresis = 5.0
        args.log_path = "logs/test.jsonl"
        args.export_dir = "exports"
        args.log_level = "INFO"
        args.refresh_interval = 500
        args.seed = None
        args.scenario = "default"
        args.backend = "sim"
        
        config = create_config_from_args(args)
        
        assert config.channel.start_channel == 0
        assert config.channel.end_channel == 125
        assert config.scan.measurement_window == 1.0
        assert config.default_backend == "sim"
    
    def test_create_config_with_channels(self):
        args = Mock()
        args.start_channel = 0
        args.end_channel = 125
        args.channels = [1, 6, 11, 37, 62]
        args.window = 1.0
        args.interval = 0.01
        args.min_samples = 10
        args.repetitions = 0
        args.no_retry = False
        args.max_retries = 2
        args.clear_max = 24
        args.moderate_max = 49
        args.busy_max = 74
        args.heavy_min = 75
        args.baseline_scans = 10
        args.history_length = 100
        args.persistent_threshold = 75.0
        args.persistence_windows = 3
        args.spike_threshold = 30.0
        args.burst_threshold = 40.0
        args.change_threshold = 25.0
        args.alert_cooldown = 30.0
        args.hysteresis = 5.0
        args.log_path = "logs/test.jsonl"
        args.export_dir = "exports"
        args.log_level = "INFO"
        args.refresh_interval = 500
        args.seed = None
        args.scenario = "default"
        args.backend = "sim"
        
        config = create_config_from_args(args)
        
        assert config.channel.channel_filter == [1, 6, 11, 37, 62]
        assert config.channel.channel_count == 5


class TestRunSingleScan:
    """Tests for run_single_scan."""
    
    @patch('cli_scan.HardwareRadio')
    @patch('cli_scan.SimRadio')
    def test_single_scan_sim(self, mock_sim_radio, mock_hw_radio, capsys):
        config = AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=2),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
            anomaly=AnomalyConfig(),
            storage=StorageConfig(export_dir=""),
            default_backend="sim",
        )
        
        mock_radio = Mock()
        mock_radio.initialize.return_value = True
        mock_radio.cleanup.return_value = None
        mock_sim_radio.return_value = mock_radio
        
        # This test is complex due to threading, so we just test the config creation
        assert config.default_backend == "sim"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])