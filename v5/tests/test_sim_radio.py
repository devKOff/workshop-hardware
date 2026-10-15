"""Unit tests for simulation radio backend."""

import pytest
import time
from sim_radio import SimRadio, ChannelModel, ChannelPattern, create_test_scenarios
from config import ChannelConfig, ScanConfig, SimulationConfig
from exceptions import SimulationError


class TestChannelModel:
    """Tests for ChannelModel behavior."""
    
    def test_default_model(self):
        model = ChannelModel(channel=10, base_probability=0.5)
        assert model.channel == 10
        assert model.base_probability == 0.5
        assert model.pattern == ChannelPattern.BACKGROUND
    
    def test_get_rpd_probability_background(self):
        model = ChannelModel(channel=5, base_probability=0.3, pattern=ChannelPattern.BACKGROUND)
        prob = model.get_rpd_probability(1000.0)
        assert 0.0 <= prob <= 1.0
        assert prob == 0.3
    
    def test_get_rpd_probability_burst(self):
        model = ChannelModel(
            channel=5,
            base_probability=0.1,
            pattern=ChannelPattern.BURST,
            burst_probability=1.0,
            burst_duration=0.5,
        )
        prob = model.get_rpd_probability(1000.0)
        assert prob == 0.9
    
    def test_get_rpd_probability_frequency_hopping(self):
        model = ChannelModel(
            channel=10,
            base_probability=0.1,
            pattern=ChannelPattern.FREQUENCY_HOPPING,
            hop_channels=[10, 20, 30],
            hop_interval=0.1,
        )
        # At time 0, should be on first hop channel (10)
        prob = model.get_rpd_probability(0.0)
        assert prob == 0.8
        
        # After hop interval, should move to next channel
        prob = model.get_rpd_probability(0.15)
        assert prob == 0.1
    
    def test_get_rpd_probability_wifi_like(self):
        model = ChannelModel(
            channel=12,
            base_probability=0.6,
            pattern=ChannelPattern.WIFI_LIKE,
        )
        prob = model.get_rpd_probability(1000.0)
        assert 0.7 <= prob <= 0.9
    
    def test_get_rpd_probability_failure(self):
        model = ChannelModel(channel=5, base_probability=0.5, failure_rate=1.0)
        prob = model.get_rpd_probability(1000.0)
        assert prob == -1.0
    
    def test_persistent_high(self):
        model = ChannelModel(
            channel=5,
            base_probability=0.5,
            pattern=ChannelPattern.PERSISTENT_HIGH,
        )
        prob = model.get_rpd_probability(1000.0)
        assert 0.85 <= prob <= 0.95
    
    def test_sudden_spike(self):
        model = ChannelModel(
            channel=5,
            base_probability=0.1,
            pattern=ChannelPattern.SUDDEN_SPIKE,
            spike_time=0.0,
            spike_duration=2.0,
        )
        prob = model.get_rpd_probability(0.5)
        assert prob == 0.95
        
        prob = model.get_rpd_probability(3.0)
        assert prob == 0.1
    
    def test_sudden_reduction(self):
        model = ChannelModel(
            channel=5,
            base_probability=0.5,
            pattern=ChannelPattern.SUDDEN_REDUCTION,
            reduction_time=0.0,
            reduction_duration=2.0,
        )
        prob = model.get_rpd_probability(0.5)
        assert prob == 0.05
        
        prob = model.get_rpd_probability(3.0)
        assert prob == 0.5


class TestSimRadio:
    """Tests for SimRadio simulation backend."""
    
    @pytest.fixture
    def config(self):
        return ChannelConfig(start_channel=0, end_channel=125)
    
    @pytest.fixture
    def scan_config(self):
        return ScanConfig(measurement_window=1.0, sampling_interval=0.01, min_valid_samples=10)
    
    def test_initialization(self, config, scan_config):
        radio = SimRadio(config, scan_config, seed=42)
        assert radio.initialize() is True
        assert radio.is_initialized() is True
        radio.cleanup()
        assert radio.is_initialized() is False
    
    def test_set_get_channel(self, config, scan_config):
        radio = SimRadio(config, scan_config, seed=42)
        radio.initialize()
        
        radio.set_channel(5)
        assert radio.get_channel() == 5
        
        radio.set_channel(10)
        assert radio.get_channel() == 10
    
    def test_invalid_channel(self, config, scan_config):
        radio = SimRadio(config, scan_config, seed=42)
        radio.initialize()
        
        with pytest.raises(SimulationError):
            radio.set_channel(-1)
        with pytest.raises(SimulationError):
            radio.set_channel(126)
    
    def test_read_rpd_before_init(self, config, scan_config):
        radio = SimRadio(config, scan_config, seed=42)
        with pytest.raises(SimulationError):
            radio.read_rpd()
    
    def test_read_rpd_returns_bool(self, config, scan_config):
        radio = SimRadio(config, scan_config, seed=42)
        radio.initialize()
        
        result = radio.read_rpd()
        assert isinstance(result, bool)
    
    def test_scan_channel(self, config, scan_config):
        radio = SimRadio(config, scan_config, seed=42)
        radio.initialize()
        
        valid, positive, negative = radio.scan_channel(12, duration=0.1, interval=0.01)
        
        assert valid >= 0
        assert positive >= 0
        assert negative >= 0
        assert valid == positive + negative
    
    def test_scan_channel_insufficient_duration(self, config, scan_config):
        radio = SimRadio(config, scan_config, seed=42)
        radio.initialize()
        
        valid, positive, negative = radio.scan_channel(5, duration=0.001, interval=0.01)
        
        assert valid == 0
    
    def test_seed_reproducibility(self, config, scan_config):
        radio1 = SimRadio(config, scan_config, seed=12345)
        radio1.initialize()
        v1, p1, n1 = radio1.scan_channel(5, duration=0.1, interval=0.01)
        
        radio2 = SimRadio(config, scan_config, seed=12345)
        radio2.initialize()
        v2, p2, n2 = radio2.scan_channel(5, duration=0.1, interval=0.01)
        
        assert v1 == v2
        assert p1 == p2
        assert n1 == n2
    
    def test_set_seed_resets_state(self, config, scan_config):
        # Two radios with same seed should produce same results
        radio1 = SimRadio(config, scan_config, seed=42)
        radio1.initialize()
        v1, p1, n1 = radio1.scan_channel(5, duration=0.1, interval=0.01)
        radio1.cleanup()
        
        radio2 = SimRadio(config, scan_config, seed=42)
        radio2.initialize()
        v2, p2, n2 = radio2.scan_channel(5, duration=0.1, interval=0.01)
        radio2.cleanup()
        
        assert v1 == v2
        assert p1 == p2
        assert n1 == n2
    
    def test_get_channel_model(self, config, scan_config):
        radio = SimRadio(config, scan_config, seed=42)
        radio.initialize()
        
        model = radio.get_channel_model(12)
        assert model is not None
        assert model.channel == 12
        
        model = radio.get_channel_model(999)
        assert model is None
    
    def test_wifi_channels_high_activity(self, config, scan_config):
        config = ChannelConfig(start_channel=10, end_channel=65)
        radio = SimRadio(config, scan_config, seed=42)
        radio.initialize()
        
        wifi_channels = [12, 37, 62]
        for ch in wifi_channels:
            model = radio.get_channel_model(ch)
            assert model.pattern == ChannelPattern.WIFI_LIKE
            assert model.base_probability >= 0.6
    
    def test_scenario_quiet(self, config, scan_config):
        radio = SimRadio(config, scan_config, 
                        simulation_config=SimulationConfig(scenario="quiet", seed=42))
        radio.initialize()
        
        v, p, n = radio.scan_channel(5, duration=0.5, interval=0.01)
        assert p / max(v, 1) < 0.1
    
    def test_scenario_moderate(self, config, scan_config):
        radio = SimRadio(config, scan_config,
                        simulation_config=SimulationConfig(scenario="moderate", seed=42))
        radio.initialize()
        
        v, p, n = radio.scan_channel(5, duration=0.5, interval=0.01)
        assert 0.15 < p / max(v, 1) < 0.5
    
    def test_scenario_persistent_busy(self, config, scan_config):
        radio = SimRadio(config, scan_config,
                        simulation_config=SimulationConfig(scenario="persistent_busy", seed=42))
        radio.initialize()
        
        v, p, n = radio.scan_channel(50, duration=0.5, interval=0.01)
        assert p / max(v, 1) > 0.8
    
    def test_get_available_scenarios(self):
        scenarios = SimRadio.get_available_scenarios()
        assert "default" in scenarios
        assert "quiet" in scenarios
        assert "persistent_busy" in scenarios
        assert len(scenarios) == 12
    
    def test_create_scenario(self, config, scan_config):
        radio = SimRadio.create_scenario("persistent_busy", config, scan_config, seed=42)
        radio.initialize()
        assert radio.is_initialized()


class TestSimRadioDeterministic:
    """Tests for deterministic simulation behavior."""
    
    def test_same_seed_same_sequence(self):
        config = ChannelConfig(start_channel=0, end_channel=125)
        scan_config = ScanConfig(measurement_window=1.0, sampling_interval=0.01)
        
        results = []
        for _ in range(3):
            radio = SimRadio(config, scan_config, seed=999)
            radio.initialize()
            v, p, n = radio.scan_channel(50, duration=0.5, interval=0.01)
            results.append((v, p, n))
            radio.cleanup()
        
        assert all(r == results[0] for r in results)
    
    def test_different_seeds_different_results(self):
        config = ChannelConfig(start_channel=0, end_channel=125)
        scan_config = ScanConfig(measurement_window=1.0, sampling_interval=0.01)
        
        radio1 = SimRadio(config, scan_config, seed=111)
        radio1.initialize()
        r1 = radio1.scan_channel(50, duration=0.5, interval=0.01)
        radio1.cleanup()
        
        radio2 = SimRadio(config, scan_config, seed=222)
        radio2.initialize()
        r2 = radio2.scan_channel(50, duration=0.5, interval=0.01)
        radio2.cleanup()
        
        assert r1 != r2


class TestCreateTestScenarios:
    """Tests for create_test_scenarios function."""
    
    def test_creates_all_scenarios(self):
        scenarios = create_test_scenarios()
        assert "quiet" in scenarios
        assert "persistent_busy" in scenarios
        assert "sudden_spike" in scenarios
        assert len(scenarios) == 10
    
    def test_scenario_structure(self):
        scenarios = create_test_scenarios()
        for name, (channel_config, scan_config, expected) in scenarios.items():
            assert isinstance(channel_config, ChannelConfig)
            assert isinstance(scan_config, ScanConfig)
            assert "expected_heavy" in expected
            assert "expected_anomalies" in expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])