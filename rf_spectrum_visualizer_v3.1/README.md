# RF Spectrum Visualizer v3.1

Modern Python desktop GUI for RF spectrum analysis with a professional dark navy
sidebar, light workspace, and crimson accents.

## Status

**Phase 5 — Complete integration, testing, and finalization complete.** All
four phases are complete. Live Spectrum, Start Analysis, and Blocker work
together as one stable desktop application. Scan data flows from Live Spectrum
to Analysis without duplicate scanner instances. Blocker exclusions persist
across restarts and are applied to Analysis recommendations. Excluded channels
remain visible in Live Spectrum measurements.

## Look & feel

- Dark navy sidebar
- Light workspace
- Crimson accents

Exactly three sidebar items:

1. **Live Spectrum** — live spectrum chart, channel activity table, Start/Stop Scan
2. **Start Analysis** — summary cards, activity chart, results table with
   recommendations (analyzes real scan data on demand)
3. **Blocker** — channel input (0-125), Add/Remove/Clear, persistent exclusion list

## Requirements

- Python 3.10+
- tkinter (bundled with Python)
- matplotlib>=3.8.0
- pytest (for tests)

Optional (hardware mode only, Raspberry Pi):
- pyrf24, spidev

Install:

```bash
pip install -r requirements.txt
```

## Launch

From the project root (`rf_spectrum_visualizer_v3.1/`):

```bash
python main.py
```

The package is importable as `rf_spectrum_visualizer` when run from the
project root (main.py adds `src/` to `sys.path`).

## Live Spectrum controls

- **Mode**: "sim" (simulated data) or "hardware" (nRF24L01+ via pyrf24).
  Hardware mode is unavailable on this machine (pyrf24 not installed) and
  falls back gracefully with an error dialog if selected.
- **Start Scan**: begins scanning all channels in the selected range
  (default 0–125) in a background thread. Frequency = 2400 + channel MHz.
- **Stop Scan**: halts the scanner and cleans up radio resources.
- **Channel range**: Spinboxes for start/end channel (0–125).
- **Window (s)**: Measurement window per channel.
- **Interval (ms)**: RPD sampling interval.

## Start Analysis controls

- **Start Analysis**: analyzes the latest measurements from the shared
  SpectrumData (produced by Live Spectrum scan). Does NOT start a scanner.
- **Summary cards**: Channels Analyzed, Busiest Channel, Average Activity,
  Recommended Clear Channels.
- **Activity chart**: bar chart of activity % by channel, color-coded by
  status, with threshold reference lines.
- **Results table**: Channel, Freq (MHz), Activity (%), Status,
  Recommendation. Blocked channels (from Blocker page) are excluded from
  recommendations but remain visible.
- **Status indicators**: Ready / Analyzing / Complete / No data; staleness
  warning when scan data is older than 60 seconds.
- Frequency formula: `2400 + channel_number` MHz.
- Status labels: Clear (≤24%), Moderate (≤49%), Busy (≤74%), Heavy Load (≥75%),
  INSUFFICIENT DATA for missing/incomplete readings.

## Blocker controls (software-level channel exclusion)

- **Add Exclusion**: enter a channel (0-125) and add it to the exclusion list.
  Frequency is calculated as `2400 + channel_number` MHz.
- **Remove Selected**: remove one or more selected channels (with confirmation).
- **Clear All**: remove all excluded channels (with confirmation).
- **Exclusion list**: displays Channel and Frequency (MHz) for each excluded
  channel. List is saved to `blocker_exclusions.json` and restored on restart.
- Excluded channels are omitted from Analysis recommendations but remain
  fully visible in Live Spectrum measurements.
- This is software-level channel exclusion only — it does NOT physically block
  RF signals or prevent transmissions.

## Displayed data

- Live spectrum bar chart (activity % by channel, color-coded by status)
- Channel activity table: Ch, Freq (MHz), Activity %, Status, Samples, RPD+, Data OK
- Status labels: Clear / Moderate / Busy / Heavy Load (plus INSUFFICIENT DATA / SENSOR_ERROR)
- Status bar: scanner status, scan cycles, busiest channel, average activity, last scanned channel
- Data source banner clearly distinguishes real hardware measurements from simulated data
- No fake measurements are displayed; empty states show "No scan data"

## Tests

```bash
pytest tests/
```

## Test results (last run)

```
> pytest tests/
======================== 72 passed, 2 skipped in 3.06s =========================
```

| Test file | Result |
|---|---|
| `tests/test_channel_validation.py` | 8 passed (channel range 0–125, `2400 + channel` frequency, round-trip, invalid inputs) |
| `tests/test_blocker_add_remove.py` | 7 passed (add, duplicate rejected, multi-channel sorted, remove, clear all, frequency label) |
| `tests/test_blocker_persistence.py` | 13 passed (save/load roundtrip, missing file, corruption recovery, invalid data) |
| `tests/test_blocker_analysis_integration.py` | 5 passed (excluded channels omitted from recommendations, remain visible in measurements) |
| `tests/test_cross_module_integration.py` | 15 passed (Live Spectrum→Analysis, blocker persistence, exclusion visibility, end-to-end frequency/activity/classification) |
| `tests/test_gui_navigation.py` | 3 passed (window launches with exactly 3 pages, page switching, clean shutdown) |
| `tests/test_scanner_integration.py` | 10 passed, 1 skipped (hardware unverified — no Raspberry Pi/pyrf24 available) |
| `tests/test_analysis.py` | 11 passed (activity calculations, frequency mapping, empty/invalid/stale data, blocker exclusion, no duplicate scanner) |

Scanner integration test coverage:

- SpectrumData creation and backend labeling
- Sim backend start/stop with observation production
- All 126 channels (0–125) in scan range
- Frequency = 2400 + channel_number
- Activity classifications: Clear (≤24), Moderate (≤49), Busy (≤74), Heavy Load (≥75), INSUFFICIENT DATA
- Duplicate scanner start raises ScannerAlreadyRunningError
- ChannelObservation fields (channel, frequency_mhz, backend, activity_percentage, status, etc.)
- Scan cycle count increments
- Hardware availability reported as skipped (not available on this machine)

Blocker persistence test coverage:

- Save/load roundtrip
- Empty list
- Missing file returns empty
- Duplicate channels deduplicated
- Out-of-range channels dropped
- Non-integer channels dropped
- Storage file created
- Clear storage removes file
- Corrupted JSON returns empty
- Empty/whitespace file returns empty
- JSON array instead of object returns empty
- Missing channels key returns empty
- Channels key not a list returns empty

Cross-module integration test coverage:

- Live Spectrum scan data flows to Analysis without duplicate scanner workers
- Blocker exclusions persist and affect Analysis recommendations
- Excluded channels remain visible in Live Spectrum measurements
- End-to-end channel numbering, frequency mapping, activity classifications

Blocker → Analysis integration test coverage:

- Excluded channels omitted from recommendations
- Excluded channels remain visible in results entries
- Blocked channels not counted as recommended
- Persisted blocker exclusions affect Analysis
- Exclusion does not remove measurement data from SpectrumData

Analysis test coverage:

- Empty data → empty result, no crash
- All insufficient data → channels_analyzed=0, average=0
- Frequency mapping verified (0→2400, 122→2522, 125→2525)
- Activity calculations: busiest channel, average activity
- Threshold classification: Clear/Moderate/Busy/Heavy Load boundaries
- Blocked channels excluded from recommendations
- Stale data detection (data older than 60s)
- Analysis does not start a duplicate scanner worker
- SENSOR_ERROR / invalid readings handled safely
- Each run_analysis() call returns an independent snapshot

GUI smoke test: `python main.py` launches the window, all three pages render,
and the app exits cleanly on close.

## File structure

```
rf_spectrum_visualizer_v3.1/
├── main.py                  # Application entry point (Tkinter)
├── README.md
├── TODO.md
├── requirements.txt
├── .gitignore
├── docs/
│   └── TEST_REPORT.md       # Detailed test report
├── src/
│   └── rf_spectrum_visualizer/
│       ├── __init__.py
│       ├── config.py        # AppConfig + ChannelConfig/ScanConfig/ThresholdConfig
│       ├── constants.py     # Channel limits, page ids, colors, fonts
│       ├── v3_bridge.py     # Read-only import of V3 scanner modules (workshop/v3)
│       ├── gui/
│       │   ├── __init__.py
│       │   ├── main_window.py   # Shell: sidebar + stacked pages + scanner lifecycle
│       │   ├── sidebar.py       # Three nav items with icons (Tkinter)
│       │   ├── theme.py         # Colors, fonts, styles (Tkinter)
│       │   ├── canvas.py        # Reusable matplotlib TkAgg canvas
│       │   ├── live_spectrum_page.py   # Live scanner integration
│       │   ├── start_analysis_page.py  # Analysis of shared scan data
│       │   └── blocker_page.py   # Channel exclusion with persistence
│       └── utils/
│           ├── __init__.py
│           ├── channel.py     # validate_channel / channel_to_frequency
│           └── persistence.py # Blocker exclusion JSON persistence
├── tests/                   # pytest suite (72 passed, 2 skipped)
└── assets/                  # Placeholder assets
```

## Roadmap

- CSV/JSON export
- Packaging (pyproject.toml, entry points)

## Source preservation

The original V3 (`workshop/v3`) and V6 (`workshop/v6`) projects are **never
modified**. V3 scanner code is imported read-only via `v3_bridge.py`.
