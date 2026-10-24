"""Solar Panel Performance Monitor application package.

Provides the Flask application factory :func:`create_app`.
"""

from __future__ import annotations

import logging

from flask import Flask

from app.api import register_api_routes
from app.config import Config, load_config
from app.database import Database
from app.routes import register_web_routes
from app.services.history_service import HistoryService
from app.services.sensor_service import SensorService

__version__ = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def create_app(config: Config | None = None) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    config:
        Optional pre-built :class:`~app.config.Config`. When omitted,
        configuration is loaded from ``.env`` / ``config.json`` / environment
        variables via :func:`load_config`.
    """
    if config is None:
        config = Config.from_dict(load_config())
    config.validate()

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=config.secret_key,
        DATABASE_PATH=config.database_path,
        SENSOR_MODE=config.sensor_mode,
        SAMPLING_INTERVAL_SECONDS=config.sampling_interval_seconds,
    )

    # Wire services together.
    database = Database(config.database_path)
    sensor_service = SensorService(config, database)
    history_service = HistoryService(database)

    # Register routes.
    register_web_routes(app, sensor_service, history_service)
    register_api_routes(app, sensor_service, history_service)

    # Stash services on the app for access in run.py / tests.
    app.solar_config = config
    app.solar_database = database
    app.sensor_service = sensor_service
    app.history_service = history_service

    return app
