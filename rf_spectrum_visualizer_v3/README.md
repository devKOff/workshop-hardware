# RF Spectrum Visualizer V3 — Live Spectrum (Phase 2)

Unified RF spectrum visualizer for the 2.4 GHz ISM band. This is the
destination project into which the V3 and V6 source projects are integrated
(read-only inspection; **V3 and V6 source projects are never modified**).

## Phase 2 — Live Spectrum (complete)

The **Live Spectrum** tool connects a Tkinter + matplotlib GUI to the actual
V3 nRF24L01+ scanner implementation (`v3/scanner.py`: `ScannerThread`,
`SpectrumData`, `ChannelObservation`; `v3/sim_radio.py` `SimRadio`;
`v3/hardware_radio.py` `HardwareRadio`).

### Features

- **Scan all 126 channels (0–125)** with frequency = `2400 + channel_number`
  MHz (e.g., Ch 0 = 2400 MHz, Ch 125 = 2525 MHz).
- **Live spectrum bar chart** — activity % per channel, colour-coded by status,
  with Clear/Moderate/Busy threshold reference lines.
- **Channel activity table** — channel, frequency (MHz), activity %, status,
  samples, RPD-positive count, data-sufficient flag.
- **Activity percentage (0–100%)** and status labels:
  **Clear** (≤24%), **Moderate** (≤49%), **Busy** (≤74%), **Heavy Load** (≥75%),
  plus `INSUFFICIENT DATA` and `SENSOR_ERROR`.
- **Start Scan / Stop Scan** controls.
- **Hardware and Simulation modes**, clearly distinguished:
  - Hardware — real nRF24L01+ RPD measurements via pyrf24.
  - Simulation — deterministic channel model; data is **simulated, not
    calibrated hardware readings**, and is labeled as such in the UI.
- **Scanner status bar**: running/stopped, backend, scan cycles, busiest
  channel, average activity, last-scanned channel (progress).
- **Responsive GUI**: background scanning thread, thread-safe `SpectrumData`,
  UI refresh driven by `tk.after` (main thread only).
- **No duplicate scanner threads** (`ScannerAlreadyRunningError`).
- **Clean shutdown** on Stop and on window close.
- **Hardware errors handled without crashing and without fake readings**:
  if pyrf24/hardware is unavailable, scanning is not started and a dialog is
  shown.

### Source data

All observations carry a `backend` field (`"sim"` or `"hardware"`) and a
`frequency_mhz` field (`2400 + channel`). The shared `SpectrumData` instance
holds all scan data and is ready for the future Analysis page.

## Prerequisites

- Python 3.10+ (tested with 3.12.10)
- tkinter (usually bundled with Python on Windows)
- matplotlib, numpy

Optional (hardware mode only, Raspberry Pi):
- `pyrf24`, `spidev` (Pi-only; not installed in this environment)

## Installation

No installation is required beyond the Python dependencies. From the project
root:

```
# from rf_spectrum_visualizer_v3/
python -m pip install matplotlib numpy   # tkinter is typically included
```

## Quick start

Launch the Live Spectrum GUI:

```
python run_live_spectrum.py
```

The GUI starts in **Simulation mode** (deterministic model) because `pyrf24`
is not available on a typical Windows dev machine. Select **Hardware** mode
only on a Raspberry Pi with `pyrf24`/`spidev` and an nRF24L01+ wired
(CE=GPIO25, CSN=SPI CE0).

1. Choose a mode (Simulation / Hardware).
2. Optionally adjust the channel range (0–125), measurement window, and
   sampling interval.
3. Press **Start Scan**.
4. Watch the spectrum chart and channel table update live.
5. Press **Stop Scan** when done.

## Simulation limitations

Simulation data is synthetic and deterministic. It is **not** a calibrated
power measurement and is **not** a substitute for real hardware readings. The
nRF24L01+ provides narrowband channel-activity (RPD) observations only — no
calibrated dBm. Simulated data is clearly labeled "Simulation (deterministic
model — simulated data, not calibrated hardware readings)".

## Hardware limitations (unverified)

No Raspberry Pi or `pyrf24` is available in this environment, so hardware
mode is **untested on real hardware**. Hardware-mode error handling (missing
`pyrf24`/SPI) is verified: the scanner reports an error, does not start, and
displays no fake readings.

## Project structure

```
rf_spectrum_visualizer_v3/
├── run_live_spectrum.py          # entry point: launches Live Spectrum GUI
├── README.md                     # this file
├── TODO.md                       # task tracking (updated with results)
├── docs/
│   ├── INTEGRATION_MAP.md        # V3/V6 -> destination integration decisions
│   └── TEST_REPORT.md            # test results
├── src/rf_spectrum_visualizer/
│   ├── exceptions.py             # shared exception hierarchy
│   ├── models/channel.py         # channel <-> frequency mapping (0-125)
│   ├── radio/                    # hardware + simulation radio adapters
│   ├── services/                 # scanner / analysis / blocklist services
│   ├── storage/
│   ├── exporters/
│   └── ui/
│       ├── __init__.py
│       └── live_spectrum.py      # Live Spectrum GUI (Phase 2)
└── tests/
    ├── __init__.py
    └── test_live_spectrum.py     # Phase 2 tests (13 tests, all passing)
```

## Related

- `docs/INTEGRATION_MAP.md` — mapping of V3/V6 components to this project.
- `TODO.md` — remaining work (Analysis and Blocker backends are deliberately
  not implemented yet).
- Source projects `v3/` and `v6/` are **unchanged** (read-only inspection).
