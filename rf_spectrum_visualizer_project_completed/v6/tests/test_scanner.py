"""Tests for scanner module."""

import pytest
import time
from unittest.mock import Mock, MagicMock
from v6.scanner import ScannerThread, SpectrumData, ChannelObservation
from v6.config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, SimConfig
from v6.sim_radio import SimRadio
from v6.exceptions import ScannerError, ScannerAlreadyRunningError, ScannerNotRunningError


@pytest.fixture
def config():
    return AppConfig(
        channel=ChannelConfig(0, 5),
        scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01, min_valid_samples=5),
        thresholds=ThresholdConfig(),
        sim=SimConfig(seed=42, deterministic=True),
    )


@pytest.fixture
def spectrum_data(config):
    return SpectrumData(config)


@pytest.fixture
def sim_radio(config):
    radio = SimRadio(config.channel, config.scan, config.sim)
    radio.initialize()
    yield radio
    radio.cleanup()


class TestSpectrumData:
    def test_update_and_get_observation(self, spectrum_data):
        obs = ChannelObservation(
            timestamp=time.time(), channel=10, frequency_mhz=2410, backend="sim",
            valid_samples=100, rpd_positive=10, rpd_negative=90,
            activity_percentage=10.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        spectrum_data.update_observation(obs)
        
        retrieved = spectrum_data.get_observation(10)
        assert retrieved is not None
        assert retrieved.channel == 10
        assert retrieved.activity_percentage == 10.0
    
    def test_get_all_observations(self, spectrum_data):
        for ch in [0, 1, 2]:
            obs = ChannelObservation(
                timestamp=time.time(), channel=ch, frequency_mhz=2400+ch, backend="sim",
                valid_samples=100, rpd_positive=10, rpd_negative=90,
                activity_percentage=10.0, status="Clear", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
            spectrum_data.update_observation(obs)
        
        all_obs = spectrum_data.get_all_observations()
        assert len(all_obs) == 3
        assert all(ch in all_obs for ch in [0, 1, 2])
    
    def test_get_channels_in_range(self, spectrum_data):
        channels = spectrum_data.get_channels_in_range()
        assert channels == list(range(6))
    
    def test_rolling_history(self, spectrum_data):
        for i in range(5):
            obs = ChannelObservation(
                timestamp=time.time() + i, channel=10, frequency_mhz=2410, backend="sim",
                valid_samples=100, rpd_positive=10, rpd_negative=90,
                activity_percentage=10.0, status="Clear", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
            spectrum_data.update_observation(obs)
        
        history = spectrum_data.get_rolling_history(10)
        assert len(history) == 5
    
    def test_waterfall_data(self, spectrum_data):
        for ch in [0, 1, 2]:
            obs = ChannelObservation(
                timestamp=time.time(), channel=ch, frequency_mhz=2400+ch, backend="sim",
                valid_samples=100, rpd_positive=10, rpd_negative=90,
                activity_percentage=10.0, status="Clear", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
            spectrum_data.update_observation(obs)
        
        waterfall = spectrum_data.get_waterfall_data()
        assert len(waterfall) == 3
    
    def test_scan_count(self, spectrum_data):
        assert spectrum_data.get_scan_count() == 0
        spectrum_data.increment_scan_count()
        assert spectrum_data.get_scan_count() == 1
    
    def test_clear(self, spectrum_data):
        obs = ChannelObservation(
            timestamp=time.time(), channel=10, frequency_mhz=2410, backend="sim",
            valid_samples=100, rpd_positive=10, rpd_negative=90,
            activity_percentage=10.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        spectrum_data.update_observation(obs)
        spectrum_data.clear()
        
        assert spectrum_data.get_observation(10) is None
        assert spectrum_data.get_scan_count() == 0
    
    def test_export_all(self, spectrum_data):
        obs = ChannelObservation(
            timestamp=1000.0, channel=10, frequency_mhz=2410, backend="sim",
            valid_samples=100, rpd_positive=10, rpd_negative=90,
            activity_percentage=10.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        spectrum_data.update_observation(obs)
        
        exported = spectrum_data.export_all()
        assert len(exported) == 1
        assert exported[0]["channel"] == 10
        assert exported[0]["activity_percentage"] == 10.0


class TestScannerThread:
    def test_start_stop(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        
        assert not scanner.is_running()
        scanner.start()
        assert scanner.is_running()
        
        time.sleep(0.5)
        scanner.stop()
        assert not scanner.is_running()
    
    def test_start_already_running(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        
        with pytest.raises(ScannerAlreadyRunningError):
            scanner.start()
        
        scanner.stop()
    
    def test_stop_not_running(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        assert scanner.stop() is True
    
    def test_shutdown(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        scanner.shutdown()
        assert not scanner.is_running()
    
    def test_backend_property(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        assert scanner.backend == "sim"
        
        scanner.backend = "hardware"
        assert scanner.backend == "hardware"
    
    def test_backend_change_while_running(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        
        with pytest.raises(ScannerError):
            scanner.backend = "hardware"
        
        scanner.stop()
    
    def test_observation_callback(self, config, spectrum_data, sim_radio):
        observations = []
        
        def on_obs(obs):
            observations.append(obs)
        
        scanner = ScannerThread(config, spectrum_data, sim_radio, on_observation=on_obs)
        scanner.start()
        time.sleep(0.5)
        scanner.stop()
        
        assert len(observations) > 0
    
    def test_error_callback(self, config, spectrum_data):
        errors = []
        
        def on_error(e):
            errors.append(e)
        
        # Radio that always fails
        class FailingRadio:
            def is_initialized(self): return True
            def scan_channel(self, *args, **kwargs):
                raise Exception("Test error")
        
        scanner = ScannerThread(config, spectrum_data, FailingRadio(), on_error=on_error)
        scanner.start()
        time.sleep(0.5)
        scanner.stop()
        
        assert len(errors) > 0
    
    def test_scan_complete_callback(self, config, spectrum_data, sim_radio):
        scans = []
        
        def on_complete():
            scans.append(1)
        
        scanner = ScannerThread(config, spectrum_data, sim_radio, on_scan_complete=on_complete)
        scanner.start()
        time.sleep(0.5)
        scanner.stop()
        
        assert len(scans) > 0
    
    def test_observation_data_quality(self, config, spectrum_data, sim_radio):
        scanner = ScannerThread(config, spectrum_data, sim_radio)
        scanner.start()
        time.sleep(0.5)
        scanner.stop()
        
        obs = spectrum_data.get_observation(0)
        assert obs is not None
        assert obs.valid_samples >= config.scan.min_valid_samples
        assert obs.data_sufficient is True
        assert obs.activity_percentage is not None
        assert 0 <= obs.activity_percentage <= 100


class TestChannelObservation:
    def test_to_dict(self):
        obs = ChannelObservation(
            timestamp=1000.0, channel=10, frequency_mhz=2410, backend="sim",
            valid_samples=100, rpd_positive=10, rpd_negative=90,
            activity_percentage=10.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        d = obs.to_dict()
        assert d["channel"] == 10
        assert d["activity_percentage"] == 10.0
        assert d["backend"] == "sim"
    
    def test_iso_timestamp(self):
        obs = ChannelObservation(
            timestamp=1000.0, channel=10, frequency_mhz=2410, backend="sim",
            valid_samples=100, rpd_positive=10, rpd_negative=90,
            activity_percentage=10.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        iso = obs.iso_timestamp
        assert "1970" in iso or "2024" in iso or "2025" in iso or "2026" in iso


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
