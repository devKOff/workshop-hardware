"""Report generation and export module for RF Spectrum Visualizer V5."""

import json
import csv
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, TextIO
from dataclasses import asdict

from config import AppConfig
from scanner import SpectrumData, ChannelObservation
from anomaly_detector import AnomalyDetector, Anomaly

logger = logging.getLogger("rf_visualizer.reports")


class ReportGenerator:
    """Generates and exports scan reports in various formats."""
    
    def __init__(self, config: AppConfig, spectrum_data: SpectrumData, 
                 anomaly_detector: Optional[AnomalyDetector] = None):
        self._config = config
        self._spectrum_data = spectrum_data
        self._anomaly_detector = anomaly_detector
    
    def generate_scan_report(self) -> Dict[str, Any]:
        """Generate a complete scan report."""
        observations = self._spectrum_data.get_all_observations()
        
        heavy_load_channels = [
            ch for ch, obs in observations.items()
            if obs.activity_percentage is not None 
            and obs.activity_percentage >= self._config.thresholds.heavy_min
            and obs.data_sufficient
        ]
        
        busy_channels = [
            ch for ch, obs in observations.items()
            if obs.activity_percentage is not None 
            and obs.activity_percentage >= self._config.thresholds.busy_max
            and obs.data_sufficient
        ]
        
        failed_channels = self._spectrum_data.get_failed_channels()
        
        report = {
            "report_version": "5.0",
            "report_type": "channel_scan",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_at_unix": time.time(),
            "software": {
                "name": "RF Spectrum Visualizer",
                "version": "5.0",
            },
            "run_info": {
                "backend": self._spectrum_data.get_backend(),
                "scan_count": self._spectrum_data.get_scan_count(),
                "last_scan_duration": self._spectrum_data.get_last_scan_duration(),
                "scan_range": f"{self._config.channel.start_channel}-{self._config.channel.end_channel}",
                "channel_count": len(self._config.channel.channel_range()),
            },
            "configuration": {
                "measurement_window": self._config.scan.measurement_window,
                "sampling_interval": self._config.scan.sampling_interval,
                "min_valid_samples": self._config.scan.min_valid_samples,
                "thresholds": self._config.thresholds.get_thresholds_dict(),
            },
            "summary": {
                "total_channels": len(observations),
                "channels_with_data": sum(1 for o in observations.values() if o.data_sufficient),
                "channels_insufficient_data": sum(1 for o in observations.values() if not o.data_sufficient and not o.error),
                "channels_failed": len(failed_channels),
                "heavy_load_channels": len(heavy_load_channels),
                "busy_channels": len(busy_channels),
                "anomaly_count": len(self._anomaly_detector.get_active_anomalies()) if self._anomaly_detector else 0,
            },
            "observations": [obs.to_dict() for obs in observations.values()],
        }
        
        if self._anomaly_detector:
            report["anomalies"] = [a.to_dict() for a in self._anomaly_detector.get_active_anomalies()]
            report["anomaly_history"] = [a.to_dict() for a in self._anomaly_detector.get_anomaly_history(50)]
        
        report["limitations"] = [
            "nRF24L01+ is a narrowband transceiver, not a calibrated spectrum analyzer",
            "RPD (Received Power Detector) provides binary energy detection only",
            "Activity percentage represents proportion of positive RPD samples, not calibrated power",
            "Cannot identify specific protocols or transmitters from energy detection alone",
            "Single measurements may not represent persistent conditions",
            "Results are heuristic classifications, not standardized RF measurements",
        ]
        
        return report
    
    def generate_anomaly_report(self) -> Dict[str, Any]:
        """Generate anomaly-specific report."""
        if not self._anomaly_detector:
            return {"error": "Anomaly detector not available"}
        
        anomalies = self._anomaly_detector.get_active_anomalies()
        history = self._anomaly_detector.get_anomaly_history(100)
        
        by_type = {}
        by_severity = {}
        by_channel = {}
        
        for anomaly in anomalies:
            by_type[anomaly.anomaly_type.value] = by_type.get(anomaly.anomaly_type.value, 0) + 1
            by_severity[anomaly.severity.value] = by_severity.get(anomaly.severity.value, 0) + 1
            by_channel[anomaly.channel] = by_channel.get(anomaly.channel, 0) + 1
        
        return {
            "report_version": "5.0",
            "report_type": "anomaly_report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generated_at_unix": time.time(),
            "backend": self._spectrum_data.get_backend(),
            "active_anomalies": [a.to_dict() for a in anomalies],
            "anomaly_history": [a.to_dict() for a in history],
            "statistics": {
                "by_type": by_type,
                "by_severity": by_severity,
                "by_channel": by_channel,
                "total_active": len(anomalies),
                "total_historical": len(history),
            },
        }
    
    def export_csv(self, output: TextIO, include_anomalies: bool = False) -> int:
        """Export observations to CSV."""
        observations = self._spectrum_data.get_all_observations()
        channels = self._config.channel.channel_range()
        
        fieldnames = [
            "timestamp", "timestamp_iso", "channel", "frequency_mhz", "backend",
            "valid_samples", "rpd_positive", "rpd_negative",
            "activity_percentage", "status", "data_sufficient",
            "measurement_window", "sampling_interval", "error", "scan_id",
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        count = 0
        for ch in channels:
            obs = observations.get(ch)
            if obs:
                row = obs.to_dict()
                row["timestamp_iso"] = obs.iso_timestamp
                writer.writerow(row)
                count += 1
            else:
                writer.writerow({
                    "timestamp": "",
                    "timestamp_iso": "",
                    "channel": ch,
                    "frequency_mhz": 2400 + ch,
                    "backend": self._spectrum_data.get_backend(),
                    "valid_samples": 0,
                    "rpd_positive": 0,
                    "rpd_negative": 0,
                    "activity_percentage": "",
                    "status": "NOT_SCANNED",
                    "data_sufficient": False,
                    "measurement_window": self._config.scan.measurement_window,
                    "sampling_interval": self._config.scan.sampling_interval,
                    "error": "Channel not scanned",
                    "scan_id": "",
                })
        
        if include_anomalies and self._anomaly_detector:
            writer.writerow({})  # blank row
            writer.writerow({"timestamp": "ANOMALY REPORT"})
            
            anomaly_fieldnames = [
                "anomaly_id", "anomaly_type", "channel", "frequency_mhz",
                "detection_time", "detection_time_iso", "current_activity",
                "baseline_activity", "difference_from_baseline",
                "supporting_observations", "severity", "detection_reason",
                "confidence", "state", "acknowledged",
            ]
            writer.writerow({fn: fn for fn in anomaly_fieldnames})
            
            for anomaly in self._anomaly_detector.get_active_anomalies():
                row = anomaly.to_dict()
                writer.writerow({fn: row.get(fn, "") for fn in anomaly_fieldnames})
        
        return count
    
    def export_json(self, output: TextIO, include_anomalies: bool = True) -> None:
        """Export observations to JSON."""
        report = self.generate_scan_report()
        json.dump(report, output, indent=2, default=str)
    
    def export_jsonl(self, output: TextIO) -> int:
        """Export observations as JSON Lines (one per line)."""
        observations = self._spectrum_data.get_all_observations()
        channels = self._config.channel.channel_range()
        
        count = 0
        for ch in channels:
            obs = observations.get(ch)
            if obs:
                output.write(json.dumps(obs.to_dict(), default=str) + "\n")
                count += 1
            else:
                output.write(json.dumps({
                    "channel": ch,
                    "frequency_mhz": 2400 + ch,
                    "backend": self._spectrum_data.get_backend(),
                    "activity_percentage": None,
                    "status": "NOT_SCANNED",
                    "data_sufficient": False,
                    "error": "Channel not scanned",
                }, default=str) + "\n")
        
        return count
    
    def export_anomaly_jsonl(self, output: TextIO) -> int:
        """Export anomalies as JSON Lines."""
        if not self._anomaly_detector:
            return 0
        
        count = 0
        for anomaly in self._anomaly_detector.get_anomaly_history(500):
            output.write(json.dumps(anomaly.to_dict(), default=str) + "\n")
            count += 1
        return count
    
    def save_reports(self, base_name: Optional[str] = None) -> Dict[str, str]:
        """Save all report formats to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backend = self._spectrum_data.get_backend()
        
        if base_name is None:
            base_name = f"scan_{backend}_{timestamp}"
        
        export_dir = Path(self._config.storage.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        
        paths = {}
        
        json_path = export_dir / f"{base_name}.json"
        with open(json_path, "w") as f:
            self.export_json(f)
        paths["json"] = str(json_path)
        logger.info(f"Exported JSON: {json_path}")
        
        csv_path = export_dir / f"{base_name}.csv"
        with open(csv_path, "w", newline="") as f:
            self.export_csv(f, include_anomalies=True)
        paths["csv"] = str(csv_path)
        logger.info(f"Exported CSV: {csv_path}")
        
        jsonl_path = export_dir / f"{base_name}.jsonl"
        with open(jsonl_path, "w") as f:
            self.export_jsonl(f)
        paths["jsonl"] = str(jsonl_path)
        logger.info(f"Exported JSONL: {jsonl_path}")
        
        if self._anomaly_detector:
            anomaly_jsonl_path = export_dir / f"{base_name}_anomalies.jsonl"
            with open(anomaly_jsonl_path, "w") as f:
                self.export_anomaly_jsonl(f)
            paths["anomaly_jsonl"] = str(anomaly_jsonl_path)
            logger.info(f"Exported anomaly JSONL: {anomaly_jsonl_path}")
        
        anomaly_report_path = export_dir / f"{base_name}_anomalies.json"
        with open(anomaly_report_path, "w") as f:
            json.dump(self.generate_anomaly_report(), f, indent=2, default=str)
        paths["anomaly_report"] = str(anomaly_report_path)
        
        return paths
    
    def generate_summary_text(self) -> str:
        """Generate human-readable summary."""
        observations = self._spectrum_data.get_all_observations()
        channels = self._config.channel.channel_range()
        
        heavy = sum(1 for o in observations.values() 
                   if o.activity_percentage is not None 
                   and o.activity_percentage >= self._config.thresholds.heavy_min
                   and o.data_sufficient)
        busy = sum(1 for o in observations.values() 
                  if o.activity_percentage is not None 
                  and o.activity_percentage >= self._config.thresholds.busy_max
                  and o.data_sufficient)
        moderate = sum(1 for o in observations.values() 
                      if o.activity_percentage is not None 
                      and o.activity_percentage > self._config.thresholds.clear_max
                      and o.activity_percentage < self._config.thresholds.heavy_min
                      and o.data_sufficient)
        clear = sum(1 for o in observations.values() 
                   if o.activity_percentage is not None 
                   and o.activity_percentage <= self._config.thresholds.clear_max
                   and o.data_sufficient)
        insufficient = sum(1 for o in observations.values() 
                          if not o.data_sufficient and not o.error)
        failed = len(self._spectrum_data.get_failed_channels())
        
        anomaly_count = len(self._anomaly_detector.get_active_anomalies()) if self._anomaly_detector else 0
        
        lines = [
            "=" * 60,
            "RF SPECTRUM VISUALIZER - SCAN SUMMARY",
            "=" * 60,
            f"Backend: {self._spectrum_data.get_backend().upper()}",
            f"Scan range: Channels {self._config.channel.start_channel}-{self._config.channel.end_channel}",
            f"Scan count: {self._spectrum_data.get_scan_count()}",
            f"Last scan duration: {self._spectrum_data.get_last_scan_duration():.2f}s",
            f"Measurement window: {self._config.scan.measurement_window}s per channel",
            f"Sampling interval: {self._config.scan.sampling_interval*1000:.0f}ms",
            "-" * 60,
            "CHANNEL CLASSIFICATION:",
            f"  CLEAR:            {clear:3d}",
            f"  MODERATE:         {moderate:3d}",
            f"  BUSY:             {busy:3d}",
            f"  HEAVY LOAD:       {heavy:3d}",
            f"  INSUFFICIENT DATA: {insufficient:3d}",
            f"  SENSOR ERROR:      {failed:3d}",
            "-" * 60,
            f"ACTIVE ANOMALIES:   {anomaly_count}",
            "=" * 60,
        ]
        
        if anomaly_count > 0 and self._anomaly_detector:
            lines.append("TOP ANOMALIES:")
            for anomaly in self._anomaly_detector.get_active_anomalies()[:5]:
                lines.append(
                    f"  Ch {anomaly.channel:3d} ({anomaly.frequency_mhz} MHz): "
                    f"{anomaly.anomaly_type.value} [{anomaly.severity.value}] - "
                    f"{anomaly.current_activity:.1f}% activity"
                )
            lines.append("=" * 60)
        
        return "\n".join(lines)


def export_spectrum_png(spectrum_data: SpectrumData, config: AppConfig, 
                        output_path: str, plot_type: str = "spectrum") -> bool:
    """Export spectrum or waterfall as PNG (requires matplotlib)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("Matplotlib not available, skipping PNG export")
        return False
    
    observations = spectrum_data.get_all_observations()
    channels = config.channel.channel_range()
    
    if plot_type == "spectrum":
        fig, ax = plt.subplots(figsize=(12, 6))
        
        activities = []
        colors = []
        for ch in channels:
            obs = observations.get(ch)
            if obs and obs.activity_percentage is not None:
                activities.append(obs.activity_percentage)
            else:
                activities.append(0)
            
            if obs and obs.status == "HEAVY LOAD":
                colors.append("#ef5350")
            elif obs and obs.status == "BUSY":
                colors.append("#ffa726")
            elif obs and obs.status == "MODERATE":
                colors.append("#ffca28")
            elif obs and obs.status == "CLEAR":
                colors.append("#66bb6a")
            else:
                colors.append("#9e9e9e")
        
        bars = ax.bar(channels, activities, color=colors, width=0.8, edgecolor="white", linewidth=0.5)
        
        ax.set_xlabel("nRF24 Channel")
        ax.set_ylabel("Estimated Activity (%)")
        ax.set_title(f"RF Spectrum - {spectrum_data.get_backend().upper()} Backend")
        ax.set_ylim(0, 100)
        ax.grid(True, alpha=0.3)
        
        for threshold, label, color in [
            (config.thresholds.clear_max, "Clear", "green"),
            (config.thresholds.moderate_max, "Moderate", "orange"),
            (config.thresholds.busy_max, "Busy", "red"),
        ]:
            ax.axhline(y=threshold, color=color, linestyle=":", alpha=0.5, linewidth=1)
            ax.text(channels[-1] + 1, threshold, label, va="center", ha="left", color=color, fontsize=8)
        
        wifi_channels = {1: 12, 6: 37, 11: 62}
        for wifi_ch, nrf_ch in wifi_channels.items():
            if config.channel.start_channel <= nrf_ch <= config.channel.end_channel:
                ax.axvline(x=nrf_ch, color="blue", linestyle="--", alpha=0.5, linewidth=1)
                ax.text(nrf_ch, 102, f"WiFi {wifi_ch}", rotation=90, va="bottom", ha="center", fontsize=8, color="blue")
        
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return True
    
    elif plot_type == "waterfall":
        waterfall_data = spectrum_data.get_waterfall_data(max_age=config.gui.waterfall_time_window)
        if not waterfall_data:
            logger.warning("No waterfall data available")
            return False
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        channel_activity = {}
        for obs in waterfall_data:
            if obs.channel not in channel_activity:
                channel_activity[obs.channel] = []
            if obs.activity_percentage is not None:
                channel_activity[obs.channel].append(obs.activity_percentage)
        
        max_len = max(len(v) for v in channel_activity.values()) if channel_activity else 0
        if max_len < 2:
            logger.warning("Insufficient waterfall data")
            return False
        
        data_matrix = np.zeros((len(channels), max_len))
        for i, ch in enumerate(channels):
            if ch in channel_activity:
                vals = channel_activity[ch]
                data_matrix[i, -len(vals):] = vals
        
        im = ax.imshow(
            data_matrix,
            aspect="auto",
            origin="lower",
            extent=[0, config.gui.waterfall_time_window, channels[0], channels[-1]],
            cmap="plasma",
            vmin=0,
            vmax=100,
        )
        
        ax.set_xlabel("Time (seconds ago)")
        ax.set_ylabel("nRF24 Channel")
        ax.set_title(f"Waterfall - {spectrum_data.get_backend().upper()} Backend")
        fig.colorbar(im, ax=ax, label="Activity (%)")
        
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return True
    
    return False