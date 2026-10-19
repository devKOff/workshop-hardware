# Raspberry Pi setup — step by step

Run these commands on the Raspberry Pi (Raspberry Pi OS). Each command is
followed by a plain-language explanation.

## 1. Install and update Raspberry Pi OS

Flash Raspberry Pi OS (64-bit, desktop or lite) onto the microSD card with the
Raspberry Pi Imager on another computer. Boot the Pi, then open a terminal.

```bash
sudo apt update
sudo apt full-upgrade -y
```
- `apt update` refreshes the list of available packages.
- `apt full-upgrade -y` installs all available upgrades (`-y` answers yes
  automatically).

Reboot if the kernel was upgraded:
```bash
sudo reboot
```

## 2. Enable the I²C interface

The INA219 talks to the Pi over I²C, which is disabled by default.

Option A — using raspi-config (recommended, beginner-friendly):
```bash
sudo raspi-config
```
Navigate to **Interface Options → I2C → Yes** to enable, then **Finish** and
reboot when prompted.

Option B — editing config.txt directly:
```bash
echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
sudo reboot
```
(On newer Pi OS versions the file may be `/boot/firmware/config.txt`.)

After reboot, verify I²C is enabled:
```bash
ls /dev/i2c-1
```
You should see `/dev/i2c-1` (Pi 3 A+ uses I²C bus 1).

## 3. Check whether the INA219 is detected on the I²C bus

Install the I²C detection tool:
```bash
sudo apt install -y i2c-tools
```

Wire the INA219 per docs/03_wiring_table.md, then scan the bus:
```bash
sudo i2cdetect -y 1
```

Expected output: a grid with `40` at row 4, column 0 (address **0x40**) when
A0 and A1 are tied to GND.

- If you see `40`: the sensor is detected. Continue.
- If the grid is all `--`: no device responded. Check wiring, VCC/GND, and
  that I²C is enabled. See docs/07_testing_troubleshooting.md.
- If you see a different address (e.g. `41`, `42`), update `INA219_ADDRESS`
  in `src/config.py` to match.

## 4. Install Python dependencies in a virtual environment

A virtual environment keeps project packages separate from the system Python.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r src/requirements.txt
```
- `python -m venv .venv` creates the environment folder `.venv`.
- `source .venv/bin/activate` activates it (your prompt will show `(.venv)`).
- `pip install -r src/requirements.txt` installs Flask, the `ina219` library,
  and `smbus2` (the I²C backend).

`src/requirements.txt` contains:
```
flask>=3.0.0
ina219>=0.1.0
smbus2>=0.4.0
```

## 5. Install and configure the INA219-compatible Python library

The `ina219` package (from `requirements.txt`) is the INA219-compatible
library. It is configured in code via `src/config.py`:

```python
INA219_ADDRESS = 0x40
SHUNT_OHMS = 0.1        # <-- verify on your breakout
MAX_AMPS = 2.0          # calibration full-scale current
```

No separate system install is needed beyond `pip install`. The library is
initialized in `src/ina219_reader.py` (`sensor.configure()`), which sets the
INA219 gain and calibration based on `SHUNT_OHMS` and `MAX_AMPS`.

## 6. Test the sensor before developing the complete application

With the venv activated, run a quick manual read:

```bash
source .venv/bin/activate
python - <<'EOF'
from src.ina219_reader import SolarSensor
s = SolarSensor()
s.initialize()
r = s.read()
print(r)
EOF
```

Expected (in sunlight, with load connected):
```
Reading(timestamp='...', bus_voltage_v=5.xx, shunt_voltage_v=0.0xx,
        current_ma=xxx.x, power_mw=xxxx, ok=True, error=None)
```

If `ok` is False, check the error message and wiring (see docs/07).

Compare the reported voltage/current against a multimeter (docs/07, step 4).

## 7. Start the application automatically after boot (optional)

Two options:

### A. Manual start (simplest for demos)
```bash
source .venv/bin/activate
python src/app.py
```
Then open `http://<pi-ip-address>:5000` from another device on the LAN.

### B. Systemd service (auto-start on boot)
Copy `systemd/solar-monitor.service` to `/etc/systemd/system/`, adjust the
`WorkingDirectory` and `User` paths to match your Pi, then:

```bash
sudo cp systemd/solar-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now solar-monitor.service
sudo systemctl status solar-monitor.service
```

Logs: `journalctl -u solar-monitor.service -f`

## Convenience scripts

- `scripts/install.sh` — one-shot OS + I²C + Python setup (run once).
- `scripts/start.sh` — activate venv and launch the dashboard.

Make them executable: `chmod +x scripts/install.sh scripts/start.sh`.
