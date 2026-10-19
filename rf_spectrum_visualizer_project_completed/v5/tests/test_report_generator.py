"""Unit tests for report generator module."""

import pytest
import json
import csv
import io
import time
from unittest.mock import Mock
from report_generator import ReportGenerator, export_spectrum_png
from config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, AnomalyConfig, StorageConfig
from scanner import SpectrumData, ChannelObservation
from anomaly_detector import AnomalyDetector, Anomaly, AnomalyType, Severity


class TestReportGenerator:
    """Tests for ReportGenerator."""
    
    @pytest.fixture
    def config(self):
        return AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01),
            thresholds=ThresholdConfig(),
            anomaly=AnomalyConfig(),
            storage=StorageConfig(export_dir="test_exports"),
        )
    
    @pytest.fixture
    def spectrum_data(self, config):
        data = SpectrumData(config)
        data.set_backend("sim")
        for ch in range(6):
            obs = ChannelObservation(
                timestamp=time.time(),
                channel=ch,
                frequency_mhz=2400 + ch,
                backend="sim",
                valid_samples=100,
                rpd_positive=ch * 10,
                rpd_negative=100 - ch * 10,
                activity_percentage=float(ch * 10) if ch * 10 <= 100 else None,
                status="HEAVY LOAD" if ch * 10 >= 75 else "BUSY" if ch * 10 >= 50 else "MODERATE" if ch * 10 > 24 else "CLEAR",
                data_sufficient=True,
                measurement_window=1.0,
                sampling_interval=0.01,
            )
            data.update_observation(obs)
        data.increment_scan_count()
        data.set_scan_complete(2.5)
        return data
    
    @pytest.fixture
    def anomaly_detector(self, config):
        detector = AnomalyDetector(config.anomaly, config.thresholds, config.channel)
        return detector
    
    @pytest.fixture
    def report_gen(self, config, spectrum_data, anomaly_detector):
        return ReportGenerator(config, spectrum_data, anomaly_detector)
    
    def test_generate_scan_report(self, report_gen):
        report = report_gen.generate_scan_report()
        
        assert report["report_version"] == "5.0"
        assert report["report_type"] == "channel_scan"
        assert "generated_at" in report
        assert report["run_info"]["backend"] == "sim"
        assert report["run_info"]["scan_count"] == 1
        assert report["run_info"]["channel_count"] == 6
        assert len(report["observations"]) == 6
        assert "limitations" in report
        assert len(report["limitations"]) > 0
    
    def test_generate_anomaly_report(self, report_gen):
        # Add an anomaly
        anomaly = Anomaly(
            anomaly_id="test123",
            anomaly_type=AnomalyType.PERSISTENT_HIGH_ACTIVITY,
            channel=50,
            frequency_mhz=2450,
            detection_time=time.time(),
            current_activity=85.0,
            baseline_activity=20.0,
            difference_from_baseline=65.0,
            supporting_observations=100,
            severity=Severity.HIGH,
            detection_reason="Test",
            confidence=0.9,
        )
        report_gen._anomaly_detector._active_anomalies["test123"] = anomaly
        
        report = report_gen.generate_anomaly_report()
        
        assert report["report_type"] == "anomaly_report"
        assert len(report["active_anomalies"]) == 1
        assert report["statistics"]["total_active"] == 1
    
    def test_export_csv(self, report_gen):
        output = io.StringIO()
        count = report_gen.export_csv(output, include_anomalies=False)
        
        assert count == 6
        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)
        assert len(rows) == 6
        assert rows[0]["channel"] == "0"
        assert rows[5]["channel"] == "5"
    
    def test_export_csv_with_anomalies(self, report_gen):
        anomaly = Anomaly(
            anomaly_id="test123",
            anomaly_type=AnomalyType.PERSISTENT_HIGH_ACTIVITY,
            channel=50,
            frequency_mhz=2450,
            detection_time=time.time(),
            current_activity=85.0,
            baseline_activity=20.0,
            difference_from_baseline=65.0,
            supporting_observations=100,
            severity=Severity.HIGH,
            detection_reason="Test",
            confidence=0.9,
        )
        report_gen._anomaly_detector._active_anomalies["test123"] = anomaly
        
        output = io.StringIO()
        count = report_gen.export_csv(output, include_anomalies=True)
        
        assert count == 6
    
    def test_export_json(self, report_gen):
        output = io.StringIO()
        report_gen.export_json(output)
        
        output.seek(0)
        data = json.load(output)
        
        assert data["report_version"] == "5.0"
        assert len(data["observations"]) == 6
    
    def test_export_jsonl(self, report_gen):
        output = io.StringIO()
        count = report_gen.export_jsonl(output)
        
        assert count == 6
        output.seek(0)
        lines = output.readlines()
        assert len(lines) == 6
        
        for line in lines:
            parsed = json.loads(line)
            assert "channel" in parsed
    
    def test_export_anomaly_jsonl(self, report_gen):
        anomaly = Anomaly(
            anomaly_id="test123",
            anomaly_type=AnomalyType.PERSISTENT_HIGH_ACTIVITY,
            channel=50,
            frequency_mhz=2450,
            detection_time=time.time(),
            current_activity=85.0,
            baseline_activity=20.0,
            difference_from_baseline=65.0,
            supporting_observations=100,
            severity=Severity.HIGH,
            detection_reason="Test",
            confidence=0.9,
        )
        report_gen._anomaly_detector._active_anomalies["test123"] = anomaly
        report_gen._anomaly_detector._anomaly_history.append(anomaly)
        
        output = io.StringIO()
        count = report_gen.export_anomaly_jsonl(output)
        
        assert count == 1
        output.seek(0)
        line = output.readline()
        parsed = json.loads(line)
        assert parsed["anomaly_type"] == "PERSISTENT_HIGH_ACTIVITY"
    
    def test_generate_summary_text(self, report_gen):
        summary = report_gen.generate_summary_text()
        
        assert "RF SPECTRUM VISUALIZER - SCAN SUMMARY" in summary
        assert "Backend: SIM" in summary
        assert "CHANNEL CLASSIFICATION:" in summary
        assert "CLEAR:" in summary
        assert "HEAVY LOAD:" in summary


class TestExportSpectrumPNG:
    """Tests for PNG export (mocked)."""
    
    def test_export_without_matplotlib(self, monkeypatch):
        # Mock matplotlib import to fail
        monkeypatch.setitem(__import__('sys').modules, 'matplotlib', None)
        monkeypatch.setitem(__import__('sys').modules, 'matplotlib.pyplot', None)
        monkeypatch.setitem(__import__('sys').modules, 'numpy', None)
        
        config = AppConfig(
            channel=ChannelConfig(start_channel=0, end_channel=5),
            scan=ScanConfig(),
            thresholds=ThresholdConfig(),
            anomaly=AnomalyConfig(),
            storage=StorageConfig(),
        )
        data = SpectrumData(config)
        
        result = export_spectrum_png(data, config, "test.png", "spectrum")
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])