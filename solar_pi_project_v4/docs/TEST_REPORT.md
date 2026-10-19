# Test Report — Solar Panel Performance Monitor

Generated: Phase 11 (Final Testing, Regression Fixes, Final Audit)
Date: 2026-10-20
Platform: Windows 11, Python 3.12.10, PySide6 6.12.0
Qt Platform: offscreen (QT_QPA_PLATFORM=offscreen)

## Executive Summary

| Metric | Value |
|--------|-------|
| Total tests | 147 |
| Passed | 146 |
| Failed | 0 |
| Skipped | 1 |
| Unexecuted | 0 |

**Overall result: PASS** — all automated tests pass. One test is skipped
because it exercises POSIX file-permission semantics that do not apply on
Windows (covered by the invalid-path OSError test instead).

## Test Suite Breakdown

| Test File | Tests | Passed | Failed | Skipped | Notes |
|-----------|-------|--------|--------|---------|-------|
| test_backup.py | 6 | 6 | 0 | 0 | Backup/restore never overwrites silently |
| test_core_measurement.py | 17 | 17 | 0 | 0 | Measurement models, power, validation, energy |
| test_csv_export_content.py | 8 | 7 | 0 | 1 | CSV schema, filters, errors, BOM, empty data |
| test_database.py | 5 | 5 | 0 | 0 | Flat-layout database shim (legacy API) |
| test_database_src.py | 14 | 14 | 0 | 0 | src/solar_monitor/database (app-data path, DAOs, settings, transactions) |
| test_energy.py | 8 | 8 | 0 | 0 | Trapezoidal energy integration |
| test_gui_pages.py | 7 | 7 | 0 | 0 | Six pages wired to engine/database |
| test_gui_shell.py | 6 | 6 | 0 | 0 | Main window, six nav items, APP OPTIONS, context actions |
| test_hardware_backend.py | 13 | 13 | 0 | 0 | Mock INA219: readings, P=V×I, faults, calibration |
| test_historical_filtering.py | 7 | 7 | 0 | 0 | DAO start/end/range filtering, GUI page filter |
| test_measurement.py | 10 | 10 | 0 | 0 | Flat-layout measurement shim (legacy API) |
| test_measurement_engine.py | 8 | 8 | 0 | 0 | Start/stop/pause/resume, energy, invalid readings, hardware unavailable |
| test_simulation.py | 4 | 4 | 0 | 0 | Simulation plausibility, no Pi imports |
| test_simulation_backend.py | 9 | 9 | 0 | 0 | Realistic simulation: clouds, low-light, noise, faults |
| test_settings_persistence.py | 11 | 11 | 0 | 0 | Settings persistence, validation, no silent mode switch |
| test_sessions.py | 7 | 7 | 0 | 0 | Session DAO |
| test_smoke.py | 2 | 2 | 0 | 0 | --version flag, config defaults |

**Total: 147 | 146 | 0 | 1**

## Test Categories Covered

### Application startup, navigation, resizing, shutdown
- `test_main_window_launches` — window title, minimum size
- `test_has_six_navigation_items` — all 6 sidebar items present
- `test_nav_switch_changes_page` — switching pages via sidebar
- `test_gui_shell.py` — APP OPTIONS button, context-sensitive action button
- `test_gui_pages.py` — all 6 pages load and render

### Measurement calculations, units, validation, timestamps
- `test_core_measurement.py` — validate_reading, compute_power, attach_power, Measurement dataclass
- `test_measurement.py` — flat-layout legacy API compatibility
- `test_energy.py` — trapezoidal integration with known sequences

### Database persistence, migrations, recovery
- `test_database.py` / `test_database_src.py` — schema init, version, migrations, DAOs, settings, backup/restore, transactions, app-data path (not in CWD)
- `test_records_persist_across_restart` — re-open same DB file

### Simulation behavior, deterministic scenarios
- `test_simulation.py` / `test_simulation_backend.py` — plausible V/A/P bounds, clouds, low-light, noise, faults, deterministic seed

### Start, Stop, Pause, Resume lifecycle
- `test_measurement_engine.py` — start/stop (no duplicate worker), pause/resume, stop-when-idle, shutdown-prevents-restart
- `test_gui_pages.py` — UI Start/Stop/Pause/Resume buttons

### Energy integration using known measurement sequences
- `test_energy.py` — trapezoidal rule, constant power, irregular intervals, gap handling, invalid sample breaks chain
- `test_measurement_engine.py` — known-sequence energy (0.5 W → 1.0 W trapezoid)

### Chart updates and GUI responsiveness
- `test_gui_pages.py` — dashboard receives measurements and updates graph
- `test_graph_widget.py` — bounded data buffers, time-window cutoff, clear, history resize

### Historical filtering and actual CSV contents
- `test_historical_filtering.py` — DAO start/end/range filtering, GUI page filter application
- `test_csv_export_content.py` — CSV schema match, values match measurements, filter-matching exports

### Settings persistence and diagnostics
- `test_settings_persistence.py` — persistence across restart, validation, no silent mode switch
- `test_gui_pages.py` — settings page save interval/mode

### Missing hardware, invalid readings, sensor disconnection
- `test_hardware_backend.py` — hardware unavailable → BackendError, invalid reading → fault, never accumulated

### Thread safety, repeated scans, worker cleanup
- `test_measurement_engine.py` — no duplicate workers, stop joins worker thread, shutdown prevents restart

### Installation and dependency compatibility
- `test_core_measurement.py::test_core_imports_without_pi` — no board/busio/adafruit/rpi/gpiozero/smbus in core
- `test_simulation.py::test_no_pi_imports` — no Pi imports in simulation
- `test_hardware_backend.py::test_no_adafruit_import_at_module_level` — lazy import only

## Manual Verification Steps Performed

1. `python main.py --version` → "Solar Panel Performance Monitor v1.0.0-dev"
2. `python main.py` launches resizable window with dark charcoal title bar (Windows immersive dark mode)
3. All 6 pages navigate via left sidebar
4. Context-sensitive bottom-right button: "Start monitoring" (Live Monitoring), "Export CSV…" (CSV Reports), hidden elsewhere
5. Bottom-left APP OPTIONS button present
6. Live graphs render voltage/current/power with bounded buffers
7. Hardware backend reports "unavailable" on Windows (no Pi) and raises honest error instead of simulating

## Known Limitations

1. **Genuine INA219 hardware cannot be tested on Windows.** Hardware backend tests are mock-based (13 tests). Real Pi + INA219 hardware tests remain pending:
   - Genuine I²C readings from physical sensor
   - Calibration verification against known load (33 Ω, 6 V panel)
   - INA219 initialization failure on real hardware
   - Sensor disconnection mid-run
   - Hardware mode never silently falls back to simulation (on real Pi)

2. **`pytest-qt` is not installed.** GUI tests use plain pytest + offscreen QApplication rather than pytest-qt fixtures. This is a test-infrastructure limitation, not a functional one.

3. **One test skipped on Windows:** `test_csv_permission_error_on_readonly_dir` skips because the POSIX file-permission model does not apply on Windows. The equivalent invalid-path OSError path is covered by `test_csv_invalid_path_raises_oserror`.

4. **Live graph uses a single shared y-axis** (V dominates scale). Separate y-axes per curve is a future refinement.

## Regressions Fixed in Phase 11

None — all 146 tests pass with zero failures. No regressions introduced.

## Pending Work (Phase 12)

- Documentation finalization, GitHub release, Raspberry Pi deployment
- Push commits and tags to GitHub remote (remote not yet configured)
- Physical sensor tests on Raspberry Pi 3 Model A+ + INA219

## Git Status

- Branch: `main`
- Last commit: `7d33162` (Phase 11) — Phase 12 docs pending push
- Tags: phase-1-complete through phase-11-complete
- Remote: none configured (push pending, awaiting GitHub URL)
- Working tree: clean
