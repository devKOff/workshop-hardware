#!/usr/bin/env bash
#
# setup_pi.sh — Raspberry Pi OS setup for the Solar Panel Performance Monitor.
#
# Run once on the Raspberry Pi:
#   curl -fsSL ... | bash   (or copy this file and run: bash scripts/setup_pi.sh)
#
set -euo pipefail

echo "==> Solar Panel Performance Monitor — Raspberry Pi setup"
echo

# --- 1. System packages -----------------------------------------------------
echo "==> Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip i2c-tools git

# --- 2. Enable the I2C interface -------------------------------------------
echo "==> Enabling I2C (dtparam=i2c_arm=on)..."
CONFIG_FILE=""
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    CONFIG_FILE="/boot/config.txt"
else
    echo "    WARNING: neither /boot/config.txt nor /boot/firmware/config.txt found."
    CONFIG_FILE=""
fi

if [ -n "$CONFIG_FILE" ] && ! grep -qE "^dtparam=i2c_arm=on" "$CONFIG_FILE"; then
    echo "dtparam=i2c_arm=on" | sudo tee -a "$CONFIG_FILE" >/dev/null
    echo "    I2C enabled in $CONFIG_FILE — a reboot is required."
else
    echo "    I2C already enabled."
fi

# --- 3. Add current user to the i2c group ----------------------------------
echo "==> Adding user '$USER' to the i2c group..."
sudo usermod -aG i2c "$USER" || true

# --- 4. Python virtual environment + dependencies --------------------------
echo "==> Creating Python virtual environment (.venv)..."
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "==> Setup complete."
echo
echo "Next steps:"
echo "  1. Reboot the Pi to enable I2C:   sudo reboot"
echo "  2. Wire the INA219 per docs/HARDWARE_WIRING.md (POWER OFF FIRST)."
echo "  3. Verify the sensor:             sudo i2cdetect -y 1"
echo "  4. Check the hardware:            python scripts/check_hardware.py"
echo "  5. Start the dashboard:           ./scripts/start.sh"
