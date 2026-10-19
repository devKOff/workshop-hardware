# RF Spectrum Visualizer V3 - Integration Map

Generated during Phase Two: Source Inventory and Integration Planning.

This document maps each important component from the V3 and V6 source projects to the unified application's destination modules. Decisions are based on actual code inspection, not assumptions.

## Integration Map Table

| Feature | V3 Source | V6 Source | Destination | Decision | Verification |
|---|---|---|---|---|---|
| Radio hardware | v3/hardware_radio.py | v6/hardware_radio.py | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/radio/ | Reuse/adapt | Both implement nRF24L01+ via pyrf24 with same pinout (CE=GPIO25, CSN=GPIO8/SPI CE0). V6 has more detailed SPI diagnostic and HardwareConfig. Decision: reuse V3's simpler interface, adapt V6's HardwareConfig and SPI checks. |
| Simulation | v3/sim_radio.py | v6/sim_radio.py | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/radio/ | Reuse/adapt | Both implement SimRadio with deterministic data, ChannelModel, scenario support. V6 has richer scenario types (QUIET, SINGLE_BUSY, CHANNEL_122_HIGH/LOW, WIFI_LIKE, FREQUENCY_HOPPING, SENSOR_ERRORS, MIXED, BURST, HIGH_ACTIVITY) and create_scenario classmethod. Decision: merge V6's richer scenario system with V3's simpler SimRadio, use V6's SimRadio as the unified simulation adapter. |
| Scanner | v3/scanner.py | v6/scanner.py | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/services/ | Reuse/adapt | Both implement SpectrumData (thread-safe observations), ScannerThread (background worker with start/stop/shutdown). V6 has validate_channel import and slightly different exception hierarchy. Decision: reuse V3's scanner.py structure, integrate V6's validate_channel and exception types. |
| Analysis | v3/mitigation.py (MitigationEngine) | v6/channel_selector.py (ChannelSelector) | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/analysis/ | Integrate | V3's MitigationEngine focuses on persistent activity detection with alerts and recommendations. V6's ChannelSelector focuses on channel eligibility, rankings, and blocklist-aware recommendations. Decision: adopt V6's ChannelSelector as the primary analysis service (cleaner eligibility model, blocklist integration, get_recommendations, get_channel_ranking), adapt V3's mitigation concepts where compatible (persistent_threshold, hysteresis). |
| Blocker | v3/mitigation.py (partial) | v6/blocklist_manager.py | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/blocker/ | Integrate | V6's BlocklistManager is a complete persistent JSON blocklist with atomic writes, block/unblock, is_blocked, get_blocked_channels, persistence across restarts, corrupt-storage recovery. V3's mitigation.py has some alert logic but not a full blocklist. Decision: adopt V6's BlocklistManager as the unified blocklist service. |
| GUI | v3/app.py (SpectrumVisualizerApp) | v6/app.py (SpectrumVisualizerApp) | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/ui/ | Unify | Both are Tkinter-based with similar structure (menubar, toolbar, main paned window, channel table, spectrum graph, waterfall, alerts). V6 has blocklist controls, recommendations panel, status filtering, eligibility column, block status column, scenario simulation dialog. Decision: create new unified GUI with vertical left toolbar (3 tools), incorporating V6's blocklist controls and recommendations, V3's spectrum visualization. |
| Persistence | v3/config.py (StorageConfig, logging) | v6/blocklist_manager.py, v6/logging_config.py | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/storage/ | Unify | V3 has StorageConfig (rolling_history_size, waterfall_history_size, log_path, export_dir). V6 has BlocklistManager (JSON persistence), JSONLinesFormatter, setup_logging with RotatingFileHandler. Decision: combine V6's BlocklistManager for blocklist persistence + V3's logging setup, use V6's JSON-backed blocklist as the shared persistence mechanism. |
| Channel model | v3/config.py (ChannelConfig, ThresholdConfig, ScanConfig) | v6/config.py (ChannelConfig, ThresholdConfig, ScanConfig, BlocklistConfig, SimConfig, HardwareConfig) | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/models/ | Unify | Both have ChannelConfig (0-125), ThresholdConfig (clear/moderate/busy/heavy), ScanConfig. V6 adds BlocklistConfig, SimConfig, HardwareConfig. V6's channel_utils.py has channel_to_frequency, frequency_to_channel, ChannelInfo, validate_channel, parse_channel_input. Decision: adopt V6's channel_utils.py as the shared channel model (validates 0-125, maps 2400+channel, parses "2522 MHz" input), keep V3's config dataclasses. |
| Exports | v3/app.py (_export_csv, _export_json, _export_png) | v6/report_generator.py, v6/app.py (_export_csv, _export_json, _export_all_formats) | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/exporters/ | Integrate | V3 has basic CSV/JSON/PNG exports from within app. V6 has ReportGenerator with export_json, export_csv, export_blocklist_json, export_blocklist_csv, export_waterfall_csv, export_all_formats. Decision: adopt V6's ReportGenerator as the unified export service. |
| Exceptions | v3/exceptions.py | v6/exceptions.py | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/ | Unify | Both have HardwareError, InvalidChannelError, ScannerError. V6 adds BlocklistError, RadioInitError, SPIError, SimulationError, BackendError, InsufficientDataError. Decision: adopt V6's full exception hierarchy. |
| Logging | v3/logging_config.py | v6/logging_config.py | rf_spectrum_visualizer_v3/src/rf_spectrum_visualizer/ | Unify | Both have setup_logging, get_logger. V6 has JSONLinesFormatter for JSONL output, log_countermeasure_event. Decision: adopt V6's logging setup with JSONL format for countermeasure events. |

## Component Details

### V3: hardware_radio.py
- Responsibilities: nRF24L01+ radio interface via pyrf24, channel scanning with RPD, initialization, cleanup, info diagnostics.
- Public interface: HardwareRadio.__init__, is_available, initialize, is_initialized, set_channel, get_channel, read_rpd, scan_channel, cleanup, get_info, locked context manager.
- Dependencies: pyrf24, config.ChannelConfig, config.ScanConfig, exceptions.HardwareError, exceptions.RadioInitializationError, exceptions.SPIError, exceptions.RadioNotFoundError, exceptions.InvalidChannelError.
- Tests: v3/tests/test_hardware_radio.py (mocked pyrf24 tests).
- Decision: Reuse as hardware adapter, integrate V6's HardwareConfig and _check_spi_device, graceful fallback to simulation when pyrf24 unavailable.

### V3: sim_radio.py
- Responsibilities: Simulated nRF24L01+ radio for testing/development, deterministic ChannelModel with activity patterns.
- Public interface: SimRadio.__init__, initialize, is_initialized, set_channel, get_channel, read_rpd, scan_channel, cleanup, get_channel_model, set_seed.
- Dependencies: config.ChannelConfig, config.ScanConfig, exceptions.SimulationError, random, threading.
- Tests: v3/tests/test_sim_radio.py (ChannelModel probs, SimRadio initialization, scan_channel, seed reproducibility, get_channel_model, WiFi channels).
- Decision: Replace with V6's SimRadio (richer scenarios, create_scenario classmethod, deterministic seed control).

### V3: scanner.py
- Responsibilities: SpectrumData (thread-safe storage), ScannerThread (background scanning loop).
- Public interface: ScannerThread.__init__, start, stop, shutdown, is_running, backend property, backend setter.
- Dependencies: config.AppConfig, sim_radio.SimRadio, hardware_radio.HardwareRadio, exceptions.ScannerError, ScannerNotRunningError, ScannerAlreadyRunningError, InsufficientDataError.
- Tests: v3/tests/test_scanner.py, v3/tests/test_concurrency.py, v3/tests/test_gui.py.
- Decision: Reuse ScannerThread structure, integrate V6's validate_channel calls, merge exception types.

### V6: channel_selector.py
- Responsibilities: Channel selection and recommendation engine, eligibility assessment, rankings, blocklist awareness, peak tracking, hysteresis.
- Public interface: ChannelSelector.__init__, assess_channel, assess_all_channels, get_eligible_channels, recommend_channel, get_recommendations, get_channel_ranking, get_blocked_channels, get_peak_activity, reset_peaks, export_assessment.
- Dependencies: config.ChannelConfig, config.ThresholdConfig, blocklist_manager.BlocklistManager, exceptions.InvalidChannelError.
- Tests: v6/tests/test_channel_selector.py, v6/tests/test_error_handling.py (TestChannelSelectorEdgeCases), v6/tests/test_regression.py (TestRegressionChannelSelection).
- Decision: Adopt as the unified analysis service. Clean eligibility model (ELIGIBLE/BLOCKED/INSUFFICIENT_DATA/SENSOR_ERROR/HIGH_ACTIVITY/PERSISTENT_HIGH_ACTIVITY), blocklist integration, recommendations with exclusion, channel rankings.

### V6: blocklist_manager.py
- Responsibilities: Persistent JSON blocklist management, atomic writes, block/unblock/is_blocked, get_blocked_channels, get_blocked_entries, clear, reload, export_json, import_json, stats, corrupt-storage recovery.
- Public interface: BlocklistManager.__init__, block_channel, unblock_channel, is_blocked, get_blocked_channels, get_blocked_entries, get_entry, clear, get_stats, _get_file_mtime, reload, export_json, import_json.
- Dependencies: config.BlocklistConfig, exceptions.BlocklistError, exceptions.InvalidChannelError, channel_utils.validate_channel.
- Tests: v6/tests/test_blocklist_manager.py (block, duplicate, unblock, is_blocked, get_channels, entries, clear, persistence, corrupted file recovery, invalid entries, export/import JSON, stats, concurrent access, atomic write, large blocklist, corrupted backup).
- Decision: Adopt as the unified blocklist service. JSON persistence, atomic writes, corrupt-storage backup, block/unblock, immediate shared state updates, exclusion from recommendations, visible in measurements.

### V6: channel_utils.py
- Responsibilities: Channel number <-> frequency conversion, validation, formatting, WiFi overlap info, parse channel input.
- Public interface: channel_to_frequency, frequency_to_channel, validate_channel, validate_channel_list, get_all_channels, get_channels_in_range, format_channel, parse_channel_input, get_wifi_overlap_channels, ChannelInfo.
- Dependencies: config.ChannelConfig.
- Tests: v6/tests/test_channel_utils.py (channel_to_frequency boundaries, frequency_to_channel boundaries, validate_channel, validate_channel_list, get_all_channels 126, test_full_range, test_partial_range, format_channel with/without freq, parse_channel_input plain/CH/MHZ, test_invalid, test_wifi_overlaps, ChannelInfo valid/invalid).
- Decision: Adopt as the shared channel model. Validates 0-125, frequency = 2400 + channel, maps 2522 MHz -> 122, parses "Ch 122", "2522 MHz", supports all 126 channels.

### V6: report_generator.py
- Responsibilities: Generate and export comprehensive scan reports, CSV/JSON/blocklist/waterfall exports, full report structure with metadata, assessments, recommendations, summary.
- Public interface: ReportGenerator.__init__, generate_full_report, _generate_summary, export_json, export_json_file, export_csv, export_csv_file, export_blocklist_json, export_blocklist_csv, export_waterfall_csv, export_all_formats.
- Dependencies: config.AppConfig, scanner.SpectrumData, blocklist_manager.BlocklistManager, channel_selector.ChannelSelector, channel_utils.get_all_channels.
- Tests: v6/tests/test_exports.py (generate_full_report, export_json, export_json_file, export_csv, export_csv_file, export_blocklist_json, export_blocklist_csv, export_waterfall_csv, export_all_formats, summary_stats, roundtrip_json, csv_has_all_fields).
- Decision: Adopt as the unified export service. All export formats, report structure with metadata/blocklist/assessments/recommendations/summary.

### V6: exceptions.py
- Responsibilities: Custom exception hierarchy for RF system errors.
- Public interface: RFSystemError (base), BlocklistError, RadioInitError, InvalidChannelError, ConfigurationError, ScannerError, InsufficientDataError, BackendError, SimulationError, HardwareError, SPIError, RadioNotFoundError.
- Tests: v6/tests/test_error_handling.py (TestExceptions, TestConfigValidation, TestChannelUtilsEdgeCases, TestBlocklistEdgeCases, TestSimRadioEdgeCases, TestScannerEdgeCases, TestChannelSelectorEdgeCases).
- Decision: Adopt V6's full exception hierarchy as the unified exception system.

### V6: logging_config.py
- Responsibilities: Application logging setup, JSON Lines format for countermeasure events.
- Public interface: setup_logging, get_logger, JSONLinesFormatter, log_countermeasure_event.
- Tests: Part of v6 test suites.
- Decision: Adopt V6's logging setup with JSONL format for countermeasure events, integrate with V3's basic logging.

### V3: app.py (GUI)
- Responsibilities: Tkinter GUI with spectrum visualization, channel table, waterfall, alerts, scanning controls.
- Features: Vertical toolbar with Start/Stop, backend selector, channel range, measurement window, interval, ARMED checkbox, export buttons. Left pane: channel table + live spectrum graph. Right pane: waterfall + alerts. Menu: File (export, exit), View (clear history), Help (about).
- Decision: Design new unified GUI with vertical left-side toolbar (3 tools: Live Spectrum, Start Analysis, Blocker), incorporating V6's blocklist controls and recommendations panel, V3's spectrum visualization.

### V6: app.py (GUI)
- Responsibilities: Tkinter GUI with blocklist controls, channel activity table (with blocked/eligible columns), live spectrum graph, waterfall, recommendations panel, alerts, status filtering, sorting, scenario simulation dialog.
- Features: Blocklist control panel (channel input, Block/Unblock/Check/Clear buttons). Channel table with 9 columns including "Eligible" and "Blocked". Recommendations display text area. Status filtering (All/Clear/Moderate/Busy/Heavy Load/INSUFFICIENT DATA/SENSOR_ERROR/BLOCKED). Scenario simulation dialog with 10 predefined scenarios.
- Decision: Incorporate V6's blocklist controls, recommendations, status filtering, eligibility/blocked columns into unified GUI.

## Source Project Preservation

Both original V3 and V6 projects remain unchanged. This integration map documents the decisions made during inspection, and all source code in v3/ and v6/ directories has not been modified. The unified application builds upon the inspected implementations without altering the source projects.

## Notes

- Frequency mapping is consistent: `frequency_mhz = 2400 + channel_number` across all sources. Verified for channels 0-125.
- Channel range is 0-125, giving 126 channels, consistent across V3 and V6.
- Blocklist exclusions: Blocked channels are excluded from recommendations but remain visible in spectrum and historical measurements.
- Source labels: Hardware vs simulation data clearly distinguished in UI and exports.
- The integration map will be updated as implementation progresses and decisions are verified.