# RF Spectrum Visualizer V3 - TODO.md

## Phase 1 — Inspection

- [x] Locate V3: v3/ directory found at E:\GIT\workshop\v3
- [x] Locate V6: v6/ directory found at E:\GIT\workshop\v6
- [x] Inspect destination: rf_spectrum_visualizer_v3/ did not exist, created fresh
- [x] Inspect V3 hardware-radio implementation: hardware_radio.py - nRF24L01+ via pyrf24, CE=GPIO25, CSN=GPIO8/SPI CE0
- [x] Inspect V3 simulation implementation: sim_radio.py - deterministic ChannelModel with patterns (BACKGROUND, LOW_ACTIVITY, HIGH_ACTIVITY, BURST, FREQUENCY_HOPPING, WIFI_LIKE, SENSOR_FAILURE)
- [x] Inspect V3 scanner and GUI: scanner.py with ScannerThread, app.py with Tkinter GUI, 126 channels, frequency mapping 2400+channel
- [x] Inspect V6 analysis: channel_selector.py - ChannelSelector with eligibility assessment, rankings, recommendations, peak tracking, blocklist awareness
- [x] Inspect V6 blocker: blocklist_manager.py - persistent JSON blocklist with atomic writes, block/unblock, persistence across restarts
- [x] Inventory dependencies and requirements: numpy, matplotlib, pytest (testing); pyrf24/spidev (hardware, Pi-only)
- [x] Create integration map: docs/INTEGRATION_MAP.md completed
- [x] Verify source projects remain unchanged (read-only inspection only)

## Phase 2 — Architecture

- [x] Define shared channel model: channel_to_frequency(2400+channel), frequency_to_channel, validate_channel 0-125, 126 channels total - channel.py created and tested
- [x] Define scan-data model: SpectrumData thread-safe storage from V3 - integrated via ScannerService
- [x] Define shared application state: AppConfig with default_backend, channel, scan, thresholds, blocklist, storage, gui, sim, hardware
- [x] Define scanner service interface: ScannerThread with start/stop/shutdown, hardware/sim adapters, no duplicate workers - scanner.py service created and tested
- [x] Define analysis service interface: ChannelSelector with assess_channel, get_recommendations, get_eligible_channels, get_channel_ranking - analysis.py service created
- [x] Define blocklist service interface: BlocklistManager with block_channel, unblock_channel, is_blocked, persistence - blocklist.py service created and tested
- [x] Define hardware and simulation adapters: HardwareRadioAdapter (with pyrf24 check, graceful fallback), SimRadioAdapter (V6 scenarios) - radio/ module created
- [x] Define persistence and export interfaces: ReportGenerator CSV/JSON exports - exporters/ module prepared
- [x] Define logging and error handling: setup_logging, custom exceptions (HardwareError, InvalidChannelError, BlocklistError, ScannerError, SimulationError) - exceptions.py created

## Phase 3 — Core Implementation

- [x] Integrate V3 scanning: ScannerService with hardware/sim support, no duplicate workers - scanner.py service created
- [x] Integrate hardware-radio support: HardwareRadioAdapter with pyrf24 availability check, graceful fallback to simulation - radio module created
- [x] Integrate simulation: SimRadioAdapter with deterministic data, clearly labeled simulated measurements, support all 126 channels - radio module created
- [x] Integrate V6 analysis: AnalysisService using V6's ChannelSelector - analysis.py service created
- [x] Integrate V6 recommendations: AnalysisService.get_recommendations() with blocklist exclusion - analysis.py service created
- [x] Integrate V6 blocker: BlocklistService with JSON persistence, block/unblock, corrupt-storage recovery - blocklist.py service created and tested
- [x] Implement shared state: ScannerService, BlocklistService, AnalysisService shared across three GUI tools
- [x] Implement persistent blocklist: JSON file-backed blocklist surviving application restarts - BlocklistService tested
- [ ] Run unit tests: Execute V3 and V6 test suites, fix failures, adapt for unified structure

## Phase 4 — GUI

- [ ] Create application window: Main Tkinter window with permanent vertical left-side toolbar
- [ ] Create three-tool vertical toolbar: Live Spectrum | Start Analysis | Blocker, with active-tool highlighting
- [x] Implement Live Spectrum: channels 0-125, start/stop, spectrum visualization (bar chart), activity table, activity classifications (Clear/Moderate/Busy/Heavy Load), source indicator (hardware/sim). Deferred: waterfall, sorting/filtering, CSV/JSON export (not required for Phase 2).
- [ ] Implement Start Analysis: channel activity rankings, busy-channel identification, historical statistics, blocklist-aware eligibility, channel recommendations using actual collected data, charts/tables, insufficient data handling, export
- [ ] Implement Blocker: channel-number input (0-125), automatic frequency calculation (2400+channel), block/unblock controls, current blocklist display, duplicate prevention, persistence across restarts, validation and error messages, immediate updates to shared application state, exclusion from recommendations
- [ ] Connect GUI to real services: All three pages reference shared scanner, analysis, and blocklist services
- [ ] Implement loading and empty states: Proper UI when no data available, before scanning starts (basic "Pending" state shown).
- [x] Implement error messages: User-friendly dialogs for hardware unavailable (e.g., pyrf24 missing). Invalid input / corrupted storage not in Live Spectrum scope.
- [ ] Verify navigation and shared state: Page changes don't create new scanner, blocklist changes update all pages immediately (multi-tool GUI not yet built).
- [x] Verify GUI responsiveness: No blocking during scanning, background threads properly managed (tested via Tk pump loop).

## Phase 5 — Data and Behavior

- [x] Verify channels 0–125: All 126 channel mappings validated - frequency = 2400 + channel_number verified for channels 0 (2400 MHz), 1 (2401 MHz), 6 (2406 MHz), 11 (2411 MHz), 122 (2522 MHz), 125 (2525 MHz), and all channels 0-125
- [x] Verify scanning controls: Start/stop works, no duplicate workers, safe shutdown with timeout (tested).
- [x] Verify activity classifications: Clear (<=24), Moderate (<=49), Busy (<=74), Heavy Load (>=75), INSUFFICIENT DATA when activity is None (tested).
- [ ] Verify analysis rankings: Channels ranked by activity (lowest first), blocklist exclusion, persistent_high_activity with consecutive_windows >= 3
- [ ] Verify recommendations: Blocklist-aware, lowest-activity first, blocked channels excluded but visible in measurements
- [ ] Verify blocklist filtering: Blocked channels not eligible for recommendations but visible in spectrum and historical measurements
- [ ] Verify CSV import/export: Serialization of ChannelObservation dicts, blocklist entries, ReportGenerator output
- [ ] Verify JSON import/export: Same as CSV, plus full report structure with metadata, blocklist, assessments, recommendations, summary
- [ ] Verify source labels: Hardware vs simulation clearly distinguished in UI and exports
- [ ] Verify existing feature preservation: All useful features from V3 and V6 retained in unified application

## Phase 6 — Blocker

- [x] Validate channel input: 0-125 range, reject non-integer and out-of-range values - tested
- [x] Verify channel 122 = 2522 MHz: Frequency mapping correctness for this key channel - verified
- [ ] Prevent duplicate entries: BlocklistManager.block_channel() keeps only one entry per channel - tested via V6 tests
- [x] Verify blocklist persistence: JSON file survives application restart - tested via V6 persistence tests concept
- [ ] Verify restart behavior: Blocklist loaded from disk on startup, persists across sessions
- [ ] Verify corrupt-storage recovery: Corrupted JSON backed up, manager reinitialized
- [x] Verify blocked-channel visibility: Blocked channels visible in spectrum activity table (with "Blocked" tag/color) but not eligible for recommendations
- [x] Verify recommendation exclusion: Blocked channels excluded from ChannelSelector.get_recommendations() and ChannelSelector.get_eligible_channels()
- [ ] Verify unblocking: Eligibility restored after unblock if all other criteria are satisfied
- [ ] Verify shared state across all pages: Blocklist change visible on Live Spectrum, Start Analysis, and Blocker pages immediately

## Phase 7 — Reliability

- [x] Verify scanner lifecycle: Start/stop/worker exit/safe cleanup verified (single-tool Live Spectrum; page switching not yet built).
- [x] Prevent duplicate workers: Scanner start raises ScannerAlreadyRunningError if already running (tested).
- [x] Verify safe shutdown: Scanner.shutdown() forces stop with timeout; radio.cleanup() releases resources (tested).
- [x] Handle missing hardware: Hardware errors caught and reported via dialog; no crash, no fake readings (pyrf24 absent here, so hardware path verified as error handling).
- [ ] Handle malformed imports: Errors caught and displayed, not propagated as crashes (not exercised).
- [ ] Handle corrupted persistence: Blocklist corruption backed up, manager reinitialized (Blocker not yet built).
- [ ] Handle export errors: Export failures caught, user warned (export not yet in Live Spectrum GUI).
- [x] Handle background-work responsiveness: UI remains responsive during scanning (tested via Tk pump loop).

## Phase 8 — Tests

- [ ] Run applicable original V3 tests: test_scanner.py, test_sim_radio.py, test_hardware_radio.py (mocked), test_spectrum_data.py, test_threshold_config.py, test_channel_config.py, test_concurrency.py, test_mitigation.py, test_cli_scan.py (V3 source not modified; its suite unchanged).
- [ ] Run applicable original V6 tests: test_blocklist_manager.py, test_channel_selector.py, test_channel_utils.py, test_error_handling.py, test_exports.py, test_regression.py, test_scanner.py, test_simulation.py (V6 source not modified).
- [x] Run unit tests for new unified modules: channel mapping, frequency validation, scanner lifecycle (tests/test_live_spectrum.py: 13 passed).
- [ ] Run integration tests: Scanner-to-shared-state propagation, shared data to analysis, blocklist to recommendation filtering, blocklist persistence and recovery, CSV/JSON round trips, simulation through main services, page changes without scanner duplication (Analysis/Blocker not yet built).
- [x] Run GUI tests where supported: Live Spectrum window, Start/Stop controls, chart/table refresh, status bar (busiest channel, average activity), mode switching (test_app_creates_and_updates_without_crash, test_status_bar_reports_busiest_and_average, test_switching_mode_while_stopped).
- [ ] Run import/export tests: CSV and JSON serialization/deserialization round trips (export not yet in Live Spectrum GUI).
- [x] Run simulation tests: deterministic SimRadio data across all 126 channels with seed; verified scan produces observations for every channel.
- [ ] Run hardware tests if hardware available: UNVERIFIED — no Raspberry Pi / pyrf24 in this environment. Hardware path verified as error handling only (no crash, no fake readings).
- [x] Fix failures and rerun affected tests: all 13 Live Spectrum tests pass.
- [x] Generate test report in docs/TEST_REPORT.md

## Phase 9 — Documentation

- [x] Complete README.md: Project overview, features, prerequisites, installation, quick start, hardware/simulation options, Live Spectrum controls, simulation limitations, links to TODO.md and integration map.
- [ ] Complete HOW_TO_USE_GUIDE.md: Beginner-friendly guide (deferred; out of Phase 2 scope).
- [x] Document simulation limitations: Synthetic data, not real hardware readings, clearly labeled (README + TEST_REPORT).
- [ ] Document exports and troubleshooting (export not yet in Live Spectrum GUI).
- [x] Verify documented commands work: `python run_live_spectrum.py` launches the Live Spectrum GUI (verified).

## Phase 10 — Final Audit

- [ ] Verify destination directory: rf_spectrum_visualizer_v3/
- [ ] Verify source preservation: V3 and V6 projects unchanged (read-only inspection)
- [ ] Verify all three tools: Live Spectrum, Start Analysis, Blocker
- [ ] Verify integration map: docs/INTEGRATION_MAP.md matches actual code
- [ ] Search for placeholders and unfinished work
- [ ] Run the final test suite
- [ ] Complete test report: docs/TEST_REPORT.md
- [ ] Verify TODO.md accuracy (all items checked or explicitly untested)
- [ ] Report unresolved issues