"""Tests for error handling and edge cases."""

import pytest
import tempfile
import os
import time
from pathlib import Path
from v6.exceptions import (
    RFSystemError, BlocklistError, RadioInitError, InvalidChannelError,
    ConfigurationError, ScannerError, InsufficientDataError,
    BackendError, SimulationError, HardwareError, SPIError, RadioNotFoundError,
)
from v6.config import ChannelConfig, ScanConfig, ThresholdConfig, AppConfig, SimConfig
from v6.channel_utils import validate_channel, parse_channel_input, channel_to_frequency, frequency_to_channel
from v6.blocklist_manager import BlocklistManager, BlocklistConfig
from v6.sim_radio import SimRadio, ScenarioType
from v6.scanner import ScannerThread, SpectrumData, ChannelObservation
from v6.channel_selector import ChannelSelector


class TestExceptions:
    def test_rfsystem_error(self):
        err = RFSystemError("Test error", {"detail": "info"})
        assert str(err) == "Test error"
        assert err.details == {"detail": "info"}
    
    def test_invalid_channel_error(self):
        err = InvalidChannelError(150)
        assert "150" in str(err)
        assert err.channel == 150
        assert err.min_channel == 0
        assert err.max_channel == 125
    
    def test_blocklist_error(self):
        err = BlocklistError("Blocklist failed")
        assert "Blocklist failed" in str(err)
    
    def test_exception_hierarchy(self):
        assert issubclass(BlocklistError, RFSystemError)
        assert issubclass(RadioInitError, RFSystemError)
        assert issubclass(InvalidChannelError, RFSystemError)
        assert issubclass(ConfigurationError, RFSystemError)
        assert issubclass(ScannerError, RFSystemError)
        assert issubclass(InsufficientDataError, RFSystemError)
        assert issubclass(BackendError, RFSystemError)
        assert issubclass(SimulationError, BackendError)
        assert issubclass(HardwareError, BackendError)
        assert issubclass(SPIError, HardwareError)
        assert issubclass(RadioNotFoundError, HardwareError)


class TestConfigValidation:
    def test_channel_config_valid(self):
        config = ChannelConfig(0, 125)
        assert config.start_channel == 0
        assert config.end_channel == 125
    
    def test_channel_config_invalid_start(self):
        with pytest.raises(ValueError):
            ChannelConfig(-1, 125)
        with pytest.raises(ValueError):
            ChannelConfig(126, 125)
    
    def test_channel_config_invalid_end(self):
        with pytest.raises(ValueError):
            ChannelConfig(0, -1)
        with pytest.raises(ValueError):
            ChannelConfig(0, 126)
    
    def test_channel_config_start_greater_than_end(self):
        with pytest.raises(ValueError):
            ChannelConfig(10, 5)
    
    def test_scan_config_valid(self):
        config = ScanConfig(1.0, 0.01, 10)
        assert config.measurement_window == 1.0
    
    def test_scan_config_invalid(self):
        with pytest.raises(ValueError):
            ScanConfig(-1, 0.01, 10)
        with pytest.raises(ValueError):
            ScanConfig(1.0, -0.01, 10)
        with pytest.raises(ValueError):
            ScanConfig(1.0, 0.01, 0)
    
    def test_threshold_config_valid(self):
        config = ThresholdConfig(24, 49, 74, 75)
        assert config.clear_max == 24
    
    def test_threshold_config_invalid_order(self):
        with pytest.raises(ValueError):
            ThresholdConfig(50, 49, 74, 75)  # clear > moderate
        with pytest.raises(ValueError):
            ThresholdConfig(24, 75, 74, 75)  # moderate > busy
        with pytest.raises(ValueError):
            ThresholdConfig(24, 49, 75, 74)  # busy > heavy
    
    def test_app_config_valid(self):
        config = AppConfig()
        assert config.default_backend == "sim"
    
    def test_app_config_invalid_backend(self):
        with pytest.raises(ValueError):
            AppConfig(default_backend="invalid")


class TestChannelUtilsEdgeCases:
    def test_channel_to_frequency_boundaries(self):
        assert channel_to_frequency(0) == 2400
        assert channel_to_frequency(125) == 2525
    
    def test_frequency_to_channel_boundaries(self):
        assert frequency_to_channel(2400) == 0
        assert frequency_to_channel(2525) == 125
    
    def test_parse_channel_input_variations(self):
        assert parse_channel_input("0") == 0
        assert parse_channel_input("125") == 125
        assert parse_channel_input("Ch 0") == 0
        assert parse_channel_input("CH 125") == 125
        assert parse_channel_input("ch 50") == 50
        assert parse_channel_input("2400 MHz") == 0
        assert parse_channel_input("2525 MHz") == 125
        assert parse_channel_input("  2450  MHz  ") == 50
    
    def test_parse_channel_input_errors(self):
        with pytest.raises(ValueError):
            parse_channel_input("abc")
        with pytest.raises(ValueError):
            parse_channel_input("")
        with pytest.raises(InvalidChannelError):
            parse_channel_input("126")
        with pytest.raises(InvalidChannelError):
            parse_channel_input("3000 MHz")


class TestBlocklistEdgeCases:
    def test_concurrent_access(self):
        import threading
        import time
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'[]')
            temp_path = f.name
        
        try:
            config = BlocklistConfig(file_path=temp_path)
            manager = BlocklistManager(config)
            
            errors = []
            
            def block_channels(start, count):
                try:
                    for i in range(count):
                        manager.block_channel(start + i)
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(e)
            
            threads = [
                threading.Thread(target=block_channels, args=(0, 50)),
                threading.Thread(target=block_channels, args=(50, 50)),
            ]
            
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            assert len(errors) == 0
            assert len(manager.get_blocked_channels()) == 100
        finally:
            os.unlink(temp_path)
    
    def test_atomic_write(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            config = BlocklistConfig(file_path=temp_path, atomic_writes=True)
            manager = BlocklistManager(config)
            
            manager.block_channel(10)
            
            # File should exist and be valid JSON
            assert Path(temp_path).exists()
            with open(temp_path) as f:
                data = json.load(f)
            assert len(data) == 1
        finally:
            os.unlink(temp_path)
    
    def test_non_atomic_write(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            config = BlocklistConfig(file_path=temp_path, atomic_writes=False)
            manager = BlocklistManager(config)
            
            manager.block_channel(10)
            
            assert Path(temp_path).exists()
        finally:
            os.unlink(temp_path)
    
    def test_large_blocklist(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            config = BlocklistConfig(file_path=temp_path)
            manager = BlocklistManager(config)
            
            # Block all channels
            for ch in range(126):
                manager.block_channel(ch)
            
            assert len(manager.get_blocked_channels()) == 126
            
            # Reload and verify
            manager2 = BlocklistManager(config)
            assert len(manager2.get_blocked_channels()) == 126
        finally:
            os.unlink(temp_path)
    
    def test_corrupted_file_backup(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Write corrupted JSON
            with open(temp_path, 'w') as f:
                f.write('{ invalid json }')
            
            config = BlocklistConfig(file_path=temp_path)
            with pytest.raises(BlocklistError):
                BlocklistManager(config)
            
            # Backup should exist
            backups = list(Path(temp_path).parent.glob(f"{Path(temp_path).stem}.corrupted.*.bak"))
            assert len(backups) == 1
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestSimRadioEdgeCases:
    def test_scan_channel_zero_duration(self):
        config = ChannelConfig(0, 5)
        scan_config = ScanConfig(measurement_window=0.1, sampling_interval=0.01)
        sim_config = SimConfig(seed=42)
        
        radio = SimRadio(config, scan_config, sim_config)
        radio.initialize()
        
        valid, pos, neg = radio.scan_channel(0, duration=0)
        assert valid == 0
        
        radio.cleanup()
    
    def test_scan_all_channels(self):
        config = ChannelConfig(0, 5)
        scan_config = ScanConfig(measurement_window=0.1, sampling_interval=0.01)
        sim_config = SimConfig(seed=42)
        
        radio = SimRadio(config, scan_config, sim_config)
        radio.initialize()
        
        results = {}
        for ch in range(6):
            valid, pos, neg = radio.scan_channel(ch)
            results[ch] = (valid, pos, neg)
        
        # All should have valid samples
        for ch, (v, p, n) in results.items():
            assert v > 0
            assert v == p + n
        
        radio.cleanup()
    
    def test_sensor_failure_scenario(self):
        config = ChannelConfig(0, 5)
        scan_config = ScanConfig(measurement_window=0.1, sampling_interval=0.01)
        sim_config = SimConfig(seed=42)
        
        radio = SimRadio(config, scan_config, sim_config, scenario=ScenarioType.SENSOR_ERRORS)
        radio.initialize()
        
        errors = 0
        for _ in range(100):
            try:
                radio.scan_channel(0)
            except SimulationError:
                errors += 1
        
        assert errors > 0  # Should have some sensor failures
        radio.cleanup()


class TestScannerEdgeCases:
    def test_scanner_with_failing_radio(self):
        config = AppConfig(
            channel=ChannelConfig(0, 2),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
        )
        
        class FailingRadio:
            def is_initialized(self): return True
            def scan_channel(self, *args, **kwargs):
                raise Exception("Radio failed")
            def cleanup(self): pass
        
        spectrum_data = SpectrumData(config)
        scanner = ScannerThread(config, spectrum_data, FailingRadio())
        scanner.start()
        
        import time
        time.sleep(0.3)
        scanner.stop()
        
        # Should have sensor error observations
        for ch in range(3):
            obs = spectrum_data.get_observation(ch)
            assert obs is not None
            assert obs.status == "SENSOR_ERROR"
            assert obs.error is not None
    
    def test_scanner_single_channel(self):
        config = AppConfig(
            channel=ChannelConfig(5, 5),  # Single channel
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            sim=SimConfig(seed=42),
        )
        
        radio = SimRadio(config.channel, config.scan, config.sim)
        radio.initialize()
        
        spectrum_data = SpectrumData(config)
        scanner = ScannerThread(config, spectrum_data, radio)
        scanner.start()
        
        import time
        time.sleep(0.3)
        scanner.stop()
        
        obs = spectrum_data.get_observation(5)
        assert obs is not None
        assert obs.channel == 5


class TestChannelSelectorEdgeCases:
    def test_all_channels_blocked(self):
        config = ChannelConfig(0, 5)
        thresholds = ThresholdConfig()
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            blocklist = BlocklistManager(BlocklistConfig(file_path=temp_path))
            
            # Block all channels
            for ch in range(6):
                blocklist.block_channel(ch)
            
            selector = ChannelSelector(config, thresholds, blocklist)
            
            spectrum_data = SpectrumData(AppConfig(channel=config))
            for ch in range(6):
                obs = ChannelObservation(
                    timestamp=time.time(), channel=ch, frequency_mhz=2400+ch, backend="sim",
                    valid_samples=100, rpd_positive=5, rpd_negative=95,
                    activity_percentage=5.0, status="Clear", data_sufficient=True,
                    measurement_window=1.0, sampling_interval=0.01
                )
                spectrum_data.update_observation(obs)
            
            rec = selector.recommend_channel(spectrum_data.get_all_observations())
            assert rec is None
        finally:
            os.unlink(temp_path)
    
    def test_hysteresis_boundary(self):
        config = ChannelConfig(0, 5)
        thresholds = ThresholdConfig()
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            blocklist = BlocklistManager(BlocklistConfig(file_path=temp_path))
            selector = ChannelSelector(config, thresholds, blocklist, persistent_threshold=75, hysteresis=5)
            
            # Activity at 72% - should be HIGH_ACTIVITY (72 >= 75-5=70)
            obs = ChannelObservation(
                timestamp=time.time(), channel=0, frequency_mhz=2400, backend="sim",
                valid_samples=100, rpd_positive=72, rpd_negative=28,
                activity_percentage=72.0, status="Heavy Load", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
            
            result = selector.assess_channel(0, obs)
            assert result.reason.value == "high_activity"
            
            # Activity at 69% - should be ELIGIBLE (69 < 70)
            obs2 = ChannelObservation(
                timestamp=time.time(), channel=1, frequency_mhz=2401, backend="sim",
                valid_samples=100, rpd_positive=69, rpd_negative=31,
                activity_percentage=69.0, status="Busy", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
            
            result2 = selector.assess_channel(1, obs2)
            assert result2.eligible is True
        finally:
            os.unlink(temp_path)


import json
import time

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
