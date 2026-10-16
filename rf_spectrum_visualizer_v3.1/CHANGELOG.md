# RF Spectrum Visualizer v3.1 — Changelog

## [3.1.0] — 2026-10-16

### Added
- **Phase 1 — GUI skeleton**: Dark navy sidebar, light workspace, crimson accents; exactly three sidebar items (Live Spectrum, Start Analysis, Blocker); same-window page navigation.
- **Phase 2 — Live Spectrum integration**: Real V3 nRF24L01+ scanner (ScannerThread, SpectrumData, ChannelObservation, SimRadio, HardwareRadio) connected via read-only `v3_bridge.py`; scan all 126 channels (0–125); frequency = `2400 + channel_number` MHz; live spectrum bar chart; channel activity table; Start/Stop Scan controls; Hardware/Simulation modes; scanner status, scan progress, busiest channel, average activity; thread-safe GUI updates via Tk `after()` polling; clean shutdown.
- **Phase 3 — Start Analysis integration**: Working Start Analysis button; summary cards (channels analyzed, busiest channel, average activity, recommended clear channels); channel activity comparison chart; results table (Channel, Freq MHz, Activity %, Status, Recommendation); Clear/Moderate/Busy/Heavy Load classifications via configurable thresholds; staleness detection (60s); no fake measurements.
- **Phase 4 — Blocker persistence**: Software-level channel exclusion with persistent JSON storage (`blocker_exclusions.json`); add/remove/clear with confirmation dialogs; channel validation 0–125; duplicate prevention; excluded channels omitted from Analysis recommendations but remain visible in Live Spectrum; corrupted/missing/malformed storage file recovery.
- **Phase 5 — Complete integration & testing**: Cross-module integration tests (15 tests); regression tests; HOW_TO_USE_GUIDE.md; HARDWARE_SETUP.md; code quality fixes (utils/constants.py imports, requirements.txt, .gitignore).

### Changed
- `config.py`: Added `ChannelConfig`, `ScanConfig`, `ThresholdConfig`, `StorageConfig`, `GUIConfig` dataclasses compatible with V3 `ScannerThread`; added `get_frequency_mhz()`, `validate_channel()`, `get_channel_label()` helpers.
- `gui/start_analysis_page.py`: Removed dead `set_blocked_channels()` method.
- `utils/constants.py`: Fixed broken imports (re-export `RF_CHANNEL_*` constants).
- `requirements.txt`: Removed unused `customtkinter`; added `matplotlib>=3.8.0`, `pytest>=7.0.0`.
- `.gitignore`: Removed self-referencing entry; added `blocker_exclusions.json`, `.blocker_*.tmp`.

### New files
- `main.py` — Tkinter application entry point.
- `src/rf_spectrum_visualizer/v3_bridge.py` — Read-only bridge to V3 scanner modules.
- `src/rf_spectrum_visualizer/gui/sidebar.py` — Three-item navigation sidebar.
- `src/rf_spectrum_visualizer/gui/theme.py` — Colors, fonts, styles.
- `src/rf_spectrum_visualizer/gui/canvas.py` — Matplotlib TkAgg canvas.
- `src/rf_spectrum_visualizer/gui/live_spectrum_page.py` — Live Spectrum page.
- `src/rf_spectrum_visualizer/gui/start_analysis_page.py` — Start Analysis page.
- `src/rf_spectrum_visualizer/gui/blocker_page.py` — Blocker page with persistence.
- `src/rf_spectrum_visualizer/utils/channel.py` — Channel validation/frequency helpers.
- `src/rf_spectrum_visualizer/utils/persistence.py` — Atomic JSON persistence for exclusions.
- `tests/` — 74 tests (72 pass, 2 skipped — hardware unavailable).
- `docs/HARDWARE_SETUP.md` — Raspberry Pi wiring & setup.
- `docs/HOW_TO_USE_GUIDE.md` — User guide.
- `docs/TEST_REPORT.md` — Detailed test report.
- `run_windows.bat` — Windows launch script.
- `run_raspberry_pi.sh` — Raspberry Pi launch script.
- `run_sim.py` — Python simulation mode launcher.
- `install_windows.ps1` — Windows installation script.
- `install_raspberry_pi.sh` — Raspberry Pi installation script.
- `CHANGELOG.md` — This file.

### Not implemented (deferred to future phases)
- CSV/JSON export.
- Packaging (`pyproject.toml`, entry points).
- Hardware mode is not tested on this machine (no Raspberry Pi, no pyrf24).

### Source preservation
- The original V3 (`workshop/v3`) and V6 (`workshop/v6`) projects are never modified.
- V3 scanner code is imported read-only via `v3_bridge.py`.
