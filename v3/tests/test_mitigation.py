"""Unit tests for mitigation engine."""

import pytest
import time
from mitigation import (
    MitigationEngine,
    MitigationState,
    ChannelAlert,
    MitigationEvent,
)
from config import (
    MitigationConfig,
    ThresholdConfig,
    ChannelConfig,
    AppConfig,
    ScanConfig,
)
from scanner import ChannelObservation, ChannelStatus


class TestMitigationEngine:
    """Tests for MitigationEngine."""
    
    @pytest.fixture
    def configs(self):
        mitigation = MitigationConfig(
            persistent_threshold=75.0,
            persistence_duration=0.1,
            consecutive_windows=2,
            alert_cooldown=0.1,
            hysteresis=5.0,
            armed=True,
        )
        thresholds = ThresholdConfig()
        channels = ChannelConfig(start_channel=0, end_channel=125)
        return mitigation, thresholds, channels
    
    @pytest.fixture
    def engine(self, configs):
        mitigation, thresholds, channels = configs
        return MitigationEngine(mitigation, thresholds, channels)
    
    def test_initial_state_disarmed(self, engine):
        assert engine.state == MitigationState.DISARMED
        assert engine.is_armed() is False
    
    def test_arm_disarm(self, engine):
        engine.arm()
        assert engine.state == MitigationState.ARMED
        assert engine.is_armed() is True
        
        engine.disarm()
        assert engine.state == MitigationState.DISARMED
        assert engine.is_armed() is False
    
    def test_disarm_clears_alerts(self, engine):
        engine.arm()
        # Manually add an alert
        engine._channel_alerts[10] = ChannelAlert(
            channel=10,
            frequency_mhz=2410,
            activity_percentage=80.0,
            threshold=75.0,
            classification="Heavy Load",
            persistence_start=time.time(),
            consecutive_windows=3,
        )
        
        engine.disarm()
        
        assert len(engine.get_active_alerts()) == 0
    
    def test_process_observation_disarmed(self, engine, configs):
        _, _, channels = configs
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=80,
            rpd_negative=20,
            activity_percentage=80.0,
            status="Heavy Load",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        
        result = engine.process_observation(obs, {})
        
        assert result is None
        assert len(engine.get_active_alerts()) == 0
    
    def test_process_observation_armed_below_threshold(self, engine, configs):
        engine.arm()
        _, _, channels = configs
        
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
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
        
        result = engine.process_observation(obs, {})
        
        assert result is None
        assert len(engine.get_active_alerts()) == 0
    
    def test_process_observation_armed_above_threshold(self, engine, configs):
        engine.arm()
        _, _, channels = configs
        
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=80,
            rpd_negative=20,
            activity_percentage=80.0,
            status="Heavy Load",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        
        result = engine.process_observation(obs, {})
        
        assert result is not None
        assert result.channel == 10
        assert result.consecutive_windows == 1
    
    def test_persistent_alert_generation(self, engine, configs):
        engine.arm()
        _, _, channels = configs
        
        base_time = time.time()
        
        for i in range(3):
            obs = ChannelObservation(
                timestamp=base_time + i * 0.05,
                channel=10,
                frequency_mhz=2410,
                backend="sim",
                valid_samples=100,
                rpd_positive=80,
                rpd_negative=20,
                activity_percentage=80.0,
                status="Heavy Load",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            result = engine.process_observation(obs, {})
        
        alerts = engine.get_active_alerts()
        assert len(alerts) == 1
        assert alerts[0].channel == 10
        assert alerts[0].consecutive_windows == 3
        assert alerts[0].alert_count == 1
    
    def test_alert_cooldown(self, engine, configs):
        engine.arm()
        _, _, channels = configs
        
        base_time = time.time()
        
        for i in range(3):
            obs = ChannelObservation(
                timestamp=base_time + i * 0.05,
                channel=10,
                frequency_mhz=2410,
                backend="sim",
                valid_samples=100,
                rpd_positive=80,
                rpd_negative=20,
                activity_percentage=80.0,
                status="Heavy Load",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            engine.process_observation(obs, {})
        
        # Immediate re-check should not generate new alert due to cooldown
        obs = ChannelObservation(
            timestamp=base_time + 0.2,
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=80,
            rpd_negative=20,
            activity_percentage=80.0,
            status="Heavy Load",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        engine.process_observation(obs, {})
        
        alerts = engine.get_active_alerts()
        assert alerts[0].alert_count == 1
    
    def test_hysteresis_clears_alert(self, engine, configs):
        engine.arm()
        _, _, channels = configs
        
        base_time = time.time()
        
        for i in range(3):
            obs = ChannelObservation(
                timestamp=base_time + i * 0.05,
                channel=10,
                frequency_mhz=2410,
                backend="sim",
                valid_samples=100,
                rpd_positive=80,
                rpd_negative=20,
                activity_percentage=80.0,
                status="Heavy Load",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            engine.process_observation(obs, {})
        
        # Activity drops below threshold - hysteresis
        obs = ChannelObservation(
            timestamp=base_time + 0.2,
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=65,
            rpd_negative=35,
            activity_percentage=65.0,
            status="Busy",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        engine.process_observation(obs, {})
        
        alerts = engine.get_active_alerts()
        assert len(alerts) == 0
    
    def test_get_recommendations(self, engine, configs):
        engine.arm()
        mitigation, thresholds, channels = configs
        
        all_obs = {}
        for ch in [10, 11, 12, 13, 14]:
            all_obs[ch] = ChannelObservation(
                timestamp=time.time(),
                channel=ch,
                frequency_mhz=2400 + ch,
                backend="sim",
                valid_samples=100,
                rpd_positive=80 if ch == 10 else 10,
                rpd_negative=20 if ch == 10 else 90,
                activity_percentage=80.0 if ch == 10 else 10.0,
                status="Heavy Load" if ch == 10 else "Clear",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
        
        obs = all_obs[10]
        engine.process_observation(obs, all_obs)
        
        recommendations = engine.get_recommendations()
        assert len(recommendations) > 0
        assert 10 not in recommendations
        assert all(r in [11, 12, 13, 14] for r in recommendations)
    
    def test_get_channel_status(self, engine, configs):
        engine.arm()
        _, _, channels = configs
        
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=80,
            rpd_negative=20,
            activity_percentage=80.0,
            status="Heavy Load",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        
        status = engine.get_channel_status(10, obs)
        assert status == ChannelStatus.NORMAL
        
        for _ in range(3):
            engine.process_observation(obs, {})
        
        status = engine.get_channel_status(10, obs)
        assert status == ChannelStatus.PERSISTENT_HIGH_ACTIVITY
    
    def test_clear_history(self, engine, configs):
        engine.arm()
        _, _, channels = configs
        
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=100,
            rpd_positive=80,
            rpd_negative=20,
            activity_percentage=80.0,
            status="Heavy Load",
            data_sufficient=True,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        
        for _ in range(3):
            engine.process_observation(obs, {})
        
        engine.clear_history()
        
        assert len(engine.get_alert_history()) == 0
        assert len(engine.get_channel_peaks()) == 0
        assert engine.get_recommendations() == []


class TestMitigationEngineInsfficientData:
    """Tests for handling insufficient data."""
    
    @pytest.fixture
    def engine(self):
        mitigation = MitigationConfig(armed=True)
        thresholds = ThresholdConfig()
        channels = ChannelConfig(start_channel=0, end_channel=125)
        return MitigationEngine(mitigation, thresholds, channels)
    
    def test_insufficient_data_observation(self, engine):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
            backend="sim",
            valid_samples=5,
            rpd_positive=2,
            rpd_negative=3,
            activity_percentage=None,
            status="INSUFFICIENT DATA",
            data_sufficient=False,
            measurement_window=1.0,
            sampling_interval=0.01,
        )
        
        result = engine.process_observation(obs, {})
        assert result is None
        
        status = engine.get_channel_status(10, obs)
        assert status == ChannelStatus.INSUFFICIENT_DATA
    
    def test_sensor_error_observation(self, engine):
        obs = ChannelObservation(
            timestamp=time.time(),
            channel=10,
            frequency_mhz=2410,
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
        
        status = engine.get_channel_status(10, obs)
        assert status == ChannelStatus.SENSOR_ERROR


class TestMitigationEventExport:
    """Tests for event export."""
    
    def test_export_events(self):
        mitigation = MitigationConfig(armed=True)
        thresholds = ThresholdConfig()
        channels = ChannelConfig(start_channel=0, end_channel=125)
        engine = MitigationEngine(mitigation, thresholds, channels)
        engine.arm()
        
        for i in range(3):
            obs = ChannelObservation(
                timestamp=time.time() + i * 0.05,
                channel=10,
                frequency_mhz=2410,
                backend="sim",
                valid_samples=100,
                rpd_positive=80,
                rpd_negative=20,
                activity_percentage=80.0,
                status="Heavy Load",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            engine.process_observation(obs, {})
        
        events = engine.export_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "PERSISTENT_HIGH_ACTIVITY"
        assert events[0]["channel"] == 10
        assert events[0]["activity_percentage"] == 80.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])