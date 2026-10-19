"""Unit tests for spectrum data structures."""

import pytest
import time
from scanner import ChannelObservation, SpectrumData
from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig


class TestChannelObservation:
    """Tests for ChannelObservation dataclass."""
    
    def test_creation_with_activity(self):
        obs = ChannelObservation(
            timestamp=time.time(),
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
        assert obs.channel == 12
        assert obs.activity_percentage == 68.0
        assert obs.status == "Busy"
        assert obs.data_sufficient is True
    
    def test_creation_insufficient_data(self):
        obs = ChannelObservation(
            timestamp=time.time(),
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
        assert obs.activity_percentage is None
        assert obs.status == "INSUFFICIENT DATA"
        assert obs.data_sufficient is False
    
    def test_to_dict(self):
        obs = ChannelObservation(
            timestamp=1234567890.0,
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=50,
            rpd_positive=10,
            rpd_negative=40,
            activity_percentage=20.0,
            status="Clear",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        d = obs.to_dict()
        assert d["channel"] == 10
        assert d["frequency_mhz"] == 2410
        assert d["activity_percentage"] == 20.0
        assert d["backend"] == "sim"
    
    def test_iso_timestamp(self):
        obs = ChannelObservation(
            timestamp=1234567890.0,
            channel=0,
            frequency_mhz=2400,
            backend="sim",
            valid_samples=10,
            rpd_positive=0,
            rpd_negative=10,
            activity_percentage=0.0,
            status="Clear",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        iso = obs.iso_timestamp
        assert "1970" not in iso  # Not epoch
        assert "T" in iso


class TestSpectrumData:
    """Tests for SpectrumData thread-safe storage."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
        )
    
    @pytest.fixture
    def spectrum_data(self, config):
        return SpectrumData(config)
    
    def test_initial_state(self, spectrum_data):
        assert spectrum_data.get_backend() == "unknown"
        assert spectrum_data.get_scan_count() == 0
        assert spectrum_data.get_all_observations() == {}
        assert spectrum_data.get_channels_in_range() == list(range(6))
    
    def test_set_backend(self, spectrum_data):
        spectrum_data.set_backend("sim")
        assert spectrum_data.get_backend() == "sim"
    
    def test_update_and_get_observation(self, spectrum_data):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=3,
            frequency_mhz=2403,
            backend="sim",
            valid_samples=100,
            rpd_positive=50,
            rpd_negative=50,
            activity_percentage=50.0,
            status="Busy",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        spectrum_data.update_observation(obs)
        
        retrieved = spectrum_data.get_observation(3)
        assert retrieved is not None
        assert retrieved.channel == 3
        assert retrieved.activity_percentage == 50.0
        # Verify it's a copy
        retrieved.activity_percentage = 99.0
        assert spectrum_data.get_observation(3).activity_percentage == 50.0
    
    def test_get_all_observations(self, spectrum_data):
        for ch in range(3):
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=ch,
                frequency_mhz=2400 + ch,
                backend="sim",
                valid_samples=100,
                rpd_positive=ch * 10,
                rpd_negative=100 - ch * 10,
                activity_percentage=float(ch * 10),
                status="Clear",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
        
        all_obs = spectrum_data.get_all_observations()
        assert len(all_obs) == 3
        assert all_obs[0].activity_percentage == 0.0
        assert all_obs[2].activity_percentage == 20.0
    
    def test_rolling_history(self, spectrum_data):
        for i in range(5):
            obs = ChannelObservation(
                timestamp=time.time() + i,
                channel=1,
                frequency_mhz=2401,
                backend="sim",
                valid_samples=100,
                rpd_positive=i * 10,
                rpd_negative=100 - i * 10,
                activity_percentage=float(i * 10),
                status="Clear",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
        
        history = spectrum_data.get_rolling_history(1)
        assert len(history) == 5
        assert history[0].activity_percentage == 0.0
        assert history[4].activity_percentage == 40.0
    
    def test_rolling_history_bounded(self, spectrum_data):
        config = AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=1),
            scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
        )
        config.storage.rolling_history_size = 3
        sd = SpectrumData(config)
        
        for i in range(10):
            obs = ChannelObservation(
                timestamp=time.time() + i,
                channel=0,
                frequency_mhz=2400,
                backend="sim",
                valid_samples=100,
                rpd_positive=i,
                rpd_negative=100 - i,
                activity_percentage=float(i),
                status="Clear",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            sd.update_observation(obs)
        
        history = sd.get_rolling_history(0)
        assert len(history) == 3
        assert history[0].activity_percentage == 7.0
        assert history[2].activity_percentage == 9.0
    
    def test_waterfall_history(self, spectrum_data):
        for i in range(3):
            obs = ChannelObservation(
                timestamp=time.time() + i,
                channel=i,
                frequency_mhz=2400 + i,
                backend="sim",
                valid_samples=100,
                rpd_positive=10,
                rpd_negative=90,
                activity_percentage=10.0,
                status="Clear",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
        
        waterfall = spectrum_data.get_waterfall_data()
        assert len(waterfall) == 3
    
    def test_waterfall_filter_by_age(self, spectrum_data):
        now = time.time()
        for i in range(5):
            obs = ChannelObservation(
                timestamp=now - 100 + i * 10,
                channel=0,
                frequency_mhz=2400,
                backend="sim",
                valid_samples=100,
                rpd_positive=10,
                rpd_negative=90,
                activity_percentage=10.0,
                status="Clear",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            spectrum_data.update_observation(obs)
        
        recent = spectrum_data.get_waterfall_data(max_age=30)
        assert len(recent) == 3
    
    def test_clear(self, spectrum_data):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=0,
            frequency_mhz=2400,
            backend="sim",
            valid_samples=100,
            rpd_positive=50,
            rpd_negative=50,
            activity_percentage=50.0,
            status="Busy",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        spectrum_data.update_observation(obs)
        spectrum_data.increment_scan_count()
        
        spectrum_data.clear()
        
        assert spectrum_data.get_all_observations() == {}
        assert spectrum_data.get_scan_count() == 0
        assert spectrum_data.get_waterfall_data() == []
    
    def test_export_all(self, spectrum_data):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=1,
            frequency_mhz=2401,
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
        
        exported = spectrum_data.export_all()
        assert len(exported) == 1
        assert exported[0]["channel"] == 1
        assert exported[0]["activity_percentage"] == 30.0


class TestChannelConfig:
    """Tests for ChannelConfig validation."""
    
    def test_valid_range(self):
        config = ChannelConfig(start_channel=0, end_channel=125)
        assert config.channel_count == 126
        assert list(config.channel_range()) == list(range(126))
    
    def test_custom_range(self):
        config = ChannelConfig(start_channel=10, end_channel=20)
        assert config.channel_count == 11
        assert list(config.channel_range()) == list(range(10, 21))
    
    def test_invalid_start(self):
        with pytest.raises(ValueError):
            ChannelConfig(start_channel=-1, end_channel=10)
        with pytest.raises(ValueError):
            ChannelConfig(start_channel=126, end_channel=125)
    
    def test_invalid_end(self):
        with pytest.raises(ValueError):
            ChannelConfig(start_channel=0, end_channel=126)
    
    def test_start_greater_than_end(self):
        with pytest.raises(ValueError):
            ChannelConfig(start_channel=50, end_channel=40)


class TestScanConfig:
    """Tests for ScanConfig validation."""
    
    def test_valid_config(self):
        config = ScanConfig(measurement_window=1.0, sampling_interval=0.01, min_valid_samples=10)
        assert config.expected_samples_per_channel == 100
    
    def test_invalid_window(self):
        with pytest.raises(ValueError):
            ScanConfig(measurement_window=0, sampling_interval=0.01)
        with pytest.raises(ValueError):
            ScanConfig(measurement_window=-1, sampling_interval=0.01)
    
    def test_invalid_interval(self):
        with pytest.raises(ValueError):
            ScanConfig(measurement_window=1.0, sampling_interval=0)
        with pytest.raises(ValueError):
            ScanConfig(measurement_window=1.0, sampling_interval=-0.01)
    
    def test_invalid_min_samples(self):
        with pytest.raises(ValueError):
            ScanConfig(measurement_window=1.0, sampling_interval=0.01, min_valid_samples=0)


class TestThresholdConfig:
    """Tests for ThresholdConfig validation and classification."""
    
    def test_valid_thresholds(self):
        config = ThresholdConfig(clear_max=24, moderate_max=49, busy_max=74, heavy_min=75)
        assert config.classify(10) == "Clear"
        assert config.classify(30) == "Moderate"
        assert config.classify(60) == "Busy"
        assert config.classify(80) == "Heavy Load"
        assert config.classify(None) == "INSUFFICIENT DATA"
    
    def test_boundary_values(self):
        config = ThresholdConfig(clear_max=24, moderate_max=49, busy_max=74, heavy_min=75)
        assert config.classify(24) == "Clear"
        assert config.classify(25) == "Moderate"
        assert config.classify(49) == "Moderate"
        assert config.classify(50) == "Busy"
        assert config.classify(74) == "Busy"
        assert config.classify(75) == "Heavy Load"
        assert config.classify(100) == "Heavy Load"
    
    def test_invalid_ordering(self):
        with pytest.raises(ValueError):
            ThresholdConfig(clear_max=30, moderate_max=20, busy_max=70, heavy_min=80)
        with pytest.raises(ValueError):
            ThresholdConfig(clear_max=24, moderate_max=49, busy_max=74, heavy_min=70)
        with pytest.raises(ValueError):
            ThresholdConfig(clear_max=-1, moderate_max=49, busy_max=74, heavy_min=75)
        with pytest.raises(ValueError):
            ThresholdConfig(clear_max=24, moderate_max=49, busy_max=74, heavy_min=101)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])