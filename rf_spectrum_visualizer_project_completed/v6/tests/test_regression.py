"""Regression tests for RF Spectrum Visualizer v6."""

import pytest
import json
import tempfile
import os
from pathlib import Path
from v6.config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, BlocklistConfig, SimConfig
from v6.scanner import SpectrumData, ChannelObservation, ScannerThread
from v6.sim_radio import SimRadio, ScenarioType
from v6.blocklist_manager import BlocklistManager
from v6.channel_selector import ChannelSelector, EligibilityReason
from v6.channel_utils import validate_channel, channel_to_frequency, frequency_to_channel
from v6.report_generator import ReportGenerator


class TestRegressionV3Compatibility:
    """Ensure v6 maintains compatibility with v3 behavior."""
    
    def test_channel_frequency_mapping(self):
        """Frequency = 2400 + channel (v3 behavior)."""
        for ch in [0, 1, 12, 37, 62, 76, 77, 78, 122, 125]:
            freq = channel_to_frequency(ch)
            assert freq == 2400 + ch
    
    def test_wifi_channel_mapping(self):
        """WiFi channels map correctly."""
        # WiFi 1 (2412) -> nRF 12
        # WiFi 6 (2437) -> nRF 37
        # WiFi 11 (2462) -> nRF 62
        assert frequency_to_channel(2412) == 12
        assert frequency_to_channel(2437) == 37
        assert frequency_to_channel(2462) == 62
    
    def test_threshold_classification(self):
        """Threshold classification matches v3."""
        thresholds = ThresholdConfig()
        
        assert thresholds.classify(10) == "Clear"
        assert thresholds.classify(30) == "Moderate"
        assert thresholds.classify(60) == "Busy"
        assert thresholds.classify(80) == "Heavy Load"
        assert thresholds.classify(None) == "INSUFFICIENT DATA"
    
    def test_channel_range_126(self):
        """All 126 channels (0-125) supported."""
        config = ChannelConfig(0, 125)
        assert config.channel_count == 126
        channels = list(config.channel_range())
        assert len(channels) == 126
        assert channels[0] == 0
        assert channels[-1] == 125


class TestRegressionBlocklistPersistence:
    """Test blocklist persistence across restarts."""
    
    def test_persist_block_across_processes(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            config = BlocklistConfig(file_path=temp_path)
            
            # Process 1: Block channel
            manager1 = BlocklistManager(config)
            manager1.block_channel(122, "Test persistence")
            
            # Process 2: New manager instance
            manager2 = BlocklistManager(config)
            assert manager2.is_blocked(122)
            entry = manager2.get_entry(122)
            assert entry.reason == "Test persistence"
            
            # Process 3: Unblock
            manager3 = BlocklistManager(config)
            manager3.unblock_channel(122)
            
            # Process 4: Verify unblocked
            manager4 = BlocklistManager(config)
            assert not manager4.is_blocked(122)
        finally:
            os.unlink(temp_path)
    
    def test_blocklist_survives_crash(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            config = BlocklistConfig(file_path=temp_path)
            manager = BlocklistManager(config)
            manager.block_channel(10, "Before crash")
            manager.block_channel(20, "Before crash")
            
            # Simulate crash - new process
            manager2 = BlocklistManager(config)
            assert manager2.is_blocked(10)
            assert manager2.is_blocked(20)
        finally:
            os.unlink(temp_path)


class TestRegressionSimulationDeterminism:
    """Test simulation produces deterministic results."""
    
    def test_same_seed_same_results(self):
        config = ChannelConfig(0, 5)
        scan_config = ScanConfig(measurement_window=0.1, sampling_interval=0.01)
        sim_config = SimConfig(seed=12345, deterministic=True)
        
        radio1 = SimRadio(config, scan_config, sim_config, scenario=ScenarioType.MIXED)
        radio1.initialize()
        results1 = {}
        for ch in range(6):
            results1[ch] = radio1.scan_channel(ch)
        radio1.cleanup()
        
        radio2 = SimRadio(config, scan_config, sim_config, scenario=ScenarioType.MIXED)
        radio2.initialize()
        results2 = {}
        for ch in range(6):
            results2[ch] = radio2.scan_channel(ch)
        radio2.cleanup()
        
        assert results1 == results2
    
    def test_different_seeds_different_results(self):
        config = ChannelConfig(0, 5)
        scan_config = ScanConfig(measurement_window=0.1, sampling_interval=0.01)
        
        sim_config1 = SimConfig(seed=1, deterministic=True)
        sim_config2 = SimConfig(seed=2, deterministic=True)
        
        radio1 = SimRadio(config, scan_config, sim_config1, scenario=ScenarioType.MIXED)
        radio1.initialize()
        r1 = radio1.scan_channel(0)
        radio1.cleanup()
        
        radio2 = SimRadio(config, scan_config, sim_config2, scenario=ScenarioType.MIXED)
        radio2.initialize()
        r2 = radio2.scan_channel(0)
        radio2.cleanup()
        
        assert r1 != r2
    
    def test_scenario_channel_122_high(self):
        """Channel 122 high activity scenario."""
        config = ChannelConfig(120, 125)
        scan_config = ScanConfig(measurement_window=0.1, sampling_interval=0.01)
        sim_config = SimConfig(seed=42)
        
        radio = SimRadio(config, scan_config, sim_config, scenario=ScenarioType.CHANNEL_122_HIGH)
        radio.initialize()
        
        valid, pos, neg = radio.scan_channel(122)
        if valid >= 5:
            activity = (pos / valid) * 100
            assert activity > 70  # Should be high
        
        radio.cleanup()
    
    def test_scenario_channel_122_low(self):
        """Channel 122 low activity scenario."""
        config = ChannelConfig(120, 125)
        scan_config = ScanConfig(measurement_window=0.1, sampling_interval=0.01)
        sim_config = SimConfig(seed=42)
        
        radio = SimRadio(config, scan_config, sim_config, scenario=ScenarioType.CHANNEL_122_LOW)
        radio.initialize()
        
        valid, pos, neg = radio.scan_channel(122)
        if valid >= 5:
            activity = (pos / valid) * 100
            assert activity < 10  # Should be low
        
        radio.cleanup()


class TestRegressionChannelSelection:
    """Test channel selection algorithm."""
    
    def test_blocked_excluded_from_recommendations(self):
        config = AppConfig(
            channel=ChannelConfig(0, 5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
        )
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            spectrum_data = SpectrumData(config)
            blocklist = BlocklistManager(BlocklistConfig(file_path=temp_path))
            selector = ChannelSelector(config.channel, config.thresholds, blocklist)
            
            # Add observations - ch 0 has lowest activity
            for ch in range(6):
                obs = ChannelObservation(
                    timestamp=1000.0, channel=ch, frequency_mhz=2400+ch, backend="sim",
                    valid_samples=100, rpd_positive=10*ch, rpd_negative=100-10*ch,
                    activity_percentage=10.0*ch, status="Clear", data_sufficient=True,
                    measurement_window=1.0, sampling_interval=0.01
                )
                spectrum_data.update_observation(obs)
            
            # Initially recommend ch 0
            rec = selector.recommend_channel(spectrum_data.get_all_observations())
            assert rec.channel == 0
            
            # Block ch 0
            blocklist.block_channel(0)
            rec = selector.recommend_channel(spectrum_data.get_all_observations())
            assert rec.channel == 1
            
            # Block ch 1
            blocklist.block_channel(1)
            rec = selector.recommend_channel(spectrum_data.get_all_observations())
            assert rec.channel == 2
        finally:
            os.unlink(temp_path)
    
    def test_high_activity_excluded(self):
        config = AppConfig(
            channel=ChannelConfig(0, 5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
        )
        
        spectrum_data = SpectrumData(config)
        blocklist = BlocklistManager()
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # ch 0: low activity
        spectrum_data.update_observation(ChannelObservation(
            timestamp=1000.0, channel=0, frequency_mhz=2400, backend="sim",
            valid_samples=100, rpd_positive=5, rpd_negative=95,
            activity_percentage=5.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        ))
        
        # ch 1: high activity (above persistent threshold)
        spectrum_data.update_observation(ChannelObservation(
            timestamp=1000.0, channel=1, frequency_mhz=2401, backend="sim",
            valid_samples=100, rpd_positive=80, rpd_negative=20,
            activity_percentage=80.0, status="Heavy Load", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        ))
        
        # ch 2: moderate
        spectrum_data.update_observation(ChannelObservation(
            timestamp=1000.0, channel=2, frequency_mhz=2402, backend="sim",
            valid_samples=100, rpd_positive=30, rpd_negative=70,
            activity_percentage=30.0, status="Moderate", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        ))
        
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec.channel == 0  # Lowest activity eligible
    
    def test_insufficient_data_excluded(self):
        config = AppConfig(
            channel=ChannelConfig(0, 5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
        )
        
        spectrum_data = SpectrumData(config)
        blocklist = BlocklistManager()
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # ch 0: sufficient data, low activity
        spectrum_data.update_observation(ChannelObservation(
            timestamp=1000.0, channel=0, frequency_mhz=2400, backend="sim",
            valid_samples=100, rpd_positive=5, rpd_negative=95,
            activity_percentage=5.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        ))
        
        # ch 1: insufficient data
        spectrum_data.update_observation(ChannelObservation(
            timestamp=1000.0, channel=1, frequency_mhz=2401, backend="sim",
            valid_samples=5, rpd_positive=2, rpd_negative=3,
            activity_percentage=None, status="INSUFFICIENT DATA", data_sufficient=False,
            measurement_window=1.0, sampling_interval=0.01
        ))
        
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec.channel == 0
    
    def test_no_eligible_returns_none(self):
        config = AppConfig(
            channel=ChannelConfig(0, 5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
        )
        
        spectrum_data = SpectrumData(config)
        blocklist = BlocklistManager()
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # All channels high activity
        for ch in range(3):
            spectrum_data.update_observation(ChannelObservation(
                timestamp=1000.0, channel=ch, frequency_mhz=2400+ch, backend="sim",
                valid_samples=100, rpd_positive=80, rpd_negative=20,
                activity_percentage=80.0, status="Heavy Load", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            ))
        
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec is None


class TestRegressionExports:
    """Test export formats."""
    
    def test_json_export_structure(self):
        config = AppConfig(
            channel=ChannelConfig(0, 2),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
        )
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            spectrum_data = SpectrumData(config)
            blocklist = BlocklistManager(BlocklistConfig(file_path=temp_path))
            selector = ChannelSelector(config.channel, config.thresholds, blocklist)
            report_gen = ReportGenerator(config, spectrum_data, blocklist, selector)
            
            # Add data
            for ch in range(3):
                spectrum_data.update_observation(ChannelObservation(
                    timestamp=1000.0, channel=ch, frequency_mhz=2400+ch, backend="sim",
                    valid_samples=100, rpd_positive=10, rpd_negative=90,
                    activity_percentage=10.0, status="Clear", data_sufficient=True,
                    measurement_window=1.0, sampling_interval=0.01
                ))
            
            # Export
            output = report_gen.export_json_file("test.json")
            
            # Verify structure
            with open(output) as f:
                data = json.load(f)
            
            assert "metadata" in data
            assert "blocklist" in data
            assert "channel_assessments" in data
            assert "recommendations" in data
            assert "summary" in data
            assert len(data["channel_assessments"]) == 3
        finally:
            os.unlink(temp_path)
    
    def test_csv_export_structure(self):
        config = AppConfig(
            channel=ChannelConfig(0, 2),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
        )
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            spectrum_data = SpectrumData(config)
            blocklist = BlocklistManager(BlocklistConfig(file_path=temp_path))
            selector = ChannelSelector(config.channel, config.thresholds, blocklist)
            report_gen = ReportGenerator(config, spectrum_data, blocklist, selector)
            
            for ch in range(3):
                spectrum_data.update_observation(ChannelObservation(
                    timestamp=1000.0, channel=ch, frequency_mhz=2400+ch, backend="sim",
                    valid_samples=100, rpd_positive=10, rpd_negative=90,
                    activity_percentage=10.0, status="Clear", data_sufficient=True,
                    measurement_window=1.0, sampling_interval=0.01
                ))
            
            output = report_gen.export_csv_file("test.csv")
            
            import csv
            with open(output) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 3
            assert "channel" in rows[0]
            assert "eligible" in rows[0]
            assert "blocked" in rows[0]
        finally:
            os.unlink(temp_path)


class TestRegressionHardwareGracefulFailure:
    """Test hardware mode fails gracefully without pyrf24."""
    
    def test_hardware_radio_unavailable(self):
        """HardwareRadio should report unavailable without pyrf24."""
        config = ChannelConfig(0, 5)
        scan_config = ScanConfig()
        from v6.hardware_radio import HardwareRadio, HardwareConfig
        
        radio = HardwareRadio(config, scan_config, HardwareConfig())
        assert radio.is_available() is False
    
    def test_hardware_init_raises_clear_error(self):
        """Hardware init should raise clear error without pyrf24."""
        config = ChannelConfig(0, 5)
        scan_config = ScanConfig()
        from v6.hardware_radio import HardwareRadio, HardwareConfig
        from v6.exceptions import RadioInitError
        
        radio = HardwareRadio(config, scan_config, HardwareConfig())
        
        with pytest.raises(RadioInitError) as exc_info:
            radio.initialize()
        
        assert "pyrf24" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
