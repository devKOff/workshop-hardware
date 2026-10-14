"""Unit tests for CLI scanner."""

import pytest
import sys
import io
import json
import csv
from unittest.mock import Mock, patch, MagicMock
from cli_scan import (
    CLIDisplay,
    create_config_from_args,
    run_cli_scan,
    export_json,
    export_csv,
)
from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig
from scanner import SpectrumData, ChannelObservation
import argparse


class TestCLIDisplay:
    """Tests for CLIDisplay terminal rendering."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
        )
    
    def test_render_header(self, config):
        display = CLIDisplay(config)
        lines = display.render_header("sim", 3)
        
        assert len(lines) == 7
        assert "2.4 GHz RF ACTIVITY MONITOR" in lines[1]
        assert "Backend: SIM" in lines[2]
        assert "Channels 0-5" in lines[4]
        assert "Scans completed: 3" in lines[5]
    
    def test_render_channel_with_activity(self, config):
        display = CLIDisplay(config)
        
        obs = ChannelObservation(
            timestamp=0,
            channel=12,
            frequency_mhz=2412,
            backend="sim",
            valid_samples=100,
            rpd_positive=68,
            rpd_negative=32,
            activity_percentage=68.0,
            status="Busy",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        
        line = display.render_channel(obs)
        assert "Ch  12" in line
        assert "2412 MHz" in line
        assert "68%" in line
        assert "Busy" in line
        assert "█" in line or "#" in line
    
    def test_render_channel_insufficient_data(self, config):
        display = CLIDisplay(config)
        
        obs = ChannelObservation(
            timestamp=0,
            channel=5,
            frequency_mhz=2405,
            backend="sim",
            valid_samples=5,
            rpd_positive=2,
            rpd_negative=3,
            activity_percentage=None,
            status="INSUFFICIENT DATA",
            data_sufficient=False,
            measurement_window=1.0,
            sampling_interval=0.01,
            error="Insufficient samples: 5/10",
        )
        
        line = display.render_channel(obs)
        assert "N/A" in line
        assert "INSUFFICIENT DATA" in line
        assert "insufficient data" in line.lower()
        assert "?" in line
    
    def test_render_footer(self, config):
        display = CLIDisplay(config)
        lines = display.render_footer(126)
        
        assert "Channels scanned: 126" in lines[1]
        assert "Results: Complete" in lines[2]


class TestCreateConfigFromArgs:
    """Tests for CLI argument parsing."""
    
    def test_default_args(self):
        args = argparse.Namespace(
            backend="sim",
            start_channel=0,
            end_channel=125,
            window=1.0,
            interval=0.01,
            min_samples=10,
            clear_max=24,
            moderate_max=49,
            busy_max=74,
            heavy_min=75,
            persistent_threshold=75.0,
            persistence_duration=10.0,
            consecutive_windows=3,
            alert_cooldown=30.0,
            hysteresis=5.0,
            mitigate=False,
            format="table",
            sort="channel",
            log_path="logs/countermeasures.jsonl",
            export_dir="exports",
            verbose=0,
        )
        
        config = create_config_from_args(args)
        
        assert config.default_backend == "sim"
        assert config.channel.start_channel == 0
        assert config.channel.end_channel == 125
        assert config.scan.measurement_window == 1.0
        assert config.thresholds.clear_max == 24
        assert config.mitigation.armed is False
    
    def test_custom_args(self):
        args = argparse.Namespace(
            backend="hardware",
            start_channel=10,
            end_channel=50,
            window=2.0,
            interval=0.05,
            min_samples=20,
            clear_max=20,
            moderate_max=40,
            busy_max=60,
            heavy_min=70,
            persistent_threshold=70.0,
            persistence_duration=5.0,
            consecutive_windows=2,
            alert_cooldown=10.0,
            hysteresis=3.0,
            mitigate=True,
            format="json",
            sort="activity",
            log_path="custom.log",
            export_dir="custom_exports",
            verbose=2,
        )
        
        config = create_config_from_args(args)
        
        assert config.default_backend == "hardware"
        assert config.channel.start_channel == 10
        assert config.channel.end_channel == 50
        assert config.scan.measurement_window == 2.0
        assert config.scan.sampling_interval == 0.05
        assert config.thresholds.clear_max == 20
        assert config.mitigation.armed is True


class TestExportFunctions:
    """Tests for export functions."""
    
    def test_export_json(self):
        spectrum_data = SpectrumData(AppConfig())
        
        obs = ChannelObservation(
            timestamp=1234567890.0,
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=30,
            rpd_negative=70,
            activity_percentage=30.0,
            status="Moderate",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        spectrum_data.update_observation(obs)
        
        output = io.StringIO()
        export_json(spectrum_data, AppConfig(), output)
        
        result = json.loads(output.getvalue())
        assert result["config"]["backend"] == "sim"
        assert result["scan_count"] == 0
        assert len(result["observations"]) == 1
        assert result["observations"][0]["channel"] == 10
    
    def test_export_csv(self):
        spectrum_data = SpectrumData(AppConfig())
        
        obs = ChannelObservation(
            timestamp=1234567890.0,
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=30,
            rpd_negative=70,
            activity_percentage=30.0,
            status="Moderate",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        spectrum_data.update_observation(obs)
        
        output = io.StringIO()
        export_csv(spectrum_data, AppConfig(), output)
        
        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)
        
        assert len(rows) == 1
        assert rows[0]["channel"] == "10"
        assert rows[0]["activity_percentage"] == "30.0"
        assert rows[0]["status"] == "Moderate"


class TestCLIIntegration:
    """Integration tests for CLI scanning (using simulation)."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
            mitigation=MitigationConfig(armed=False),
        )
    
    def test_run_cli_scan_sim(self, config, capsys):
        # Mock signal handlers to avoid issues in test
        with patch('cli_scan.signal.signal'):
            # We can't easily test the full run loop, but we can verify
            # the components work together
            from sim_radio import SimRadio
            from scanner import ScannerThread
            
            radio = SimRadio(config.channel, config.scan, seed=42)
            radio.initialize()
            
            spectrum_data = SpectrumData(config)
            scanner = ScannerThread(config, spectrum_data, radio)
            scanner.start()
            
            import time
            time.sleep(0.3)
            
            scanner.stop()
            radio.cleanup()
            
            observations = spectrum_data.get_all_observations()
            assert len(observations) == 6
            
            for ch in range(6):
                assert ch in observations
                obs = observations[ch]
                assert obs.valid_samples > 0
                assert obs.backend == "sim"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])