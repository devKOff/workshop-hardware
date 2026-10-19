# Solar Panel Performance Monitor — Raspberry Pi 3 A+ + INA219

A low-cost, locally-run solar monitoring system. A Raspberry Pi 3 Model A+
reads voltage, current, and power from an INA219 high-side current/power
monitor connected to a small solar panel under a test load, logs every sample
to a local SQLite database, and serves a responsive web dashboard (Flask)
reachable from a phone or computer on the same network.

Measured/displayed: panel voltage (V), current (mA/A), instantaneous power
(W), accumulated energy (Wh), daily energy (Wh/day), historical graphs,
timestamped records, CSV export, and sensor connection/error status.

## ⚠️ Important — read before wiring

This project was developed on a Windows workstation, **not** on a physical
Raspberry Pi, and the I²C-dependent code has **not** been tested against real
INA219 hardware. Treat the code as a correct, complete starting point that a
student must verify on actual hardware.

Before wiring, you **must**:

1. **Confirm the exact pin labels on your INA219 breakout.** Eight-pin INA219
   boards are not all laid out the same way. Identify VCC, GND, SDA, SCL, VIN+,
   VIN−, A0, A1 on *your* board (silkscreen or multimeter continuity check).
2. **Measure the solar panel's actual open-circuit voltage (Voc)** with a
   multimeter in bright sunlight. A "6 V" panel can often reach 7–9 V open
   circuit. Confirm it is within your INA219 breakout's rated bus-voltage range
   (commonly 0–26 V ADC input; absolute maximum depends on the variant).
3. **Confirm the shunt resistor value on the breakout** (commonly 0.1 Ω).
   The current range and calibration depend on it.
4. **Never connect the solar panel to any Raspberry Pi GPIO pin.** The Pi is
   powered separately through its micro-USB input. Only 3.3 V, GND, SDA, and
   SCL run between the Pi and the INA219.

## Block diagram (text)

```text
                       +------ solar panel (~6 V, 3 W) ------+
                       |                                     |
                  [VIN+]                                     [panel −]
                       |                                     |
              [INA219 breakout]                             [22 Ω, 5 W load]
                       |   shunt (0.1 Ω typical)             |
                  [VIN−]───────────/\/\/────────────────────+
                       |
            +----------+----------+--------------------------+
            |          |          |          |               |
          VCC        GND        SDA        SCL             GND (common)
            |          |          |          |               |
   Pi pin 1  Pi pin 6  Pi pin 3  Pi pin 5  Pi pin 6/9/14/20
  (3.3 V)   (GND)    (GPIO2 SDA)(GPIO3 SCL) (extra GND pins)

[Raspberry Pi 3 A+]
   └─ powered separately via 5 V micro-USB
   └─ I²C bus 1 talks to INA219
   └─ Python + Flask serve http://<pi-ip>:5000 to phone/computer
```

## Deliverables index

| # | Deliverable | Location |
|---|-------------|----------|
| 1 | Project overview & block diagram | README.md (this file) |
| 2 | Bill of materials | docs/02_bill_of_materials.md |
| 3 | Exact wiring table | docs/03_wiring_table.md |
| 4 | Circuit schematic (text) | docs/04_circuit_schematic.md |
| 5 | Pi setup commands | docs/05_pi_setup.md |
| 6 | Python sensor + logging code | src/ina219_reader.py, src/database.py, src/energy_tracker.py |
| 7 | SQLite database design | src/database.py (+ schema comments) |
| 8 | Flask dashboard code | src/app.py, templates/, static/ |
| 9 | Installation & execution | docs/05_pi_setup.md, scripts/install.sh, scripts/start.sh |
|10 | Example dashboard layout | docs/10_dashboard_layout.md |
|11 | Testing & troubleshooting | docs/07_testing_troubleshooting.md |
|12 | Future improvements | docs/08_future_improvements.md |
| — | Calculations & validation | docs/06_calculations.md |

## Quick start (run these on the Raspberry Pi)

```bash
# 1. Install system dependencies and enable I2C (see docs/05_pi_setup.md)
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y i2c-tools python3-venv python3-pip
# enable i2c_arm=on in /boot/config.txt or via sudo raspi-config

# 2. Detect the INA219 (expect address 0x40)
sudo i2cdetect -y 1

# 3. Clone/copy this project, then:
python -m venv .venv
source .venv/bin/activate
pip install -r src/requirements.txt

# 4. Run the dashboard
python src/app.py
# then open http://<raspberry-pi-ip-address>:5000 from another device
```

## File inventory

- `src/config.py` — I2C address, shunt ohms, sample interval, DB path
- `src/ina219_reader.py` — INA219 wrapper with error handling
- `src/database.py` — SQLite schema, inserts, queries, CSV export
- `src/energy_tracker.py` — Wh integration, daily reset, restart-safe cumulative
- `src/app.py` — Flask app + background sampling thread
- `templates/base.html`, `index.html`, `history.html` — web UI
- `static/style.css` — responsive styles
- `scripts/install.sh`, `scripts/start.sh` — convenience scripts
- `systemd/solar-monitor.service` — optional auto-start on boot
- `docs/` — wiring, schematic, setup, calculations, testing, future work

## Hardware assumptions (verify before proceeding)

| Item | Assumed value | What to check |
|------|---------------|---------------|
| INA219 shunt | 0.1 Ω | Read/silkscreen or measure the actual shunt on your board |
| INA219 address | 0x40 (A0=A1=GND) | Check jumpers/pins; address may differ |
| Panel Voc | ~6–9 V (must measure) | Multimeter in bright sun; must be < breakout bus max |
| Panel Isc | ~0.5 A (3 W / 6 V) | Must be within shunt/breakout rating |
| Load | 22 Ω, 5 W | ~1.6 W dissipation at 6 V — warm but within rating |
