"""Flask JSON API routes for the Solar Panel Performance Monitor.

Endpoints:
    GET    /api/health                     - service + sensor health
    GET    /api/measurements/current       - latest reading
    GET    /api/measurements/history       - filtered history
    GET    /api/energy/summary             - aggregated energy over a period
    GET    /api/energy/daily               - per-day energy summaries
    GET    /api/export/csv                 - CSV export of measurements
    GET    /api/export/json                - JSON export of measurements
    POST   /api/sampling/start             - start background sampler
    POST   /api/sampling/stop              - stop background sampler
    GET    /api/sampling/status            - sampler status

All errors return a consistent JSON body: {"error": ..., "message": ...}.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from flask import jsonify, request, Response

from app.services.history_service import HistoryService
from app.services.sensor_service import SensorService, SensorServiceError

logger = logging.getLogger("solar_monitor")


def _parse_iso(value: Optional[str], field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp query parameter or raise a ValueError."""
    if not value:
        raise ValueError(f"{field_name} is required")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid {field_name} '{value}'; expected ISO-8601 (e.g. 2026-10-19T08:00:00)"
        ) from exc


def _parse_optional_iso(value: Optional[str], field_name: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid {field_name} '{value}'; expected ISO-8601"
        ) from exc


def _error_response(message: str, status_code: int = 400):
    return jsonify({"error": "invalid_request", "message": message}), status_code


def _not_found(message: str = "Not found"):
    return jsonify({"error": "not_found", "message": message}), 404


def register_api_routes(app, sensor_service: SensorService, history_service: HistoryService):
    """Register all JSON API routes on the given Flask application."""

    # ------------------------------------------------------------------ #
    # Health / status
    # ------------------------------------------------------------------ #
    @app.get("/api/health")
    def health():
        status = sensor_service.status()
        current = sensor_service.current_measurement()
        return jsonify({
            "status": "ok" if status.connected else "degraded",
            "sensor": status.to_dict(),
            "sampling": sensor_service.is_running(),
            "current": current.to_dict() if current else None,
            "utc_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })

    @app.get("/api/status")
    def status():
        return health()

    # ------------------------------------------------------------------ #
    # Current measurement
    # ------------------------------------------------------------------ #
    @app.get("/api/measurements/current")
    def current_measurement():
        reading = sensor_service.current_measurement()
        if reading is None:
            # Fall back to the latest persisted record so the dashboard is
            # never entirely blank after a restart before the first sample.
            reading = history_service.get_latest()
        if reading is None:
            return _not_found("No measurements available yet")
        return jsonify(reading.to_dict())

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #
    @app.get("/api/measurements/history")
    def measurement_history():
        try:
            start = _parse_optional_iso(request.args.get("start"), "start")
            end = _parse_optional_iso(request.args.get("end"), "end")
            limit = request.args.get("limit", type=int)
            if limit is not None and limit <= 0:
                raise ValueError("limit must be a positive integer")
        except ValueError as exc:
            return _error_response(str(exc))

        measurements = history_service.get_range(start=start, end=end, limit=limit)
        return jsonify({
            "count": len(measurements),
            "measurements": [m.to_dict() for m in measurements],
        })

    # ------------------------------------------------------------------ #
    # Energy summary
    # ------------------------------------------------------------------ #
    @app.get("/api/energy/summary")
    def energy_summary():
        try:
            start = _parse_optional_iso(request.args.get("start"), "start")
            end = _parse_optional_iso(request.args.get("end"), "end")
        except ValueError as exc:
            return _error_response(str(exc))

        summary = history_service.get_energy_summary(start=start, end=end)
        return jsonify(summary.to_dict())

    # ------------------------------------------------------------------ #
    # Daily energy
    # ------------------------------------------------------------------ #
    @app.get("/api/energy/daily")
    def daily_energy():
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        daily = history_service.get_daily_energy(
            start_date=start_date, end_date=end_date
        )
        return jsonify({
            "count": len(daily),
            "daily": [d.to_dict() for d in daily],
        })

    # ------------------------------------------------------------------ #
    # Exports
    # ------------------------------------------------------------------ #
    @app.get("/api/export/csv")
    def export_csv():
        try:
            start = _parse_optional_iso(request.args.get("start"), "start")
            end = _parse_optional_iso(request.args.get("end"), "end")
        except ValueError as exc:
            return _error_response(str(exc))

        measurements = history_service.get_range(start=start, end=end)
        if not measurements:
            return _error_response("No measurements in the requested range", 404)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "timestamp", "voltage_v", "current_ma", "current_a", "power_w",
            "shunt_voltage_mv", "bus_voltage_v", "load_voltage_v",
            "sensor_ok", "error_message",
        ])
        for m in measurements:
            d = m.to_dict()
            writer.writerow([
                d["timestamp"], d["voltage_v"], d["current_ma"], d["current_a"],
                d["power_w"], d["shunt_voltage_mv"], d["bus_voltage_v"],
                d["load_voltage_v"], d["sensor_ok"], d["error_message"] or "",
            ])

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": 'attachment; filename="solar_measurements.csv"'},
        )

    @app.get("/api/export/json")
    def export_json():
        try:
            start = _parse_optional_iso(request.args.get("start"), "start")
            end = _parse_optional_iso(request.args.get("end"), "end")
        except ValueError as exc:
            return _error_response(str(exc))

        measurements = history_service.get_range(start=start, end=end)
        if not measurements:
            return _error_response("No measurements in the requested range", 404)
        return jsonify({
            "count": len(measurements),
            "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "measurements": [m.to_dict() for m in measurements],
        })

    # ------------------------------------------------------------------ #
    # Sampling control
    # ------------------------------------------------------------------ #
    @app.post("/api/sampling/start")
    def sampling_start():
        try:
            sensor_service.start_sampling()
        except SensorServiceError as exc:
            return jsonify({"error": "already_running", "message": str(exc)}), 409
        return jsonify({"status": "started", "sampling": True})

    @app.post("/api/sampling/stop")
    def sampling_stop():
        sensor_service.stop_sampling()
        return jsonify({"status": "stopped", "sampling": False})

    @app.get("/api/sampling/status")
    def sampling_status():
        return jsonify({
            "sampling": sensor_service.is_running(),
            "mode": sensor_service.status().mode,
        })
