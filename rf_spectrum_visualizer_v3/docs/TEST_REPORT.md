# Test Report — RF Spectrum Visualizer V3 (Phase 2: Live Spectrum)

**Date:** 2026-10-16  
**Environment:** Windows, Python 3.12.10, pytest 9.1.1, tkinter, matplotlib, numpy  
**Hardware:** No Raspberry Pi, no `pyrf24`, no `spidev` — hardware mode is **untested on real hardware**.  
**Scope:** Phase 2 — Live Spectrum integration only. Analysis and Blocker backends are deliberately not implemented.

## Test suite: `tests/test_live_spectrum.py`

**Result: 13 passed, 0 failed.**

| Test class | Test | Result |
|---|---|---|
| TestChannelMapping | test_boundary_channels | PASSED |
| TestChannelMapping | test_all_126_channels | PASSED |
| TestChannelMapping | test_out_of_range_channel_raises | PASSED |
| TestChannelMapping | test_validate_channel_accepts_valid | PASSED |
| TestActivityClassification | test_clear_moderate_busy_heavy | PASSED |
| TestActivityClassification | test_insufficient_data | PASSED |
| TestScannerLifecycle | test_start_stop | PASSED |
| TestScannerLifecycle | test_duplicate_start_raises | PASSED |
| TestScannerLifecycle | test_all_channels_scanned_with_freq | PASSED |
| TestScannerLifecycle | test_hardware_unavailable_no_fake_readings | PASSED |
| TestGuiResponsiveness | test_app_creates_and_updates_without_crash | PASSED |
| TestGuiResponsiveness | test_status_bar_reports_busiest_and_average | PASSED |
| TestGuiResponsiveness | test_switching_mode_while_stopped | PASSED |

## What was verified

### Channel boundaries & frequency calculations
- All 126 channels (0–125) scan successfully.
- Frequency = `2400 + channel_number` MHz verified for every channel:
  - Ch 0 → 2400 MHz, Ch 1 → 2401 MHz, Ch 125 → 2525 MHz.
- Out-of-range channels (−1, 126) raise `InvalidChannelError`.
- `validate_channel()` accepts 0 and 125, rejects −1 and 126.

### Activity classifications (ThresholdConfig)
Thresholds: Clear ≤24%, Moderate ≤49%, Busy ≤74%, Heavy Load ≥75%.
- 0 / 24 → Clear; 25 / 49 → Moderate; 50 / 74 → Busy; 75 / 100 → Heavy Load.
- `None` (insufficient samples) → `INSUFFICIENT DATA`.

### Scanner start/stop / lifecycle
- Start → running; stop → not running.
- Duplicate start raises `ScannerAlreadyRunningError` (no duplicate threads).
- `shutdown()` forces stop with timeout; radio `cleanup()` releases resources.
- All channels produce observations with `frequency_mhz == 2400 + channel`
  and `backend == "sim"`.

### GUI responsiveness
- Live Spectrum window launches and updates chart + table while scanning.
- Status bar reports busiest channel and average activity during a scan.
- Mode switching (Simulation ↔ Hardware) works while stopped.
- UI refresh driven by `tk.after` (main thread only); scanning runs on a
  background thread — the GUI does not block.

### Error handling
- Hardware mode without `pyrf24`: `ScannerError` raised, scanner not started,
  **zero observations** (no fake readings), no crash; user shown a dialog.
- Per-channel scan errors are caught and logged as `SENSOR_ERROR` observations
  rather than crashing the scanner thread.

## Hardware tests — UNVERIFIED

No Raspberry Pi and no `pyrf24`/`spidev` are available in this environment.
Per the project rules, hardware tests are reported as **unverified**, not
passed. The hardware code path is exercised only as error handling (missing
`pyrf24` → graceful error dialog). Real nRF24L01+ RPD measurements on a Pi
have not been performed.

## Items NOT tested (out of Phase 2 scope)

- Original V3 / V6 test suites (source projects not modified; not re-run here).
- Analysis / Blocker backends and their GUI pages (rule: not implemented yet).
- Waterfall view, table sorting/filtering, CSV/JSON export (deferred).
- Blocklist persistence, block/unblock, recommendations.
- Import/export round-trips.

## Commands used

Run the Live Spectrum GUI:

```
cd rf_spectrum_visualizer_v3
python run_live_spectrum.py
```

Run the Phase 2 tests:

```
cd rf_spectrum_visualizer_v3
python -m pytest tests/test_live_spectrum.py -v
```
