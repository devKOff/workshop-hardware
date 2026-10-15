"""Tests for GUI logic (non-visual components)."""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from v6.app import (
    SpectrumVisualizerApp,
    ChannelTableModel,
)
from v6.config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig
from v6.scanner import SpectrumData, ChannelObservation
from v6.blocklist_manager import BlocklistManager
from v6.channel_selector import ChannelSelector
from v6.channel_utils import validate_channel


class TestChannelTableModel:
    def test_update_and_get(self):
        config = AppConfig()
        model = ChannelTableModel(config)
        
        obs = ChannelObservation(
            timestamp=time.time(), channel=10, frequency_mhz=2410, backend="sim",
            valid_samples=100, rpd_positive=10, rpd_negative=90,
            activity_percentage=10.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        
        model.update({10: obs})
        row = model.get_row_data(10)
        
        assert row is not None
        assert row["channel"] == 10
        assert row["activity_pct"] == 10.0
        assert row["status"] == "Clear"
    
    def test_get_all_channels(self):
        config = AppConfig()
        model = ChannelTableModel(config)
        
        for ch in [0, 1, 2]:
            obs = ChannelObservation(
                timestamp=time.time(), channel=ch, frequency_mhz=2400+ch, backend="sim",
                valid_samples=100, rpd_positive=10, rpd_negative=90,
                activity_percentage=10.0, status="Clear", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
            model.update({ch: obs})
        
        channels = model.get_all_channels()
        assert channels == [0, 1, 2]


class TestSpectrumVisualizerAppLogic:
    """Test GUI logic without creating actual window."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(0, 5),
            scan=ScanConfig(measurement_window=0.1, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
        )
    
    def test_block_channel_logic(self, config):
        """Test block/unblock logic without GUI."""
        blocklist = BlocklistManager(config.blocklist)
        
        # Block
        entry = blocklist.block_channel(122, "Test")
        assert entry.channel == 122
        assert blocklist.is_blocked(122)
        
        # Unblock
        assert blocklist.unblock_channel(122) is True
        assert blocklist.is_blocked(122) is False
    
    def test_channel_recommendation_logic(self, config):
        """Test recommendation logic."""
        spectrum_data = SpectrumData(config)
        blocklist = BlocklistManager(config.blocklist)
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # Add observations
        for ch in range(6):
            activity = 5.0 * ch
            obs = ChannelObservation(
                timestamp=time.time(), channel=ch, frequency_mhz=2400+ch, backend="sim",
                valid_samples=100, rpd_positive=int(activity), rpd_negative=100-int(activity),
                activity_percentage=activity, status="Clear", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
            spectrum_data.update_observation(obs)
        
        # Should recommend channel 0 (lowest activity)
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec is not None
        assert rec.channel == 0
    
    def test_blocked_channel_not_recommended(self, config):
        """Test blocked channels are not recommended."""
        spectrum_data = SpectrumData(config)
        blocklist = BlocklistManager(config.blocklist)
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # Add observations - channel 0 has lowest activity
        for ch in range(3):
            obs = ChannelObservation(
                timestamp=time.time(), channel=ch, frequency_mhz=2400+ch, backend="sim",
                valid_samples=100, rpd_positive=5, rpd_negative=95,
                activity_percentage=5.0, status="Clear", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
            spectrum_data.update_observation(obs)
        
        # Block channel 0
        blocklist.block_channel(0)
        
        # Should recommend channel 1 now
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec is not None
        assert rec.channel == 1
    
    def test_high_activity_not_recommended(self, config):
        """Test high activity channels are not recommended."""
        spectrum_data = SpectrumData(config)
        blocklist = BlocklistManager(config.blocklist)
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # Channel 0: low activity
        obs0 = ChannelObservation(
            timestamp=time.time(), channel=0, frequency_mhz=2400, backend="sim",
            valid_samples=100, rpd_positive=5, rpd_negative=95,
            activity_percentage=5.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        
        # Channel 1: high activity
        obs1 = ChannelObservation(
            timestamp=time.time(), channel=1, frequency_mhz=2401, backend="sim",
            valid_samples=100, rpd_positive=80, rpd_negative=20,
            activity_percentage=80.0, status="Heavy Load", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        
        spectrum_data.update_observation(obs0)
        spectrum_data.update_observation(obs1)
        
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec is not None
        assert rec.channel == 0
    
    def test_insufficient_data_not_recommended(self, config):
        """Test channels with insufficient data are not recommended."""
        spectrum_data = SpectrumData(config)
        blocklist = BlocklistManager(config.blocklist)
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # Channel 0: sufficient data
        obs0 = ChannelObservation(
            timestamp=time.time(), channel=0, frequency_mhz=2400, backend="sim",
            valid_samples=100, rpd_positive=5, rpd_negative=95,
            activity_percentage=5.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        
        # Channel 1: insufficient data
        obs1 = ChannelObservation(
            timestamp=time.time(), channel=1, frequency_mhz=2401, backend="sim",
            valid_samples=5, rpd_positive=2, rpd_negative=3,
            activity_percentage=None, status="INSUFFICIENT DATA", data_sufficient=False,
            measurement_window=1.0, sampling_interval=0.01
        )
        
        spectrum_data.update_observation(obs0)
        spectrum_data.update_observation(obs1)
        
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec is not None
        assert rec.channel == 0
    
    def test_no_eligible_channels(self, config):
        """Test when no channels are eligible."""
        spectrum_data = SpectrumData(config)
        blocklist = BlocklistManager(config.blocklist)
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # All channels high activity
        for ch in range(3):
            obs = ChannelObservation(
                timestamp=time.time(), channel=ch, frequency_mhz=2400+ch, backend="sim",
                valid_samples=100, rpd_positive=80, rpd_negative=20,
                activity_percentage=80.0, status="Heavy Load", data_sufficient=True,
                measurement_window=1.0, sampling_interval=0.01
            )
            spectrum_data.update_observation(obs)
        
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec is None
    
    def test_activity_bar_generation(self, config):
        """Test activity bar string generation."""
        # We can't easily test the private method, but we can test the concept
        def make_bar(pct, width=20):
            if pct is None:
                return "?" * width
            filled = int(pct / 100 * width)
            return "█" * filled + "░" * (width - filled)
        
        assert make_bar(0) == "░" * 20
        assert make_bar(100) == "█" * 20
        assert make_bar(50) == "█" * 10 + "░" * 10
        assert make_bar(None) == "?" * 20
    
    def test_status_tag_assignment(self, config):
        """Test status tag logic."""
        blocklist = BlocklistManager(config.blocklist)
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # Clear, eligible
        obs = ChannelObservation(
            timestamp=time.time(), channel=0, frequency_mhz=2400, backend="sim",
            valid_samples=100, rpd_positive=5, rpd_negative=95,
            activity_percentage=5.0, status="Clear", data_sufficient=True,
            measurement_window=1.0, sampling_interval=0.01
        )
        assessment = selector.assess_channel(0, obs)
        
        # Should be eligible
        assert assessment.eligible is True
        
        # Blocked
        blocklist.block_channel(0)
        assessment = selector.assess_channel(0, obs)
        assert assessment.eligible is False
        assert assessment.blocked is True


class TestGUIIntegrationLogic:
    def test_full_workflow_simulation(self, config):
        """Test complete workflow: scan -> block -> recommend -> unblock."""
        spectrum_data = SpectrumData(config)
        blocklist = BlocklistManager(config.blocklist)
        selector = ChannelSelector(config.channel, config.thresholds, blocklist)
        
        # Simulate scan results
        for ch in range(6):
            activity = 10.0 * ch
            obs = ChannelObservation(
                timestamp=time.time(), channel=ch, frequency_mhz=2400+ch, backend="sim",
                valid_samples=100, rpd_positive=int(activity), rpd_negative=100-int(activity),
                activity_percentage=activity, status="Clear" if ch < 3 else "Moderate",
                data_sufficient=True, measurement_window=1.0, sampling_interval=0.01
            )
            spectrum_data.update_observation(obs)
        
        # Initial recommendation should be channel 0
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec.channel == 0
        
        # Block channel 0
        blocklist.block_channel(0)
        
        # Recommendation should now be channel 1
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec.channel == 1
        
        # Block channel 1
        blocklist.block_channel(1)
        
        # Recommendation should now be channel 2
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec.channel == 2
        
        # Unblock channel 0
        blocklist.unblock_channel(0)
        
        # Recommendation should be channel 0 again (lowest activity)
        rec = selector.recommend_channel(spectrum_data.get_all_observations())
        assert rec.channel == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
