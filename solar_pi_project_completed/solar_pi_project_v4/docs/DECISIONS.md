# Architectural Decisions

## GUI: PySide6 + pyqtgraph
- PySide6 for the desktop GUI; pyqtgraph for bounded, performant live graphs.
- Matplotlib is NOT a dependency.

## Storage: stdlib sqlite3
- WAL mode, parameterized SQL only, schema version in `PRAGMA user_version`.

## CSV: stdlib csv
- UTF-8 with BOM (`utf-8-sig`), write to temp then atomically rename.

## Tests: pytest + pytest-qt
- `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` via `os.environ.setdefault`.

## INA219 driver: adafruit-circuitpython-ina219
- In `requirements-pi.txt` only; lazy import in hardware backend; Windows unaffected.

## Simulation vs Hardware
- Explicit user choice, shown in header. Honest error states on failure. Every simulated record labeled.