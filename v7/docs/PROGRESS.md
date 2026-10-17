# Progress - rf_spectrum_visualizer v3.1

Phase status: **in progress** (Phase 2 - scan backend).

## Phase 1 - Scaffold + hardware check scripts (APPROVED)

Files:
- `src/rf_spectrum_visualizer/__init__.py` (version "3.1.0", UI v3.1)
- `src/rf_spectrum_visualizer/__main__.py` (placeholder)
- `tests/test_placeholder.py` (trivial passing test)
- `scripts/check_radio.py` (PASS on Pi: begin()=True, is PVariant=True)
- `scripts/check_rpd.py` (PASS on Pi: Activity % table, no traceback)
- `docs/hardware_check.md`, `docs/PROGRESS.md`, `pyproject.toml`, `.gitignore`, `README.md`
- Tag `v3.1-phase1` pushed.

Test results reported by me: 23 passed (dev machine).
Test results reported by you: check_radio PASS, check_rpd PASS on Pi.

## Phase 2 - Scan backend (in progress)

New files:
- `src/rf_spectrum_visualizer/scan_backend.py` (ChannelStats, ScanBackend ABC, SimBackend, HardwareBackend)
- `tests/test_scan_backend.py` (17 new tests)

Dev-machine pytest: 23 passed total.
Could NOT verify without hardware: HardwareBackend.open()/scan_channel() on real pyrf24/radio.

Open issues:
- pyrf24 0.6.0 enum names (RF24_CRC_DISABLED, RF24_1MBPS) confirmed via check_rpd.py fix on Pi.
- Tkinter behavior on Pi OS not yet verified (Phase 3).
