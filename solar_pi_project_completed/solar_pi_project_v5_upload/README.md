# Solar Panel Performance Monitor (v5)

A small desktop app that reads voltage, current and power from an INA219
sensor on a Raspberry Pi 3 Model A+ (or from a built-in simulator), shows the
live readings, keeps the data of one 10-minute session in memory, and lets the
user export that data to a CSV file at the end.

## What it does (and nothing more)

- One window with Hardware / Simulation radio buttons.
- Live readings: Voltage (V), Current (mA), Power (W).
- One session at a time, up to `duration` seconds (default 600 = 10 minutes),
  sampling every `interval` seconds (default 1.0), about 600 samples.
- Data lives only in memory for the current session. Nothing is written to
  disk except the CSV you choose to export.
- Export to CSV via a native Save dialog.
- No database, no graphs, no multiple pages, no menus, no settings screen,
  no reports, no internet, no cloud.

## Measurement

Voltage: for high-side wiring, the INA219 bus voltage is measured after the
shunt, so panel voltage ≈ bus voltage + shunt voltage (VIN+ to GND). The app
reports that sum and documents it here.

Current is reported in mA. Power (W) = Voltage (V) × Current (A), calculated
for every valid sample.

A sample is valid only if the readings are finite numbers, the INA219 overflow
flag is not set, and the values are within the sensor's configured range.
Otherwise it is stored with a status such as `read_error`, `overflow` or
`out_of_range`, and the live readings show "—". Bad readings are never
replaced with 0.

Simulator: smooth, realistic panel values (about 5–6 V, tens of mA) with small
noise, never impossible values, every record labeled `simulation`. Hardware is
never labeled as simulation and simulation is never shown as real.

## CSV export

Columns, fixed order:

| Column | Meaning | Units |
|--------|---------|-------|
| timestamp | Wall-clock time, timezone-aware ISO 8601 | — |
| elapsed_s | Seconds since session start | s |
| voltage_v | Panel voltage | V |
| current_ma | Current | mA |
| power_w | Power = V × I | W |
| status | `ok`, `read_error`, `overflow`, `out_of_range` | — |
| data_source | `hardware` or `simulation` | — |

- Native Save dialog (`tkinter.filedialog.asksaveasfilename`, asks before
  overwriting).
- Default name: `solar_readings_YYYY-MM-DD_HH-MM-SS.csv`.
- Stdlib `csv`, UTF-8 with BOM, `.` decimal separator.
- Written to a temp file and then renamed, so a failed export never leaves a
  half-written file.
- After saving, shows the row count and path. On cancel, does nothing. On
  permission or path errors, shows the real error.

## Windows (Simulation mode)

1. `python -m venv .venv`
2. `.\.venv\Scripts\Activate.ps1`
3. `pip install -r requirements-dev.txt`
4. `python -c "import tkinter; print('tkinter ok')"`
5. `python -m pytest -q`
6. `python main.py` — choose Simulation in the mode radio buttons.

For fast testing: `python main.py --duration 20 --interval 0.5`

## Raspberry Pi 3 Model A+

1. `sudo apt install -y python3-tk i2c-tools`
2. Enable I²C: `sudo raspi-config` → Interface Options → I2C → Yes → reboot.
3. `i2cdetect -y 1` — the INA219 normally shows at `0x40`.
4. `python3 -m venv .venv`
5. `source .venv/bin/activate`
6. `pip install -r requirements.txt`
7. `python3 main.py`

## Wiring reference

Verify against YOUR INA219 board's documentation before powering anything.

- VCC → Pi 3.3 V (pin 1)
- GND → GND (pin 6)
- SDA → GPIO2 (pin 3)
- SCL → GPIO3 (pin 5)

High side: panel + → VIN+, VIN− → load +, load − → panel −.
**VIN− is not GND.** Never put 5 V on GPIO/I²C pins. Check the open-circuit
voltage and expected load current before connecting.

## Troubleshooting

- **Sensor not found:** "INA219 not found. Check wiring and I²C, or choose
  Simulation." Confirm I²C is enabled, run `i2cdetect -y 1`, check the
  address is `0x40`, and check wiring. Never fall back to simulated data on
  hardware failure.
- **No display over SSH:** Tkinter needs an X display. Run locally on the Pi
  with a monitor, or forward X11 (`ssh -X`).
- **Missing tkinter:** install `python3-tk` (`sudo apt install -y python3-tk`).

## Known limitations

- Hardware mode not verified on a real Pi (verified by simulator and unit
  tests only).
- One 10-minute session in memory; data is lost when the window closes unless
  exported to CSV.
- The real 10-minute Pi run is marked "not verified" until performed on
  actual hardware.
