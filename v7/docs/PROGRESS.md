# Progress - rf_spectrum_visualizer v3.1

Phase status: **in progress** (Phase 3 - GUI shell + Live Spectrum page).

## Phase 1 - Scaffold + hardware check scripts (APPROVED)

Tag `v3.1-phase1` pushed. Files: `__init__.py`, `__main__.py`, `test_placeholder.py`,
`check_radio.py`, `check_rpd.py`, `hardware_check.md`, `PROGRESS.md`, `pyproject.toml`,
`.gitignore`, `README.md`.

Test results reported by me: 2 passed (dev machine).
Test results reported by you: check_radio PASS, check_rpd PASS on Pi.

## Phase 2 - Scan backend (APPROVED)

Tag `v3.1-phase2` pushed. Files: `scan_backend.py`, `test_scan_backend.py`.

Dev-machine pytest: 23 passed.
Test results reported by you: HardwareBackend open + scan OK on real Pi radio
(0.0% on ch 100, 3.0% on ch 37, 4.0% on ch 62).

## Phase 3 - GUI shell + Live Spectrum page (in progress)

New files:
- `src/rf_spectrum_visualizer/gui/__init__.py`
- `src/rf_spectrum_visualizer/gui/theme.py` (palette, thresholds, activity_color/channel_status/row_tint)
- `src/rf_spectrum_visualizer/gui/main_window.py` (sidebar, pages, status bar; no window at import time)
- `src/rf_spectrum_visualizer/gui/pages/__init__.py`
- `src/rf_spectrum_visualizer/gui/pages/live_spectrum.py` (toolbar, table, bar chart, log, scan worker)
- `src/rf_spectrum_visualizer/gui/pages/start_analysis.py` (stub)
- `src/rf_spectrum_visualizer/gui/pages/blocker.py` (stub)
- `src/rf_spectrum_visualizer/scan_worker.py` (background thread + queue)
- `tests/test_phase3.py` (theme + scan worker tests)

Dev-machine pytest: 32 passed total.
Could NOT verify without hardware: HardwareBackend end-to-end in GUI (fallback path
tested with mock). Tkinter window creation not tested headless (Windows dev machine
has Tkinter; Pi OS Tkinter not yet verified).

Open issues:
- Tkinter on Raspberry Pi OS not yet verified (Phase 3 runtime test).
- Matplotlib on Pi OS not yet verified.
