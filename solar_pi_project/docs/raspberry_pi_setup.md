# Solar Panel Performance Monitor - Raspberry Pi Software Setup

This section provides beginner-friendly, step-by-step instructions for preparing the
Raspberry Pi 3 Model A+ for the solar monitoring project. All commands work on Raspberry
Pi OS (64-bit or 32-bit recommended).

## 1. Installing and Updating Raspberry Pi OS

### A. Fresh Installation (Recommended)

1. Download the latest Raspberry Pi Imager from https://www.raspberrypi.com/software/.
2. Select "Raspberry Pi OS (other)" → "Raspberry Pi OS Lite" (headless) or
   "Raspberry Pi OS (desktop)" (with GUI).
3. Choose the microSD card destination.
4. Click "Edit Settings" and set:
   - Username: `pi` (default) or your preferred name
   - Password: your chosen password
   - SSH: Enable (use password or key-based authentication)
   - Wi-Fi: Enter your network SSID and password (optional if using Ethernet)
   - Set hostname (optional, e.g., `solarpi`)
5. Click "Save" and then "Write".
6. After writing, remove the microSD card and insert it into the Raspberry Pi.

### B. Post-First-Boot Steps

1. Log in with your credentials.
2. Open a terminal.

### C. Update the system

Run the following commands to ensure you have the latest packages and firmware:

```bash
# Update all installed packages to their latest versions
sudo apt update

# Upgrade all packages
sudo apt upgrade -y

# Perform a full upgrade (may install new dependencies)
sudo apt full-upgrade -y

# Remove unnecessary packages
sudo apt autoremove -y

# Clean the package cache
sudo apt clean
```

> **Why these commands?**
> - `apt update` refreshes the list of available packages and versions.
> - `apt upgrade` installs newer versions of currently installed packages.
> - `apt full-upgrade` handles changed dependencies (add/remove packages as needed).
> - `apt autoremove` removes packages that were automatically installed and are no longer
>   needed.
> - `apt clean` clears the local repository of retrieved package files.

## 2. Enabling the I²C Interface

The INA219 communicates over the I²C bus. The Pi's I²C interface must be enabled.

### Option A: Using raspi-config (recommended)

```bash
sudo raspi-config
```

1. Navigate to **Interface Options** → **I²C**.
2. Select **Yes** to enable I²C.
3. Select **Yes** to automatically load the I²C kernel module.
4. Finish and reboot if prompted:

```bash
sudo reboot
```

### Option B: Using Python (one-time setup)

```bash
# Enable I²C device tree overlay
echo "i2c-bcm2708" | sudo tee -a /etc/modules

# Add the I2C kernel parameter (for Pi 3 and later)
# This is usually already handled by raspi-config; if not:
echo "dtparam=i2c=on" | sudo tee -a /boot/firmware/config.txt

# Reboot to apply changes
sudo reboot
```

> **Note:** The Raspberry Pi 3 Model A+ has I²C on the 40-pin header, but the Model A+
> only has the 40-pin header (same as Model B). The SDA and SCL pins are:
> - GPIO 2 (physical pin 3) = SDA
> - GPIO 3 (physical pin 5) = SCL

### Verify I²C is Enabled

```bash
# Check that the I2C interface is listed
ls -la /dev/i2c-*
```

You should see something like `/dev/i2c-1`. If the device file does not exist, re-check
the above steps or reboot the Pi.

## 3. Checking Whether the INA219 is Detected on the I²C Bus

With the hardware wired correctly, you can scan the I²C bus to find the INA219 address.

```bash
# Scan the I²C bus (bus 1 is the standard on Pi 3)
i2cdetect -y 1
```

Expected output: a grid showing addresses. The INA219 default address is **0x40**,
but it may be 0x41, 0x44, or 0x45 depending on the A0/A1 pin connections.

If you see `40` (or your set address) in the output, the INA219 is detected and
communication is working.

### If the INA219 is Not Detected

1. Double-check the wiring: VCC to Pi 3.3 V, GND to Pi GND, SDA to Pi GPIO 2, SCL
   to Pi GPIO 3.
2. Verify that the INA219 A0/A1 pins are floated (default) or connected as needed.
3. Ensure the Pi has rebooted after enabling I²C (some changes require a reboot).
4. Check that the micro-USB power supply provides stable 5 V (undervoltage can
   disable I²C).
5. Try a different I²C bus address by connecting A0 or A1 to 3.3 V or GND, then
   re-run `i2cdetect -y 1`.

## 4. Installing Python Dependencies in a Virtual Environment

It is good practice to create a dedicated Python virtual environment for this project.

```bash
# Create a directory for the project
mkdir -p ~/solar_monitor
cd ~/solar_monitor

# Create a virtual environment (python3 -m venv is built into Python 3.3+)
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# The prompt should now prefix with (.venv)
```

### Install Required Python Packages

While the virtual environment is active, install the INA219 library and other dependencies:

```bash
# Core library for INA219
pip install ina219

# Flask for web dashboard
pip install Flask

# Chart.js via Flask-Assets or inline; we'll use basic HTML/JS
# (No additional Python charting package needed for our simple dashboard)

# Optional: SQLite is included with Python, no install needed
# Optional: matplotlib for local graphing
pip install matplotlib
```

> **Why a virtual environment?** It isolates the project's dependencies from the system
> Python install, preventing version conflicts with other projects or system tools.

### Verify the Installation

```bash
# Test that the INA219 library imports correctly
python3 -c "from ina219 import INA219; print('INA219 library loaded successfully')"

# Test Flask imports
python3 -c "from flask import Flask; print('Flask loaded successfully')"
```

## 5. Installing and Configuring an INA219-Compatible Python Library

The `ina219` package PyPI is the most common library for the INA219 breakout.

### Installing the Library

With the virtual environment active:

```bash
pip install ina219
```

### Basic Usage Example (Test Script)

Create a test file to verify the sensor works:

```python
# test_ina219.py
from ina219 import INA219
from ina219 import constants

# Create INA219 object (default I²C address 0x40, bus 1)
sensor = INA219()

# Set the gain to improve measurement range
# gain = 1/8 (shunt voltage range ±40 mV) or 1/1 (±400 mV) or 1/2 (±200 mV) or 1/4 (±100 mV)
sensor.gain = constants.GAIN_1_4  # ±100 mV shunt range, good for small currents

# Set the bus voltage range (default is usually fine)
# bus_adc resolution
sensor.bus_adc_resolution = constants.ADC_RESOLUTION_12BIT_128S

# Read bus voltage (V)
bus_voltage = sensor.voltage()
print(f"Bus Voltage: {bus_voltage} V")

# Read shunt voltage (mV)
shunt_voltage = sensor.shunt_voltage()
print(f"Shunt Voltage: {shunt_voltage} mV")

# Read current (mA)
current = sensor.current()
print(f"Current: {current} mA")

# Read power (W)
power = sensor.power()
print(f"Power: {power} W")
```

Run the test:

```bash
python3 test_ina219.py
```

### Library Configuration Notes

The `ina219` library requires two key parameters:

1. **Gain**: Determines the shunt voltage full-scale range.
   - GAIN_1_4 = ±100 mV (recommended for small currents, ~500 mA max with 0.1 Ω shunt)
   - GAIN_1_2 = ±200 mV
   - GAIN_1 = ±400 mV
   - GAIN_2 = ±80 mV

   > **For a 3 W / 6 V solar panel expecting ~500 mA max:**
   > With the INA219's default 0.1 Ω shunt resistor, the shunt voltage at 500 mA is:
   > V = I × R = 0.5 A × 0.1 Ω = 0.05 V = 50 mV.
   > GAIN_1_4 (±100 mV) is sufficient and gives better resolution.

2. **ADC Resolution**: Affects measurement speed and noise.
   - ADC_RESOLUTION_12BIT_128S = 128 samples, ~12-bit resolution, slower but smoother
   - ADC_RESOLUTION_12BIT_64S = 64 samples, faster
   - ADC_RESOLUTION_11BIT_32S = 32 samples, even faster
   - ADC_RESOLUTION_10BIT_16S = 16 samples, fastest, lowest resolution

   > **Recommendation:** Use the default (12-bit, 128 samples) for stationary monitoring.
   > Faster resolutions are useful for rapidly changing measurements.

## 6. Testing the Sensor Before Developing the Complete Application

Before writing the full application, verify the sensor works end-to-end:

```bash
# Ensure the virtual environment is active
source ~/solar_monitor/.venv/bin/activate

# Run the test script
python3 test_ina219.py
```

Expected output (values will vary with lighting and load):

```
Bus Voltage: 6.25 V
Shunt Voltage: 12.5 mV
Current: 125.0 mA
Power: 0.0781 W
```

### Troubleshooting No Reading or Zero Values

1. **Zero current with panel illuminated**: The panel may be open-circuited (no load
   connected). Connect the 22 Ω test load and verify again.
2. **Zero bus voltage**: Check the INA219 VCC connection to Pi 3.3 V, not 5 V.
3. **I²C errors**: Re-check wiring, ensure I²C is enabled, and verify the Pi's I²C
   device file exists.
4. **Negative current**: This is normal if the current direction reverses (e.g., panel
   voltage exceeds shunt voltage drop, or if the panel is supplying power to a battery).
   The INA219 supports bidirectional current measurement.

## 7. Starting the Application Automatically After Boot

For a permanently installed monitoring system, you may want the dashboard to start
automatically after boot.

### Option A: Systemd Service (recommended)

1. Create a systemd service file:

```bash
cat > /etc/systemd/system/solar_monitor.service << 'EOF'
[Unit]
Description=Solar Panel Performance Monitor Dashboard
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/solar_monitor
ExecStart=/home/pi/solar_monitor/.venv/bin/python src/dashboard.py
Restart=on-failure
RestartSec=5
Environment=PATH=/home/pi/solar_monitor/.venv/bin
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
```

2. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable solar_monitor
sudo systemctl start solar_monitor
```

3. Check the status:

```bash
sudo systemctl status solar_monitor
```

### Option B: Cron @reboot

```bash
# Edit crontab
crontab -e

# Add line (replace paths as needed):
@reboot cd /home/pi/solar_monitor && source .venv/bin/activate && python3 src/dashboard.py >> /var/log/solar_monitor.log 2>&1
```

> **Note:** The systemd service approach is preferred because it restarts the app if it
> crashes and manages the environment more reliably than cron.

### Accessing the Dashboard Remotely

After the server starts, note the Pi's IP address:

```bash
hostname -I
# or
ifconfig wlan0  # for Wi-Fi
# or
ip addr show wlan0
```

Access the dashboard from any device on the same local network by entering the Pi's
IP address in a web browser:

```
http://<PI_IP_ADDRESS>:5000
```

> **Important:** By default, Flask binds to `127.0.0.1` (localhost only). The dashboard
> code in this project will bind to `0.0.0.0` (all interfaces) so it is accessible from
> other devices on the network. Ensure your network's firewall or router does not block
> port 5000.