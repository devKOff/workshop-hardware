"""Unit tests for channel classifier module."""

import pytest
from channel_classifier import (
    ChannelClassifier, RecommendationEngine, ClassificationResult, ActivityCategory
)
from config import ThresholdConfig, ChannelConfig
from scanner import ChannelObservation


class TestChannelClassifier:
    """Tests for ChannelClassifier."""
    
    @pytest.fixture
    def thresholds(self):
        return ThresholdConfig(
            clear_max=24,
            moderate_max=49,
            busy_max=74,
            heavy_min=75,
        )
    
    @pytest.fixture
    def channel_config(self):
        return ChannelConfig(start_channel=0, end_channel=125)
    
    @pytest.fixture
    def classifier(self, thresholds, channel_config):
        return ChannelClassifier(thresholds, channel_config)
    
    def test_classify_clear(self, classifier):
        result = classifier.classify(10.0, data_sufficient=True)
        assert result.category == ActivityCategory.CLEAR
        assert result.activity_percentage == 10.0
        assert result.data_sufficient is True
    
    def test_classify_moderate(self, classifier):
        result = classifier.classify(35.0, data_sufficient=True)
        assert result.category == ActivityCategory.MODERATE
    
    def test_classify_busy(self, classifier):
        result = classifier.classify(60.0, data_sufficient=True)
        assert result.category == ActivityCategory.BUSY
    
    def test_classify_heavy_load(self, classifier):
        result = classifier.classify(85.0, data_sufficient=True)
        assert result.category == ActivityCategory.HEAVY_LOAD
    
    def test_classify_boundary_clear_max(self, classifier):
        result = classifier.classify(24.0, data_sufficient=True)
        assert result.category == ActivityCategory.CLEAR
    
    def test_classify_boundary_moderate_max(self, classifier):
        result = classifier.classify(49.0, data_sufficient=True)
        assert result.category == ActivityCategory.MODERATE
    
    def test_classify_boundary_busy_max(self, classifier):
        result = classifier.classify(74.0, data_sufficient=True)
        assert result.category == ActivityCategory.BUSY
    
    def test_classify_boundary_heavy_min(self, classifier):
        result = classifier.classify(75.0, data_sufficient=True)
        assert result.category == ActivityCategory.HEAVY_LOAD
    
    def test_classify_insufficient_data(self, classifier):
        result = classifier.classify(None, data_sufficient=False)
        assert result.category == ActivityCategory.INSUFFICIENT_DATA
        assert result.data_sufficient is False
    
    def test_classify_none_activity(self, classifier):
        result = classifier.classify(None, data_sufficient=True)
        assert result.category == ActivityCategory.INSUFFICIENT_DATA
    
    def test_classify_sensor_error(self, classifier):
        result = classifier.classify(50.0, data_sufficient=True, error="SPI error")
        assert result.category == ActivityCategory.SENSOR_ERROR
        assert result.error == "SPI error"
    
    def test_classify_multiple(self, classifier):
        observations = {
            10: {"activity_percentage": 10.0, "data_sufficient": True, "error": None},
            20: {"activity_percentage": 50.0, "data_sufficient": True, "error": None},
            30: {"activity_percentage": 80.0, "data_sufficient": True, "error": None},
            40: {"activity_percentage": None, "data_sufficient": False, "error": None},
            50: {"activity_percentage": 30.0, "data_sufficient": True, "error": "SPI error"},
        }
        
        results = classifier.classify_multiple(observations)
        
        assert results[10].category == ActivityCategory.CLEAR
        assert results[20].category == ActivityCategory.BUSY
        assert results[30].category == ActivityCategory.HEAVY_LOAD
        assert results[40].category == ActivityCategory.INSUFFICIENT_DATA
        assert results[50].category == ActivityCategory.SENSOR_ERROR
    
    def test_get_threshold_boundaries(self, classifier):
        boundaries = classifier.get_threshold_boundaries()
        assert boundaries["clear_max"] == 24.0
        assert boundaries["moderate_max"] == 49.0
        assert boundaries["busy_max"] == 74.0
        assert boundaries["heavy_min"] == 75.0
    
    def test_validate_thresholds(self, classifier):
        warnings = classifier.validate_thresholds()
        assert isinstance(warnings, list)
    
    def test_update_thresholds(self, classifier, channel_config):
        new_thresholds = ThresholdConfig(
            clear_max=20,
            moderate_max=40,
            busy_max=60,
            heavy_min=80,
        )
        classifier.update_thresholds(new_thresholds)
        
        result = classifier.classify(25.0, data_sufficient=True)
        assert result.category == ActivityCategory.MODERATE


class TestRecommendationEngine:
    """Tests for RecommendationEngine."""
    
    @pytest.fixture
    def thresholds(self):
        return ThresholdConfig()
    
    @pytest.fixture
    def channel_config(self):
        return ChannelConfig(start_channel=0, end_channel=20)
    
    @pytest.fixture
    def classifier(self, thresholds, channel_config):
        return ChannelClassifier(thresholds, channel_config)
    
    @pytest.fixture
    def engine(self, classifier, channel_config):
        return RecommendationEngine(classifier, channel_config)
    
    def test_get_quiet_channels(self, engine):
        observations = {
            1: {"activity_percentage": 5.0, "data_sufficient": True, "error": None, "min_valid_samples": 10},
            5: {"activity_percentage": 15.0, "data_sufficient": True, "error": None, "min_valid_samples": 10},
            10: {"activity_percentage": 40.0, "data_sufficient": True, "error": None, "min_valid_samples": 10},
            15: {"activity_percentage": 80.0, "data_sufficient": True, "error": None, "min_valid_samples": 10},
        }
        
        quiet = engine.get_quiet_channels(observations, max_results=3, max_activity=25.0)
        
        assert 1 in quiet
        assert 5 in quiet
        assert 10 not in quiet
        assert 15 not in quiet
        assert len(quiet) <= 3
    
    def test_get_quiet_channels_insufficient_data(self, engine):
        observations = {
            1: {"activity_percentage": 5.0, "data_sufficient": False, "error": None},
            5: {"activity_percentage": 15.0, "data_sufficient": True, "error": None},
        }
        
        quiet = engine.get_quiet_channels(observations, max_results=3, max_activity=25.0)
        
        assert 1 not in quiet
        assert 5 in quiet
    
    def test_get_quiet_channels_error(self, engine):
        observations = {
            1: {"activity_percentage": 5.0, "data_sufficient": True, "error": "SPI error"},
            5: {"activity_percentage": 15.0, "data_sufficient": True, "error": None},
        }
        
        quiet = engine.get_quiet_channels(observations, max_results=3, max_activity=25.0)
        
        assert 1 not in quiet
        assert 5 in quiet
    
    def test_get_busy_channels(self, engine):
        observations = {
            1: {"activity_percentage": 5.0, "data_sufficient": True, "error": None},
            5: {"activity_percentage": 40.0, "data_sufficient": True, "error": None},
            10: {"activity_percentage": 80.0, "data_sufficient": True, "error": None},
            15: {"activity_percentage": 90.0, "data_sufficient": True, "error": None},
        }
        
        busy = engine.get_busy_channels(observations, min_activity=75.0)
        
        assert 10 in busy
        assert 15 in busy
        assert 1 not in busy
        assert 5 not in busy
    
    def test_get_channel_explanation(self, engine):
        observations = {
            10: {"activity_percentage": 10.0, "data_sufficient": True, "error": None, "status": "CLEAR"},
            20: {"activity_percentage": 50.0, "data_sufficient": True, "error": None, "status": "BUSY"},
            30: {"activity_percentage": 85.0, "data_sufficient": True, "error": None, "status": "HEAVY LOAD"},
        }
        
        explanation = engine.get_channel_explanation(10, observations)
        assert "CLEAR" in explanation
        assert "2410 MHz" in explanation
        assert "Good candidate" in explanation
        
        explanation = engine.get_channel_explanation(20, observations)
        assert "BUSY" in explanation
        assert "2420 MHz" in explanation
        assert "may impact" in explanation
        
        explanation = engine.get_channel_explanation(30, observations)
        assert "HEAVY LOAD" in explanation
        assert "2430 MHz" in explanation
        assert "Investigation recommended" in explanation
    
    def test_get_channel_explanation_insufficient(self, engine):
        observations = {
            10: {"activity_percentage": None, "data_sufficient": False, "error": None, 
                 "valid_samples": 5, "min_valid_samples": 10},
        }
        
        explanation = engine.get_channel_explanation(10, observations)
        assert "Insufficient data" in explanation
        assert "5/10" in explanation
    
    def test_get_channel_explanation_error(self, engine):
        observations = {
            10: {"activity_percentage": 10.0, "data_sufficient": True, "error": "SPI error"},
        }
        
        explanation = engine.get_channel_explanation(10, observations)
        assert "Sensor error" in explanation
        assert "SPI error" in explanation
    
    def test_get_channel_explanation_no_data(self, engine):
        observations = {}
        
        explanation = engine.get_channel_explanation(10, observations)
        assert "No observation data available" in explanation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])