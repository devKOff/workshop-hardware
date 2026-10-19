"""Tests for report generation and exports."""

import pytest
import json
import csv
import tempfile
import os
from io import StringIO
from pathlib import Path
from v6.report_generator import ReportGenerator
from v6.config import AppConfig, ChannelConfig, ScanConfig, ThresholdConfig, BlocklistConfig, StorageConfig
from v6.scanner import SpectrumData, ChannelObservation
from v6.blocklist_manager import BlocklistManager
from v6.channel_selector import ChannelSelector


@pytest.fixture
def config():
    return AppConfig(
        channel=ChannelConfig(0, 5),
        scan=ScanConfig(measurement_window=1.0, sampling_interval=0.01, min_valid_samples=10),
        thresholds=ThresholdConfig(),
        blocklist=BlocklistConfig(file_path="test_blocklist.json"),
        storage=StorageConfig(export_dir="test_exports"),
    )


@pytest.fixture
def spectrum_data(config):
    data = SpectrumData(config)
    data.set_backend("sim")
    # Add some observations
    for ch in [0, 1, 2, 3]:
        obs = ChannelObservation(
            timestamp=1000.0 + ch, channel=ch, frequency_mhz=2400+ch, backend="sim",
            valid_samples=100, rpd_positive=10*ch, rpd_negative=100-10*ch,
            activity_percentage=10.0*ch, status="Clear" if ch < 2 else "Moderate",
            data_sufficient=True, measurement_window=1.0, sampling_interval=0.01
        )
        data.update_observation(obs)
    return data


@pytest.fixture
def blocklist(config):
    bl = BlocklistManager(config.blocklist)
    bl.block_channel(3, "Test block")
    return bl


@pytest.fixture
def selector(config, blocklist):
    return ChannelSelector(config.channel, config.thresholds, blocklist)


@pytest.fixture
def report_gen(config, spectrum_data, blocklist, selector):
    return ReportGenerator(config, spectrum_data, blocklist, selector)


class TestReportGenerator:
    def test_generate_full_report(self, report_gen):
        report = report_gen.generate_full_report()
        
        assert "metadata" in report
        assert "blocklist" in report
        assert "channel_assessments" in report
        assert "recommendations" in report
        assert "summary" in report
        
        assert report["metadata"]["backend"] == "sim"
        assert len(report["channel_assessments"]) == 6  # 0-5
        assert report["blocklist"]["count"] == 1
        assert report["blocklist"]["blocked_channels"] == [3]
    
    def test_export_json(self, report_gen):
        output = StringIO()
        report_gen.export_json(output)
        
        output.seek(0)
        data = json.load(output)
        
        assert "metadata" in data
        assert "channel_assessments" in data
    
    def test_export_json_file(self, report_gen, tmp_path):
        filepath = report_gen.export_json_file("test_report.json")
        assert filepath.exists()
        
        with open(filepath) as f:
            data = json.load(f)
        assert "metadata" in data
    
    def test_export_csv(self, report_gen):
        output = StringIO()
        report_gen.export_csv(output)
        
        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)
        
        assert len(rows) == 6  # 0-5
        assert rows[0]["channel"] == "0"
        assert rows[3]["blocked"] == "True"
        assert rows[0]["blocked"] == "False"
    
    def test_export_csv_file(self, report_gen, tmp_path):
        filepath = report_gen.export_csv_file("test_channels.csv")
        assert filepath.exists()
        
        with open(filepath) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 6
    
    def test_export_blocklist_json(self, report_gen):
        output = StringIO()
        report_gen.export_blocklist_json(output)
        
        output.seek(0)
        data = json.load(output)
        
        assert "blocklist" in data
        assert len(data["blocklist"]) == 1
        assert data["blocklist"][0]["channel"] == 3
    
    def test_export_blocklist_csv(self, report_gen):
        output = StringIO()
        report_gen.export_blocklist_csv(output)
        
        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)
        
        assert len(rows) == 1
        assert rows[0]["channel"] == "3"
    
    def test_export_waterfall_csv(self, report_gen):
        output = StringIO()
        report_gen.export_waterfall_csv(output)
        
        output.seek(0)
        reader = csv.DictReader(output)
        rows = list(reader)
        
        assert len(rows) == 4  # 4 observations added
    
    def test_export_all_formats(self, report_gen, tmp_path):
        results = report_gen.export_all_formats("full_test")
        
        assert "json" in results
        assert "csv" in results
        assert "blocklist_json" in results
        assert "blocklist_csv" in results
        assert "waterfall_csv" in results
        
        for path in results.values():
            assert path.exists()
    
    def test_summary_stats(self, report_gen):
        report = report_gen.generate_full_report()
        summary = report["summary"]
        
        assert summary["total_channels"] == 6
        assert summary["eligible_channels"] > 0
        assert summary["blocked_channels"] == 1
        assert "activity_stats" in summary


class TestExportIntegration:
    def test_roundtrip_json(self, report_gen, tmp_path):
        # Export
        filepath = report_gen.export_json_file("roundtrip.json")
        
        # Import back
        with open(filepath) as f:
            data = json.load(f)
        
        assert data["metadata"]["backend"] == "sim"
        assert len(data["channel_assessments"]) == 6
    
    def test_csv_has_all_fields(self, report_gen):
        output = StringIO()
        report_gen.export_csv(output)
        
        output.seek(0)
        reader = csv.DictReader(output)
        fieldnames = reader.fieldnames
        
        expected_fields = [
            "channel", "frequency_mhz", "activity_percentage", "status",
            "data_sufficient", "valid_samples", "rpd_positive", "rpd_negative",
            "eligible", "eligibility_reason", "blocked", "blocked_at", "block_reason",
            "measurement_window", "sampling_interval", "backend", "timestamp",
        ]
        
        for field in expected_fields:
            assert field in fieldnames


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
