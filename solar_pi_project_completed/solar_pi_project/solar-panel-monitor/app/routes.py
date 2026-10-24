"""Web page routes for the Solar Panel Performance Monitor dashboard."""

from __future__ import annotations

from flask import render_template

from app.services.sensor_service import SensorService


def register_web_routes(app, sensor_service: SensorService, history_service: HistoryService):
    """Register server-side page routes on the given Flask application."""

    @app.get("/")
    def index():
        status = sensor_service.status()
        current = sensor_service.current_measurement()
        return render_template(
            "index.html",
            status=status.to_dict() if status else {},
            current=current.to_dict() if current else None,
        )

    @app.get("/health")
    def web_health():
        status = sensor_service.status()
        return {
            "status": "ok" if status.connected else "degraded",
            "sensor": status.to_dict(),
            "sampling": sensor_service.is_running(),
        }
