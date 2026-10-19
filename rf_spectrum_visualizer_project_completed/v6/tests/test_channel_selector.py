"""Tests for channel_selector module."""

import pytest
import tempfile
import os
from v6.channel_selector import ChannelSelector, ChannelEligibility, EligibilityReason
from v6.config import ChannelConfig, ThresholdConfig
from v6.blocklist_manager import BlocklistManager, BlocklistConfig
from v6.scanner import ChannelObservation
from v6.exceptions import InvalidChannelError


@pytest.fixture
def config():
    return ChannelConfig(0, 125)


@pytest.fixture
def thresholds():
    return ThresholdConfig(clear_max=24, moderate_max=49, busy_max=74, heavy_min=75)


@pytest.fixture
def blocklist():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('[]')
        temp_path = f.name
    config = BlocklistConfig(file_path=temp_path)
    mgr = BlocklistManager(config)
    yield mgr
    os.unlink(temp_path)


@pytest.fixture
def selector(config, thresholds, blocklist):
    return ChannelSelector(config, thresholds, blocklist)


@pytest.fixture
def sample_observations():
    """Create sample observations for testing."""
    obs = {}
    # Clear channel
    obs[0] = ChannelObservation(
        timestamp=1000.0, channel=0, frequency_mhz=2400, backend="sim",
        valid_samples=100, rpd_positive=5, rpd_negative=95,
        activity_percentage=5.0, status="Clear", data_sufficient=True,
        measurement_window=1.0, sampling_interval=0.01
    )
    # Moderate channel
    obs[10] = ChannelObservation(
        timestamp=1000.0, channel=10, frequency_mhz=2410, backend="sim",
        valid_samples=100, rpd_positive=30, rpd_negative=70,
        activity_percentage=30.0, status="Moderate", data_sufficient=True,
        measurement_window=1.0, sampling_interval=0.01
    )
    # High activity channel
    obs[20] = ChannelObservation(
        timestamp=1000.0, channel=20, frequency_mhz=2420, backend="sim",
        valid_samples=100, rpd_positive=80, rpd_negative=20,
        activity_percentage=80.0, status="Heavy Load", data_sufficient=True,
        measurement_window=1.0, sampling_interval=0.01
    )
    # Insufficient data
    obs[30] = ChannelObservation(
        timestamp=1000.0, channel=30, frequency_mhz=2430, backend="sim",
        valid_samples=5, rpd_positive=2, rpd_negative=3,
        activity_percentage=None, status="INSUFFICIENT DATA", data_sufficient=False,
        measurement_window=1.0, sampling_interval=0.01
    )
    # Sensor error
    obs[40] = ChannelObservation(
        timestamp=1000.0, channel=40, frequency_mhz=2440, backend="sim",
        valid_samples=0, rpd_positive=0, rpd_negative=0,
        activity_percentage=None, status="SENSOR_ERROR", data_sufficient=False,
        measurement_window=1.0, sampling_interval=0.01, error="Test error"
    )
    return obs


class TestChannelSelector:
    def test_assess_clear_channel(self, selector, sample_observations):
        result = selector.assess_channel(0, sample_observations[0])
        assert result.eligible is True
        assert result.reason == EligibilityReason.ELIGIBLE
        assert result.activity_percentage == 5.0
        assert result.blocked is False
    
    def test_assess_moderate_channel(self, selector, sample_observations):
        result = selector.assess_channel(10, sample_observations[10])
        assert result.eligible is True
        assert result.reason == EligibilityReason.ELIGIBLE
    
    def test_assess_high_activity_channel(self, selector, sample_observations):
        result = selector.assess_channel(20, sample_observations[20])
        assert result.eligible is False
        assert result.reason == EligibilityReason.HIGH_ACTIVITY
    
    def test_assess_insufficient_data(self, selector, sample_observations):
        result = selector.assess_channel(30, sample_observations[30])
        assert result.eligible is False
        assert result.reason == EligibilityReason.INSUFFICIENT_DATA
    
    def test_assess_sensor_error(self, selector, sample_observations):
        result = selector.assess_channel(40, sample_observations[40])
        assert result.eligible is False
        assert result.reason == EligibilityReason.SENSOR_ERROR
    
    def test_assess_blocked_channel(self, selector, blocklist, sample_observations):
        blocklist.block_channel(0)
        result = selector.assess_channel(0, sample_observations[0])
        assert result.eligible is False
        assert result.reason == EligibilityReason.BLOCKED
        assert result.blocked is True
    
    def test_assess_none_observation(self, selector):
        result = selector.assess_channel(50, None)
        assert result.eligible is False
        assert result.reason == EligibilityReason.INSUFFICIENT_DATA
    
    def test_get_eligible_channels(self, selector, sample_observations):
        eligible = selector.get_eligible_channels(sample_observations)
        eligible_channels = [e.channel for e in eligible]
        assert 0 in eligible_channels
        assert 10 in eligible_channels
        assert 20 not in eligible_channels  # High activity
        assert 30 not in eligible_channels  # Insufficient data
        assert 40 not in eligible_channels  # Sensor error
        
        # Should be sorted by activity (lowest first)
        activities = [e.activity_percentage for e in eligible]
        assert activities == sorted(activities)
    
    def test_recommend_channel(self, selector, sample_observations):
        rec = selector.recommend_channel(sample_observations)
        assert rec is not None
        assert rec.channel == 0  # Lowest activity
    
    def test_recommend_with_exclude(self, selector, sample_observations):
        rec = selector.recommend_channel(sample_observations, exclude_channels={0})
        assert rec is not None
        assert rec.channel == 10
    
    def test_recommend_none_eligible(self, selector):
        obs = {}
        for ch in range(5):
            obs[ch] = ChannelObservation(
                timestamp=1000.0, channel=ch, frequency_mhz=2400+ch, backend="sim",
                valid_samples=100, rpd_positive=80, rpd_negative=20,
                activity_percentage=80.0, status="Heavy Load", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
        rec = selector.recommend_channel(obs)
        assert rec is None
    
    def test_get_recommendations(self, selector, sample_observations):
        recs = selector.get_recommendations(sample_observations, count=3)
        assert len(recs) <= 3
        assert all(r.eligible for r in recs)
    
    def test_get_channel_ranking(self, selector, sample_observations):
        ranking = selector.get_channel_ranking(sample_observations)
        assert len(ranking) == 126
        # First should be lowest activity
        assert ranking[0][0] == 0  # Channel 0 with 5% activity
    
    def test_persistent_high_activity(self, selector, sample_observations):
        # Simulate consecutive high readings
        for _ in range(3):
            selector.assess_channel(20, sample_observations[20])
        
        result = selector.assess_channel(20, sample_observations[20])
        assert result.reason == EligibilityReason.PERSISTENT_HIGH_ACTIVITY
    
    def test_hysteresis(self, selector, sample_observations):
        # Channel at 76% with persistent_threshold=75, hysteresis=5
        # 76 >= 75 - 5 = 70, so should be HIGH_ACTIVITY
        obs = ChannelObservation(
            timestamp=1000.0, channel=50, frequency_mhz=2450, backend="sim",
            valid_samples=100, rpd_positive=76, rpd_negative=24,
            activity_percentage=76.0, status="Heavy Load", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        result = selector.assess_channel(50, obs)
        assert result.reason == EligibilityReason.HIGH_ACTIVITY
    
    def test_get_blocked_channels(self, selector, blocklist):
        blocklist.block_channel(10)
        blocklist.block_channel(20)
        blocked = selector.get_blocked_channels()
        assert blocked == [10, 20]
    
    def test_peak_tracking(self, selector, sample_observations):
        selector.assess_channel(10, sample_observations[10])  # 30%
        peak = selector.get_peak_activity(10)
        assert peak == 30.0
        
        # Higher activity
        high_obs = ChannelObservation(
            timestamp=1001.0, channel=10, frequency_mhz=2410, backend="sim",
            valid_samples=100, rpd_positive=50, rpd_negative=50,
            activity_percentage=50.0, status="Busy", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        selector.assess_channel(10, high_obs)
        peak = selector.get_peak_activity(10)
        assert peak == 50.0
    
    def test_reset_peaks(self, selector, sample_observations):
        selector.assess_channel(10, sample_observations[10])
        selector.reset_peaks()
        assert selector.get_peak_activity(10) == 0.0
    
    def test_export_assessment(self, selector, sample_observations):
        exported = selector.export_assessment(sample_observations)
        assert len(exported) == 126
        assert all("channel" in e for e in exported)
        assert all("eligible" in e for e in exported)
        assert all("reason" in e for e in exported)
    
    def test_invalid_channel(self, selector):
        with pytest.raises(InvalidChannelError):
            selector.assess_channel(-1, None)
        with pytest.raises(InvalidChannelError):
            selector.assess_channel(126, None)


class TestChannelEligibility:
    def test_to_dict(self):
        eligibility = ChannelEligibility(
            channel=122, frequency_mhz=2522, eligible=True,
            reason=EligibilityReason.ELIGIBLE, activity_percentage=5.0,
            status="Clear", data_sufficient=True, blocked=False
        )
        d = eligibility.to_dict()
        assert d["channel"] == 122
        assert d["eligible"] is True
        assert d["reason"] == "eligible"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
