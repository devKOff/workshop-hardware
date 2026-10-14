"""Unit tests for scanner module."""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch
from scanner import (
    ScannerThread,
    SpectrumData,
    ChannelObservation,
    ChannelStatus,
)
from config import (
    AppConfig,
    ChannelConfig,
    ScanConfig,
    ThresholdConfig,
    MitigationConfig,
    StorageConfig,
)
from sim_radio import SimRadio
from exceptions import ScannerError, ScannerNotRunningError, ScannerAlreadyRunningError


class TestScannerThread:
    """Tests for ScannerThread worker."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
            mitigation=MitigationConfig(),
            storage=StorageConfig(),
        )
    
    @pytest.fixture
    def spectrum_data(self, config):
        return SpectrumData(config)
    
    @pytest.fixture
    def sim_radio(self, config):
        radio = SimRadio(config.channel, config.scan, seed=42)
        radio.initialize()
        yield radio
        radio.cleanup()
    
    def test_start_stop(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        
        assert scanner.is_running() is False
        
        scanner.start()
        assert scanner.is_running() is True
        
        time.sleep(0.3)
        
        scanner.stop()
        assert scanner.is_running() is False
    
    def test_duplicate_start_raises(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        
        with pytest.raises(ScannerAlreadyRunningError):
            scanner.start()
        
        scanner.stop()
    
    def test_stop_when_not_running(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        assert scanner.stop() is True
    
    def test_shutdown(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        time.sleep(0.1)
        scanner.shutdown()
        assert scanner.is_running() is False
    
    def test_scan_all_channels(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        
        time.sleep(0.5)
        scanner.stop()
        
        observations = spectrum_data.get_all_observations()
        assert len(observations) == 6
        for ch in range(6):
            assert ch in observations
            obs = observations[ch]
            assert obs.channel == ch
            assert obs.frequency_mhz == 2400 + ch
            assert obs.backend == "sim"
            assert obs.valid_samples >= 0
    
    def test_scan_count_increments(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        
        time.sleep(0.3)
        count1 = spectrum_data.get_scan_count()
        
        time.sleep(0.3)
        count2 = spectrum_data.get_scan_count()
        
        scanner.stop()
        
        assert count2 > count1
    
    def test_observation_callback(self, config, spectrum_data, sim_radio):
        received = []
        def on_obs(obs):
            received.append(obs)
        
        scanner = ScannerThread(config, spectrum_data, sim_radio, on_observation=on_obs)
        scanner.start()
        time.sleep(0.3)
        scanner.stop()
        
        assert len(received) == 6
    
    def test_error_callback(self, config, spectrum_data):
        errors = []
        def on_error(e):
            errors.append(e)
        
        broken_radio = Mock()
        broken_radio.is_initialized.return_value = True
        broken_radio.scan_channel.side_effect = Exception("Radio error")
        
        scanner = ScannerThread(config, spectrum_data, broken_radio, on_error=on_error)
        scanner.start()
        time.sleep(0.2)
        scanner.stop()
        
        assert len(errors) > 0
    
    def test_scan_complete_callback(self, config, spectrum_data, sim_radio):
        completions = []
        def on_complete():
            completions.append(True)
        
        scanner = ScannerThread(config, spectrum_data, sim_radio, on_scan_complete=on_complete)
        scanner.start()
        time.sleep(0.3)
        scanner.stop()
        
        assert len(completions) >= 1
    
    def test_backend_property(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        assert scanner.backend == "sim"
        
        scanner.backend = "hardware"
        assert scanner.backend == "hardware"
    
    def test_change_backend_while_running_raises(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        
        with pytest.raises(ScannerError):
            scanner.backend = "hardware"
        
        scanner.stop()
    
    def test_stop_timeout(self, config, spectrum_data):
        stuck_radio = Mock()
        stuck_radio.is_initialized.return_value = True
        stuck_radio.scan_channel.side_effect = lambda *a, **k: time.sleep(10)
        
        scanner = ScannerThread(config, spectrum_data, stuck_radio)
        scanner.start()
        time.sleep(0.1)
        
        result = scanner.stop(timeout=0.1)
        assert result is False
    
    def test_spectrum_data_backend_updated(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        time.sleep(0.1)
        scanner.stop()
        
        assert spectrum_data.get_backend() == "sim"


class TestScannerThreadConcurrency:
    """Concurrency tests for ScannerThread."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=10),
            scan=ScanConfig(measurement_window=0.05, sampling_interval=0.005),
            thresholds=ThresholdConfig(),
        )
    
    def test_concurrent_readers(self, config):
        spectrum_data = SpectrumData(config)
        sim_radio = SimRadio(config.channel, config.scan, seed=42)
        sim_radio.initialize()
        
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        
        results = []
        errors = []
        
        def reader():
            try:
                for _ in range(20):
                    obs = spectrum_data.get_all_observations()
                    results.append(len(obs))
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2.0)
        
        scanner.stop()
        sim_radio.cleanup()
        
        assert len(errors) == 0
        assert all(r >= 0 for r in results)
    
    def test_snapshot_consistency(self, config):
        spectrum_data = SpectrumData(config)
        sim_radio = SimRadio(config.channel, config.scan, seed=42)
        sim_radio.initialize()
        
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        time.sleep(0.2)
        
        snapshots = []
        for _ in range(10):
            snapshots.append(spectrum_data.get_all_observations())
            time.sleep(0.01)
        
        scanner.stop()
        sim_radio.cleanup()
        
        for snap in snapshots:
            for obs in snap.values():
                assert obs.channel in config.channel.channel_range()
                assert obs.frequency_mhz == 2400 + obs.channel
                assert obs.backend == "sim"
    
    def test_repeated_start_stop_cycles(self, config):
        for _ in range(5):
            spectrum_data = SpectrumData(config)
            sim_radio = SimRadio(config.channel, config.scan, seed=42)
            sim_radio.initialize()
            
            scanner = ScannerThread(config, spectrum_data, sim_radio)
            scanner.start()
            time.sleep(0.1)
            scanner.stop()
            sim_radio.cleanup()
            
            assert scanner.is_running() is False
    
    def test_stop_during_scan(self, config):
        spectrum_data = SpectrumData(config)
        slow_radio = SimRadio(config.channel, config.scan, seed=42)
        slow_radio.initialize()
        
        scanner = ScannerThread(config, spectrum_data, slow_radio)
        scanner.start()
        time.sleep(0.05)
        scanner.stop()
        slow_radio.cleanup()
        
        assert scanner.is_running() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])