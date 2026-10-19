# Installation — Raspberry Pi (hardware mode)

Run these commands on the Raspberry Pi 3 Model A+ with Raspberry Pi OS.

## 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPO_URL>
cd solar-panel-monitor
```

## 2. Run the Pi setup script

This installs system packages, enables I²C, creates a virtual environment, and
installs Python dependencies.

```bash
bash scripts/setup_pi.sh
```

**Reboot** to enable I²C:

```bash
sudo reboot
```

## 3. Wire the INA219 (POWER OFF FIRST)

Wire per `docs/HARDWARE_WIRING.md`. Then verify:

```bash
sudo i2cdetect -y 1
```

The INA219 should appear at its address (default 0x40). If it shows at a
different address, update `INA219_I2C_ADDRESS` in `.env` or `config.json`.

## 4. Check the hardware

```bash
. .venv/bin/activate
python scripts/check_hardware.py
```

You should see bus voltage, current, and power readings.

## 5. Configure

```bash
cp .env.example .env
cp config.example.json config.json
```

Edit `.env`:
- `SENSOR_MODE=hardware` (required to read the real INA219)
- `INA219_I2C_ADDRESS=0x40` (match what `i2cdetect` reported)
- `INA219_SHUNT_OHMS` and `INA219_MAX_EXPECTED_AMPS` for your breakout
- `HOST=0.0.0.0` to allow access from other devices on the LAN
- `PORT=5000`

## 6. Start the dashboard

```bash
./scripts/start.sh
```

Open **http://<PI-IP-ADDRESS>:5000/** from a phone or laptop on the same Wi-Fi.

## 7. Optional — run as a systemd service (automatic startup)

Create `/etc/systemd/system/solar-monitor.service`:

```ini
[Unit]
Description=Solar Panel Performance Monitor
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/solar-panel-monitor
Environment=SENSOR_MODE=hardware
ExecStart=/home/pi/solar-panel-monitor/.venv/bin/python /home/pi/solar-panel-monitor/run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable solar-monitor.service
sudo systemctl start solar-monitor.service
sudo systemctl status solar-monitor.service
```

Logs: `journalctl -u solar-monitor.service -f`

## Accessing from another device

With `HOST=0.0.0.0`, the dashboard is reachable at
`http://<PI-IP>:5000/` from any device on the same Wi-Fi. Find the Pi's IP with
`hostname -I`. **Do not expose port 5000 to the public internet**; keep it on
your local network only (or use a VPN).
