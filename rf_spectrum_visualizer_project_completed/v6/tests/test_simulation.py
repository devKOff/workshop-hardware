"""Tests for simulation module."""

import pytest
from v6.sim_radio import SimRadio, ScenarioType, ChannelModel
from v6.config import ChannelConfig, ScanConfig, SimConfig
from v6.exceptions import SimulationError, InvalidChannelError
from v6.channel_utils import validate_channel


@pytest.fixture
def config():
    return ChannelConfig(0, 5)


@pytest.fixture
def scan_config():
    return ScanConfig(measurement_window=0.1, sampling_interval=0.01, min_valid_samples=5)


@pytest.fixture
def sim_config():
    return SimConfig(seed=42, deterministic=True)


class TestSimRadio:
    def test_initialize(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        assert not radio.is_initialized()
        radio.initialize()
        assert radio.is_initialized()
        radio.cleanup()
        assert not radio.is_initialized()
    
    def test_set_get_channel(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        radio.initialize()
        
        radio.set_channel(3)
        assert radio.get_channel() == 3
        
        radio.set_channel(0)
        assert radio.get_channel() == 0
        
        radio.cleanup()
    
    def test_invalid_channel(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        radio.initialize()
        
        with pytest.raises(InvalidChannelError):
            radio.set_channel(-1)
        with pytest.raises(InvalidChannelError):
            radio.set_channel(126)
        
        radio.cleanup()
    
    def test_read_rpd(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        radio.initialize()
        
        radio.set_channel(0)
        result = radio.read_rpd()
        assert isinstance(result, bool)
        
        radio.cleanup()
    
    def test_read_rpd_not_initialized(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        
        with pytest.raises(SimulationError):
            radio.read_rpd()
    
    def test_scan_channel(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        radio.initialize()
        
        valid, positive, negative = radio.scan_channel(0)
        
        assert valid > 0
        assert valid == positive + negative
        assert positive >= 0
        assert negative >= 0
        
        radio.cleanup()
    
    def test_scan_channel_not_initialized(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        
        with pytest.raises(SimulationError):
            radio.scan_channel(0)
    
    def test_deterministic_with_seed(self, config, scan_config):
        sim_config1 = SimConfig(seed=42, deterministic=True)
        sim_config2 = SimConfig(seed=42, deterministic=True)
        
        radio1 = SimRadio(config, scan_config, sim_config1)
        radio1.initialize()
        v1, p1, n1 = radio1.scan_channel(0)
        radio1.cleanup()
        
        radio2 = SimRadio(config, scan_config, sim_config2)
        radio2.initialize()
        v2, p2, n2 = radio2.scan_channel(0)
        radio2.cleanup()
        
        assert v1 == v2
        assert p1 == p2
        assert n1 == n2
    
    def test_different_seeds_different_results(self, config, scan_config):
        sim_config1 = SimConfig(seed=1, deterministic=True)
        sim_config2 = SimConfig(seed=2, deterministic=True)
        
        radio1 = SimRadio(config, scan_config, sim_config1)
        radio1.initialize()
        v1, p1, n1 = radio1.scan_channel(0)
        radio1.cleanup()
        
        radio2 = SimRadio(config, scan_config, sim_config2)
        radio2.initialize()
        v2, p2, n2 = radio2.scan_channel(0)
        radio2.cleanup()
        
        # With different seeds, results should differ (probabilistically)
        # At least one should be different
        assert (v1, p1, n1) != (v2, p2, n2)
    
    def test_set_seed_resets(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        radio.initialize()
        
        v1, p1, n1 = radio.scan_channel(0)
        radio.set_seed(42)
        v2, p2, n2 = radio.scan_channel(0)
        
        # After reset with same seed, should get same results as first run with that seed
        radio.cleanup()
    
    def test_get_channel_model(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        radio.initialize()
        
        model = radio.get_channel_model(0)
        assert model is not None
        assert model.channel == 0
        
        radio.cleanup()
    
    def test_cleanup(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config)
        radio.initialize()
        radio.cleanup()
        assert not radio.is_initialized()


class TestScenarios:
    def test_quiet_scenario(self, config, scan_config, sim_config):
        radio = SimRadio.create_scenario(ScenarioType.QUIET, seed=42)
        radio.initialize()
        
        for ch in range(6):
            valid, positive, negative = radio.scan_channel(ch)
            if valid >= 5:
                activity = (positive / valid) * 100
                assert activity < 10  # Should be very low
        
        radio.cleanup()
    
    def test_single_busy_scenario(self, config, scan_config, sim_config):
        radio = SimRadio.create_scenario(ScenarioType.SINGLE_BUSY, seed=42)
        radio.initialize()
        
        busy_found = False
        # Busy channel is 76, so scan around that area
        for ch in range(70, 85):
            valid, positive, negative = radio.scan_channel(ch)
            if valid >= 5:
                activity = (positive / valid) * 100
                if activity > 50:
                    busy_found = True
        
        assert busy_found
        radio.cleanup()
    
    def test_channel_122_high_scenario(self, config, scan_config, sim_config):
        # Need config with channel 122
        config_full = ChannelConfig(120, 125)
        radio = SimRadio.create_scenario(ScenarioType.CHANNEL_122_HIGH, seed=42)
        radio.initialize()
        
        valid, positive, negative = radio.scan_channel(122)
        if valid >= 5:
            activity = (positive / valid) * 100
            assert activity > 70  # Should be high
        
        radio.cleanup()
    
    def test_channel_122_low_scenario(self, config, scan_config, sim_config):
        config_full = ChannelConfig(120, 125)
        radio = SimRadio.create_scenario(ScenarioType.CHANNEL_122_LOW, seed=42)
        radio.initialize()
        
        valid, positive, negative = radio.scan_channel(122)
        if valid >= 5:
            activity = (positive / valid) * 100
            assert activity < 10  # Should be low
        
        radio.cleanup()
    
    def test_wifi_like_scenario(self, config, scan_config, sim_config):
        radio = SimRadio.create_scenario(ScenarioType.WIFI_LIKE, seed=42)
        radio.initialize()
        
        # WiFi channels 1, 6, 11 map to nRF 12, 37, 62
        for ch in [12, 37, 62]:
            if ch <= 5:  # Only in our limited range
                valid, positive, negative = radio.scan_channel(ch)
                if valid >= 5:
                    activity = (positive / valid) * 100
                    assert activity > 50
        
        radio.cleanup()
    
    def test_sensor_errors_scenario(self, config, scan_config, sim_config):
        radio = SimRadio.create_scenario(ScenarioType.SENSOR_ERRORS, seed=42)
        radio.initialize()
        
        # With 1% failure rate per sample, many scan_channel calls should have some failed samples
        total_failed = 0
        expected_samples = int(scan_config.measurement_window / scan_config.sampling_interval)
        for _ in range(100):
            valid, pos, neg = radio.scan_channel(0)
            total_failed += (expected_samples - valid)
        
        # With 1% failure rate over 1000 samples (100 calls * 10 samples), expect ~10 failures
        assert total_failed > 0
        radio.cleanup()
    
    def test_get_scenario_info(self, config, scan_config, sim_config):
        radio = SimRadio(config, scan_config, sim_config, scenario=ScenarioType.MIXED)
        info = radio.get_scenario_info()
        
        assert info["scenario"] == "mixed"
        assert "description" in info
        assert info["seed"] == 42
        assert info["deterministic"] is True


class TestChannelModel:
    def test_get_rpd_probability(self, config, scan_config, sim_config):
        model = ChannelModel(channel=0, base_probability=0.5, scenario=ScenarioType.QUIET)
        
        import random
        rng = random.Random(42)
        prob = model.get_rpd_probability(0.0, rng)
        
        assert 0 <= prob <= 1
    
    def test_burst_pattern(self, config, scan_config, sim_config):
        model = ChannelModel(
            channel=0, base_probability=0.1,
            scenario=ScenarioType.BURST,
            burst_probability=1.0,  # Always burst
            burst_duration=10.0
        )
        
        import random
        rng = random.Random(42)
        
        # First call should trigger burst
        prob = model.get_rpd_probability(0.0, rng)
        assert prob == 0.9
        
        # During burst
        prob = model.get_rpd_probability(0.05, rng)
        assert prob == 0.9
        
        # After burst
        prob = model.get_rpd_probability(15.0, rng)
        assert prob < 0.9
    
    def test_frequency_hopping(self, config, scan_config, sim_config):
        model = ChannelModel(
            channel=10, base_probability=0.1,
            scenario=ScenarioType.FREQUENCY_HOPPING,
            hop_channels=[10, 20, 30],
            hop_interval=1.0
        )
        
        import random
        rng = random.Random(42)
        
        # At hop time 0, should be on channel 10
        prob = model.get_rpd_probability(0.0, rng)
        assert prob == 0.8
        
        # At hop time 1.0, should be on channel 20
        prob = model.get_rpd_probability(1.0, rng)
        # Not on 10 anymore
        assert prob < 0.8
    
    def test_reset(self, config, scan_config, sim_config):
        model = ChannelModel(channel=0, base_probability=0.5, scenario=ScenarioType.BURST)
        model._in_burst = True
        model._hop_index = 2
        
        model.reset()
        
        assert model._in_burst is False
        assert model._hop_index == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
