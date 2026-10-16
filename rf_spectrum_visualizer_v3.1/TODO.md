# TODO — rf_spectrum_visualizer v3.1

## Phase 1 — GUI skeleton (DONE)
- [x] Project structure: main.py, src/rf_spectrum_visualizer/{__init__,config,constants,gui,utils}, tests/, docs/, assets/
- [x] Theme: dark navy sidebar, light workspace, crimson accents (Tkinter)
- [x] Sidebar: exactly three items (Live Spectrum, Start Analysis, Blocker)
- [x] Page navigation via frame switching (same window)
- [x] Live Spectrum page stub: empty chart, channel table, scan buttons
- [x] Start Analysis page stub: summary cards, chart placeholder, results table
- [x] Blocker page stub: channel input (0-125), Add/Remove/Clear, temporary list
- [x] Channel validation + `2400 + channel_number` frequency calculation

## Phase 2 — Live Spectrum integration (DONE)
- [x] Inspect V3 source files (scanner.py, sim_radio.py, hardware_radio.py, config.py, exceptions.py)
- [x] Create v3_bridge.py for read-only import of V3 scanner modules
- [x] Expand config.py with V3-compatible ChannelConfig, ScanConfig, ThresholdConfig
- [x] Connect Live Spectrum page to V3 ScannerThread (background thread)
- [x] Scan all 126 channels (0–125), frequency = 2400 + channel_number
- [x] Live spectrum chart (activity % by channel, color-coded by status)
- [x] Channel activity table with status labels (Clear/Moderate/Busy/Heavy Load)
- [x] Working Start Scan / Stop Scan controls (no duplicate threads)
- [x] Hardware and Simulation modes, clearly distinguished
- [x] Scanner status, scan progress, busiest channel, average activity
- [x] Thread-safe GUI updates via Tk after() polling
- [x] Clean shutdown on stop / window close
- [x] Hardware errors caught without crashing, no fake readings
- [x] Shared SpectrumData available for future Analysis page
- [x] Unit tests: channel validation, frequency, classifications, scanner start/stop, GUI navigation

## Phase 3 — Start Analysis integration (DONE)
- [x] Connect Start Analysis page to shared SpectrumData (no second scanner)
- [x] Working Start Analysis button with status indicators
- [x] Summary cards: channels analyzed, busiest channel, average activity, recommended clear channels
- [x] Channel activity bar chart, color-coded by status, threshold lines
- [x] Results table: Channel, Freq (MHz), Activity (%), Status, Recommendation
- [x] Frequency formula: `2400 + channel_number` MHz
- [x] Status classification: Clear/Moderate/Busy/Heavy Load via configurable thresholds
- [x] Blocker exclusion interface for recommendations (no blocker data invented)
- [x] Handles missing data, insufficient scans, invalid readings, analysis errors
- [x] Data freshness / staleness indicators (data older than 60s = stale)
- [x] No fake measurements invented
- [x] Unit tests: activity calculations, frequency, empty/invalid/stale data, blocker exclusion, no duplicate scanner

## Phase 4 — Blocker backend (DONE)
- [x] Persistent blocker storage (JSON file: blocker_exclusions.json)
- [x] Persistence across application restarts (exclusions loaded on BlockerPage init)
- [x] Add/Remove/Clear with confirmation dialogs (auto-confirm in test mode)
- [x] Channel validation 0-125 with clear error messages
- [x] Duplicate entry prevention
- [x] Excluded channels omitted from Analysis recommendations
- [x] Excluded channels remain visible in Live Spectrum measurements
- [x] Corrupted/missing/malformed storage file recovery (safe defaults)
- [x] Software-level exclusion disclaimer (not RF jamming/physical blocking)
- [x] Unit tests: persistence save/load, corruption recovery, invalid data, Blocker→Analysis integration

## Phase 5 — Complete Integration, Testing, and Finalization (DONE)
- [x] Reviewed entire codebase for integration errors, bugs, inconsistent interfaces
- [x] Fixed utils/constants.py broken imports (CHANNEL_MAX → RF_CHANNEL_MAX, etc.)
- [x] Fixed requirements.txt (removed unused customtkinter, added matplotlib + pytest)
- [x] Fixed .gitignore (removed self-referencing entry, added blocker_exclusions.json)
- [x] Removed dead code (set_blocked_channels from start_analysis_page.py)
- [x] Verified Live Spectrum → Analysis data flow (no duplicate scanner instances)
- [x] Verified Blocker exclusions persist across restarts and apply to Analysis
- [x] Confirmed excluded channels remain visible in Live Spectrum measurements
- [x] Verified channel numbering (0–125), frequency (2400 + channel), activity %, status classifications
- [x] Tested Hardware and Simulation modes (hardware unverified — no Raspberry Pi)
- [x] Verified GUI navigation, responsiveness, error handling, clean shutdown
- [x] Checked imports, dependencies, configuration, logging, file paths
- [x] Added regression tests: test_cross_module_integration.py (15 tests)
- [x] Created docs/HOW_TO_USE_GUIDE.md
- [x] Created docs/HARDWARE_SETUP.md
- [x] Updated README.md, TODO.md, docs/TEST_REPORT.md

## Testing
- [x] tests/test_channel_validation.py — 8 passed
- [x] tests/test_blocker_add_remove.py — 7 passed
- [x] tests/test_blocker_persistence.py — 13 passed
- [x] tests/test_blocker_analysis_integration.py — 5 passed
- [x] tests/test_cross_module_integration.py — 15 passed
- [x] tests/test_gui_navigation.py — 3 passed
- [x] tests/test_scanner_integration.py — 10 passed, 1 skipped (hardware unavailable)
- [x] tests/test_analysis.py — 11 passed
- [x] docs/TEST_REPORT.md — detailed report
- [ ] Hardware tests on Raspberry Pi (unverified — no hardware available)

## Remaining issues
- Hardware mode unavailable on this machine (pyrf24 not installed, no Raspberry Pi)
- Hardware tests reported as skipped/unverified, not passed
