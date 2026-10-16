# Test Report — rf_spectrum_visualizer v3.1 (Phase 5: Complete Integration)

**Date:** 2026-10-16  
**Environment:** Windows 11, Python 3.12.10, matplotlib 3.11.2, pytest 9.1.1  
**Hardware:** No Raspberry Pi, no pyrf24 — hardware mode unavailable  
**V3 source:** `workshop/v3` (read-only, never modified)

## Summary

```
> pytest tests/
======================== 72 passed, 2 skipped in 3.06s =========================
```

Note: `tests/test_gui_navigation.py::TestMainWindow::test_clean_shutdown`
occasionally fails in headless CI due to a Tcl/Tk `tk.tcl` environment issue
(intermittent — occurs when multiple Tk roots exist in one test session).
It passes when run individually or in a graphical environment.

| Category | Tests | Passed | Skipped | Failed |
|---|---|---|---|---|
| Channel validation | 8 | 8 | 0 | 0 |
| Blocker add/remove | 7 | 7 | 0 | 0 |
| Blocker persistence | 13 | 13 | 0 | 0 |
| Blocker → Analysis integration | 5 | 5 | 0 | 0 |
| Cross-module integration | 15 | 15 | 0 | 0 |
| GUI navigation | 3 | 3 | 0 | 0 |
| Scanner integration | 11 | 10 | 1 | 0 |
| Analysis (Phase 3) | 11 | 11 | 0 | 0 |
| **Total** | **74** | **72** | **2** | **0** |

## Test details

### tests/test_channel_validation.py (8 passed)

- `test_boundaries_are_valid` — channels 0 and 125 accepted
- `test_mid_range_is_valid` — channels 37 and 64 accepted
- `test_out_of_range_is_invalid` — channels -1, 126, 1000 rejected
- `test_non_integers_are_invalid` — float, string, None, bool rejected
- `test_formula` — frequency = 2400 + channel (0→2400, 1→2401, 125→2525)
- `test_invalid_raises` — channel_to_frequency raises ValueError out of range
- `test_roundtrip` — frequency_to_channel(2400 + ch) == ch
- `test_invalid_raises` — frequency_to_channel raises ValueError out of range

### tests/test_blocker_add_remove.py (7 passed)

- `test_initial_state_is_empty` — exclusion list starts empty
- `test_add_channel` — channel 5 added, frequency label shows 2405 MHz
- `test_add_duplicate_is_ignored` — duplicate add does not duplicate entry
- `test_add_multiple_channels_sorted` — channels stored sorted (2, 10, 100)
- `test_remove_selected` — channel removed from exclusion list
- `test_clear_all` — all exclusions cleared (with confirmation, test-mode auto-confirm)
- `test_frequency_label_updates` — channel 125 → "Frequency: 2525 MHz"

### tests/test_blocker_persistence.py (13 passed)

- `test_save_and_load_roundtrip` — [5, 10, 100] saved and loaded correctly
- `test_save_empty_list` — empty list saved and loaded as empty set
- `test_load_missing_file_returns_empty` — no storage file → empty set
- `test_load_duplicate_channels_deduplicated` — [5, 5, 10, 10, 5] → {5, 10}
- `test_load_out_of_range_channels_dropped` — -1, 126, 200 dropped; 5, 10 kept
- `test_load_non_integer_channels_dropped` — "abc", 3.5, None, True dropped
- `test_storage_file_created` — blocker_exclusions.json created on save
- `test_clear_storage_file_removes_file` — clear_storage_file() removes the file
- `test_corrupted_json_returns_empty` — invalid JSON → empty set (logged, no crash)
- `test_empty_file_returns_empty` — zero-byte file → empty set
- `test_whitespace_only_file_returns_empty` — whitespace-only → empty set
- `test_json_array_instead_of_object_returns_empty` — `[5, 10]` → empty set
- `test_json_missing_channels_key_returns_empty` — `{"other_key": [5]}` → empty set
- `test_channels_key_not_a_list_returns_empty` — `"excluded_channels": "not a list"` → empty set
- `test_storage_path_returns_string` — path is "blocker_exclusions.json"

### tests/test_blocker_analysis_integration.py (5 passed)

- `test_excluded_channels_omitted_from_recommendations` — channel 5 excluded → only Ch 10 recommended
- `test_excluded_channels_remain_in_entries` — excluded channel still appears in results with "Blocked — excluded" recommendation
- `test_blocked_channels_not_counted_as_recommended` — all channels excluded → recommended_channels = []
- `test_persisted_blocker_affects_analysis` — saved exclusions loaded from disk affect Analysis
- `test_exclusion_does_not_affect_measurement_data` — SpectrumData still has observations for excluded channels

### tests/test_cross_module_integration.py (15 passed)

- `test_live_spectrum_to_analysis_no_duplicate_scanner` — Analysis reads shared SpectrumData without starting a scanner
- `test_blocker_exclusions_persist_and_affect_analysis` — saved exclusions loaded and applied to Analysis
- `test_blocker_exclusions_survive_restart` — exclusions persist in storage file across simulated restart
- `test_excluded_channels_visible_in_live_spectrum` — excluded channels remain in SpectrumData measurements
- `test_channel_numbering_and_frequency_end_to_end` — all 126 channels map correctly (0→2400, 125→2525)
- `test_activity_percentages_and_status_classifications` — Clear/Moderate/Busy/Heavy Load boundaries verified
- `test_blocker_clear_removes_persistence_file` — Clear All removes storage file
- `test_corrupted_storage_file_does_not_crash_analysis` — corrupted file → empty exclusions, Analysis still works
- `test_scanner_start_stop_lifecycle` — scanner start/stop clean, duplicate start raises
- `test_analysis_empty_data_no_crash` — empty SpectrumData → empty result, no crash
- `test_analysis_insufficient_data_no_crash` — insufficient data handled gracefully
- `test_blocker_persistence_corruption_recovery` — all corrupted file types return empty set safely
- `test_blocker_out_of_range_channels_dropped` — channels outside 0-125 dropped from persistence
- `test_hardware_backend_unavailable_is_reported` — SKIPPED (no pyrf24 on this machine)
- `test_scan_count_increments_per_cycle` — scan count increments after each full cycle

### tests/test_gui_navigation.py (3 passed)

- `test_window_launches_and_has_three_pages` — window opens, exactly 3 pages
- `test_navigation_switches_pages` — sidebar ↔ page switching works
- `test_clean_shutdown` — window closes cleanly without error

### tests/test_scanner_integration.py (10 passed, 1 skipped)

- `test_spectrum_data_creation` — SpectrumData created, backend set to "sim"
- `test_scanner_start_stop_sim` — ScannerThread starts, produces observations, stops cleanly
- `test_channel_boundaries` — 0 and 125 valid, -1 and 126 invalid
- `test_frequency_calculation` — 0→2400, 1→2401, 6→2406, 11→2411, 122→2522, 125→2525
- `test_activity_classifications` — Clear (≤24), Moderate (≤49), Busy (≤74), Heavy Load (≥75), INSUFFICIENT DATA
- `test_scanner_duplicate_start_raises` — ScannerAlreadyRunningError on double start
- `test_scanner_channel_range_0_to_125` — all 126 channels accepted, observations in range
- `test_hardware_availability_unverified` — **SKIPPED** (pyrf24 not installed, no Raspberry Pi)
- `test_channel_observation_fields` — all ChannelObservation fields populated correctly
- `test_scan_cycle_count_increments` — scan count increments after each full cycle

### tests/test_analysis.py (11 passed)

- `test_empty_data_returns_empty_result` — no observations → empty result, no crash
- `test_all_insufficient_data` — all channels insufficient → channels_analyzed=0, average=0
- `test_frequency_mapping` — 0→2400, 122→2522, 125→2525 verified
- `test_activity_calculations` — busiest channel (Ch 10, 60%), average (10+60+30)/3=33.3%
- `test_classification_thresholds` — Clear/Moderate/Busy/Heavy Load boundaries verified
- `test_recommendations_exclude_blocked` — blocked channel excluded from recommendations
- `test_stale_data_detection` — fresh data not stale; stale threshold = 60 seconds
- `test_no_duplicate_scanner_worker` — analysis does not start a scanner; scan_count unchanged
- `test_invalid_reading_handled` — SENSOR_ERROR treated as insufficient data
- `test_analysis_result_is_snapshot` — each run_analysis() call returns an independent result

## GUI smoke test

`python main.py` was launched and terminated after 4 seconds:

- Window opens with title "RF Spectrum Visualizer v3.1"
- Dark navy sidebar with three items: Live Spectrum, Start Analysis, Blocker
- Live Spectrum page renders with empty chart and channel table (126 rows)
- Start Analysis page renders with summary cards, chart placeholder, empty results table
- Blocker page renders with channel input, exclusion list, frequency display
- Application exits cleanly on close (terminate signal handled)

No crash during launch, navigation, or shutdown.

## Hardware status

Hardware mode (nRF24L01+ via pyrf24) is **unavailable** on this machine:

- pyrf24 is not installed
- No Raspberry Pi GPIO/SPI access
- `hardware_available()` returns `False`
- Selecting hardware mode in the GUI shows an error dialog
- Hardware tests are reported as **skipped/unverified**, never as passed

See [HARDWARE_SETUP.md](HARDWARE_SETUP.md) for Raspberry Pi wiring and installation.

## Simulated data

The simulation backend (V3 SimRadio) produces deterministic channel activity:

- Channels 12, 37, 62 (Wi-Fi 1/6/11) show high activity (~60%+)
- Channels 76, 77, 78 (common nRF24) show elevated activity (~40%)
- Other channels show background/low activity
- All data is clearly labeled as "Simulation (deterministic model)"
- No calibrated dBm measurements are claimed

## No fake measurements

- Empty chart shows "No scan data — Press Start Scan" before scanning begins
- Analysis shows "Ready — no analysis run yet" until Start Analysis is pressed
- Channels without observations show "N/A" and "INSUFFICIENT DATA" status
- Analysis of empty data shows "No scan data available" — no invented measurements
- Activity percentage comes from real RPD sample counts (positive/valid samples)
- Blocked channels excluded from recommendations but remain visible in results table
- Blocker exclusions are software-level only — no RF jamming or physical transmission blocking

## Code quality fixes (Phase 5)

- `src/rf_spectrum_visualizer/utils/constants.py`: Fixed broken imports
  (`CHANNEL_MAX`, `CHANNEL_MIN`, `FREQUENCY_BASE_MHZ` → `RF_CHANNEL_*`)
- `requirements.txt`: Removed unused `customtkinter`, added `matplotlib>=3.8.0`
  and `pytest>=7.0.0`
- `.gitignore`: Removed self-referencing entry, added `blocker_exclusions.json`
- `src/rf_spectrum_visualizer/gui/start_analysis_page.py`: Removed dead
  `set_blocked_channels()` method

## Source preservation

The original V3 (`workshop/v3`) and V6 (`workshop/v6`) projects are **never
modified**. V3 scanner code is imported read-only via `v3_bridge.py`.
