# How to Use — RF Spectrum Visualizer v3.1

Beginner-friendly guide for installing, launching, and using the RF Spectrum
Visualizer desktop application.

## Prerequisites

- Windows 10/11 or Linux with Python 3.10+
- tkinter (bundled with Python on most distributions)
- matplotlib >= 3.8.0
- pytest >= 7.0.0 (for running tests)

Optional — Hardware mode (Raspberry Pi only):
- pyrf24
- spidev

See [Hardware Setup](HARDWARE_SETUP.md) for Raspberry Pi wiring and installation.

## Installation

1. Open a terminal in the project folder:

   ```bash
   cd rf_spectrum_visualizer_v3.1
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   Note: `customtkinter` is not required — the app uses standard tkinter.

## Launching the Application

From the project root (`rf_spectrum_visualizer_v3.1/`):

```bash
python main.py
```

The application adds `src/` to `sys.path` automatically, so the package is
importable as `rf_spectrum_visualizer`.

## Using the Application

The window has a dark navy sidebar on the left with three navigation items
and a light workspace on the right. Click a sidebar item to open its page.

### 1. Live Spectrum

Scan the 2.4 GHz ISM band (channels 0–125) and view real-time activity.

**Controls:**
- **Mode**: "sim" (simulated data) or "hardware" (nRF24L01+ via pyrf24).
  Hardware mode requires a Raspberry Pi with pyrf24 installed.
- **Start Scan**: begins scanning all channels in the selected range
  in a background thread. The GUI remains responsive during scanning.
- **Stop Scan**: halts the scanner and cleans up radio resources.
- **Channels**: Spinboxes for start/end channel (0–125).
- **Window (s)**: Measurement window per channel (0.05–10.0 s).
- **Interval (ms)**: RPD sampling interval (1–1000 ms).

**Displays:**
- **Data Source banner**: clearly indicates "Hardware (nRF24L01+)" or
  "Simulation (deterministic model)" so you know whether readings are real
  or simulated.
- **Channel Activity table**: Ch, Freq (MHz), Activity %, Status, Samples,
  RPD+, Data OK for all 126 channels.
- **Live Spectrum chart**: bar chart of activity % by channel, color-coded
  by status (green=Clear, orange=Moderate, red=Busy, dark red=Heavy Load).
- **Status bar**: scanner status, scan cycles, busiest channel, average
  activity, last scanned channel.

**Important:** No calibrated dBm measurements are claimed. The nRF24L01+
provides limited channel-activity observations (RPD), not calibrated power
readings.

### 2. Start Analysis

Analyze measurements collected by a Live Spectrum scan.

**Controls:**
- **Start Analysis**: analyzes the latest measurements from the shared
  scan data. Does NOT start a scanner or access hardware.

**Displays:**
- **Summary cards**: Channels Analyzed, Busiest Channel, Average Activity,
  Recommended Clear Channels.
- **Channel Activity Comparison chart**: bar chart of activity % by channel.
- **Results table**: Channel, Freq (MHz), Activity (%), Status,
  Recommendation (Recommended / Use with caution / Avoid / Blocked — excluded).

**Status labels:**
- Clear: activity ≤ 24%
- Moderate: activity ≤ 49%
- Busy: activity ≤ 74%
- Heavy Load: activity ≥ 75%
- INSUFFICIENT DATA: missing or incomplete readings

**Important:** Run a Live Spectrum scan first. If no scan data exists,
clicking Start Analysis shows an informational message.

### 3. Blocker (Software-Level Channel Exclusion)

Exclude channels from Analysis recommendations. This is software-level
exclusion only — it does NOT physically block RF signals or prevent
transmissions.

**Controls:**
- **Channel**: Spinbox (0–125). Frequency updates automatically
  (2400 + channel_number MHz).
- **Add Exclusion**: adds the channel to the exclusion list.
- **Remove Selected**: removes selected channels (confirmation required).
- **Clear All**: removes all exclusions (confirmation required).
- **Excluded Channels list**: displays Channel and Frequency (MHz).

**Behavior:**
- Excluded channels are omitted from Analysis recommendations but remain
  fully visible in Live Spectrum measurements.
- The exclusion list is saved to `blocker_exclusions.json` and restored
  when the application restarts.
- Duplicate entries are prevented.
- Invalid channel numbers (outside 0–125) show an error message.

## Data Source Transparency

The application clearly distinguishes real measurements from simulated data:

- **Simulation mode**: deterministic channel model. All data is labeled
  "Simulation (deterministic model)". Not calibrated hardware readings.
- **Hardware mode**: real nRF24L01+ RPD readings. Requires pyrf24 and a
  Raspberry Pi. Not available on this development machine.

## Exiting the Application

Close the window using the close button (X). The scanner (if running) is
stopped and radio resources are cleaned up automatically.

## Running Tests

```bash
pytest tests/
```

Hardware tests are skipped on machines without pyrf24 or a Raspberry Pi.

## Limitations

- No calibrated dBm measurements.
- Hardware mode unavailable without Raspberry Pi + pyrf24.
- Blocked/excluded channels affect Analysis recommendations only; they do
  not affect Live Spectrum measurements.
- Persistent storage is a local JSON file (`blocker_exclusions.json`), not
  a database.
- No CSV/JSON export yet (planned for a future phase).
