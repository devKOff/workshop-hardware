"""Logging configuration for RF Spectrum Visualizer."""

import logging
import logging.handlers
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JSONLinesFormatter(logging.Formatter):
    """Formatter that outputs log records as JSON Lines."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if hasattr(record, "event_id"):
            log_data["event_id"] = record.event_id
        if hasattr(record, "event_type"):
            log_data["event_type"] = record.event_type
        if hasattr(record, "backend"):
            log_data["backend"] = record.backend
        if hasattr(record, "channel"):
            log_data["channel"] = record.channel
        if hasattr(record, "frequency_mhz"):
            log_data["frequency_mhz"] = record.frequency_mhz
        if hasattr(record, "activity_percentage"):
            log_data["activity_percentage"] = record.activity_percentage
        if hasattr(record, "sample_count"):
            log_data["sample_count"] = record.sample_count
        if hasattr(record, "rpd_positive_count"):
            log_data["rpd_positive_count"] = record.rpd_positive_count
        if hasattr(record, "measurement_window"):
            log_data["measurement_window"] = record.measurement_window
        if hasattr(record, "threshold"):
            log_data["threshold"] = record.threshold
        if hasattr(record, "classification"):
            log_data["classification"] = record.classification
        if hasattr(record, "recommended_response"):
            log_data["recommended_response"] = record.recommended_response
        if hasattr(record, "action_status"):
            log_data["action_status"] = record.action_status
        if hasattr(record, "error_details"):
            log_data["error_details"] = record.error_details
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, separators=(",", ":"))


def setup_logging(
    log_path: str = "logs/countermeasures.jsonl",
    level: int = logging.INFO,
    console_level: int = logging.WARNING,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """Configure application logging."""
    logger = logging.getLogger("rf_visualizer")
    logger.setLevel(level)
    logger.handlers.clear()
    
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(JSONLinesFormatter())
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(console_handler)
    
    return logger


def log_countermeasure_event(
    logger: logging.Logger,
    event_id: str,
    event_type: str,
    backend: str,
    channel: int,
    frequency_mhz: int,
    activity_percentage: Optional[float],
    sample_count: int,
    rpd_positive_count: int,
    measurement_window: float,
    threshold: float,
    classification: str,
    recommended_response: str,
    action_status: str,
    error_details: Optional[str] = None,
) -> None:
    """Log a countermeasure event as JSON Lines."""
    extra = {
        "event_id": event_id,
        "event_type": event_type,
        "backend": backend,
        "channel": channel,
        "frequency_mhz": frequency_mhz,
        "activity_percentage": activity_percentage,
        "sample_count": sample_count,
        "rpd_positive_count": rpd_positive_count,
        "measurement_window": measurement_window,
        "threshold": threshold,
        "classification": classification,
        "recommended_response": recommended_response,
        "action_status": action_status,
    }
    if error_details:
        extra["error_details"] = error_details
    
    logger.info("Countermeasure event", extra=extra)


def get_logger(name: str = "rf_visualizer") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)