"""Unit tests for scanner module."""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock
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
    AnomalyConfig,
    StorageConfig,
)
from sim_radio import SimRadio
from exceptions import ScannerError, ScannerNotRunningError, ScannerAlreadyRunningError


class TestChannelObservation:
    """Tests for ChannelObservation."""
    
    def test_creation(self):
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
        assert obs.channel == 10
        assert obs.activity_percentage == 25.0
        assert obs.data_sufficient is True
    
    def test_to_dict(self):
        obs = ChannelObservation(
            timestamp=1000.0,
            channel=5,
            frequency_mhz=2405,
            backend="sim",
            valid_samples=50,
            rpd_positive=10,
            rpd_negative=40,
            activity_percentage=20.0,
            status="CLEAR",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        d = obs.to_dict()
        assert d["channel"] == 5
        assert d["activity_percentage"] == 20.0
        assert d["backend"] == "sim"
    
    def test_activity_bar(self):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=50,
            rpd_negative=50,
            activity_percentage=50.0,
            status="BUSY",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        bar = obs.activity_bar(20)
        assert len(bar) == 20
        assert "█" in bar
        assert "░" in bar
    
    def test_activity_bar_none(self):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=0,
            rpd_positive=0,
            rpd_negative=0,
            activity_percentage=None,
            status="INSUFFICIENT DATA",
            data_sufficient=False,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        bar = obs.activity_bar(10)
        assert bar == "?" * 10


class TestSpectrumData:
    """Tests for SpectrumData."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
            anomaly=AnomalyConfig(),
            storage=StorageConfig(),
        )
    
    @pytest.fixture
    def spectrum_data(self, config):
        return SpectrumData(config)
    
    def test_update_observation(self, spectrum_data):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=3,
            frequency_mhz=2403,
            backend="sim",
            valid_samples=100,
            rpd_positive=30,
            rpd_negative=70,
            activity_percentage=30.0,
            status="MODERATE",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        spectrum_data.update_observation(obs)
        
        retrieved = spectrum_data.get_observation(3)
        assert retrieved is not None
        assert retrieved.channel == 3
        assert retrieved.activity_percentage == 30.0
    
    def test_get_all_observations(self, spectrum_data):
        for ch in range(3):
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=ch,
                frequency_mhz=2400 + ch,
                backend="sim",
                valid_samples=100,
                rpd_positive=10,
                rpd_negative=90,
                activity_percentage=10.0,
                status="CLEAR",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
        
        all_obs = spectrum_data.get_all_observations()
        assert len(all_obs) == 3
        for ch in range(3):
            assert ch in all_obs
    
    def test_get_channels_in_range(self, spectrum_data):
        channels = spectrum_data.get_channels_in_range()
        assert channels == [0, 1, 2, 3, 4, 5]
    
    def test_rolling_history(self, spectrum_data):
        for i in range(5):
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=2,
                frequency_mhz=2402,
                backend="sim",
                valid_samples=100,
                rpd_positive=i * 10,
                rpd_negative=100 - i * 10,
                activity_percentage=float(i * 10),
                status="CLEAR",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
            time.sleep(0.01)
        
        history = spectrum_data.get_rolling_history(2)
        assert len(history) == 5
        assert history[-1].rpd_positive == 40
    
    def test_waterfall_data(self, spectrum_data):
        for ch in range(3):
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=ch,
                frequency_mhz=2400 + ch,
                backend="sim",
                valid_samples=100,
                rpd_positive=10,
                rpd_negative=90,
                activity_percentage=10.0,
                status="CLEAR",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
        
        waterfall = spectrum_data.get_waterfall_data()
        assert len(waterfall) == 3
    
    def test_scan_count(self, spectrum_data):
        assert spectrum_data.get_scan_count() == 0
        spectrum_data.increment_scan_count()
        assert spectrum_data.get_scan_count() == 1
        spectrum_data.increment_scan_count()
        assert spectrum_data.get_scan_count() == 2
    
    def test_backend(self, spectrum_data):
        spectrum_data.set_backend("hardware")
        assert spectrum_data.get_backend() == "hardware"
    
    def test_failed_channels(self, spectrum_data):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=5,
            frequency_mhz=2405,
            backend="sim",
            valid_samples=0,
            rpd_positive=0,
            rpd_negative=0,
            activity_percentage=None,
            status="SENSOR_ERROR",
            data_sufficient=False,
            measurement_window=1.0,
            sampling_interval=0.01,
            error="Radio error",
        )
        spectrum_data.update_observation(obs)
        
        failed = spectrum_data.get_failed_channels()
        assert 5 in failed
        assert failed[5] == "Radio error"
    
    def test_clear(self, spectrum_data):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=1,
            frequency_mhz=2401,
            backend="sim",
            valid_samples=100,
            rpd_positive=10,
            rpd_negative=90,
            activity_percentage=10.0,
            status="CLEAR",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        spectrum_data.update_observation(obs)
        spectrum_data.increment_scan_count()
        
        spectrum_data.clear()
        
        assert spectrum_data.get_scan_count() == 0
        assert len(spectrum_data.get_all_observations()) == 0
    
    def test_scan_timing(self, spectrum_data):
        spectrum_data.set_scan_start()
        time.sleep(0.01)
        spectrum_data.set_scan_complete(1.5)
        
        assert spectrum_data.get_last_scan_duration() == 1.5
        history = spectrum_data.get_scan_history()
        assert len(history) == 1
        assert history[0]["duration"] == 1.5


class TestScannerThread:
    """Tests for ScannerThread worker."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
            anomaly=AnomalyConfig(),
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
        
        time.sleep(1.0)
        count1 = spectrum_data.get_scan_count()
        
        time.sleep(1.0)
        count2 = spectrum_data.get_scan_count()
        
        scanner.stop()
        
        assert count2 > count1
    
    def test_observation_callback(self, config, spectrum_data, sim_radio):
        received = []
        def on_obs(obs):
            received.append(obs)
        
        # Use scan_repetitions=1 to run exactly one scan
        config.scan.scan_repetitions = 1
        
        scanner = ScannerThread(config, spectrum_data, sim_radio, on_observation=on_obs)
        scanner.start()
        time.sleep(0.5)
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
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
            anomaly=AnomalyConfig(),
            storage=StorageConfig(),
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