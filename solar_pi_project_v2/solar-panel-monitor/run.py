"""Entry point for the Solar Panel Performance Monitor.

Usage (Windows / Raspberry Pi):

    python run.py

The app reads configuration from ``.env`` and ``config.json`` (or environment
variables), binds to the configured host/port, and starts the background
sampler automatically. Press Ctrl-C to shut down gracefully.
"""

from __future__ import annotations

import signal
import sys

from app import create_app

app = create_app()


def _handle_shutdown(signum, frame):  # pragma: no cover - runtime signal handling
    app.sensor_service.shutdown()
    sys.exit(0)


def main() -> None:
    config = app.solar_config
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    print(f"Solar Panel Performance Monitor v{__import__('app').__version__}")
    print(f"Mode: {config.sensor_mode} | Interval: {config.sampling_interval_seconds}s")
    print(f"Database: {config.database_path}")
    print(f"Dashboard: http://{config.host}:{config.port}/")
    print("Press Ctrl-C to stop.")

    # Start background sampling automatically.
    try:
        app.sensor_service.start_sampling()
    except Exception as exc:  # noqa: BLE001 - don't crash the web server on sample failure
        print(f"Warning: could not start sampler: {exc}")

    app.run(host=config.host, port=config.port, debug=config.debug, use_reloader=False)


if __name__ == "__main__":
    main()
