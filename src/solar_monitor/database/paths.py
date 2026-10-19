"""User-writable application-data directory and default database path.

The production database lives in the OS application-data directory, never
in the current working directory, so the application works regardless of
where it is launched from and keeps user data in a single, backed-up place.
"""

from __future__ import annotations

import os
import sys

APP_NAME = "Solar Panel Performance Monitor"
DB_FILENAME = "solar_measurements.db"


def app_data_dir(app_name: str = APP_NAME) -> str:
    """Return a user-writable application-data directory.

    Windows: %APPDATA%\\<App Name> (falls back to ~)
    Linux/macOS: ~/.local/share/<App Name>
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, app_name)
    return os.path.join(os.path.expanduser("~"), ".local", "share", app_name)


def ensure_data_dir() -> str:
    """Create (if missing) and return the application-data directory."""
    directory = app_data_dir()
    os.makedirs(directory, exist_ok=True)
    return directory


def default_db_path() -> str:
    """Return the default production database path inside app-data."""
    ensure_data_dir()
    return os.path.join(app_data_dir(), DB_FILENAME)
