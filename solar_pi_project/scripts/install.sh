#!/usr/bin/env bash
# install.sh — one-shot setup for the Solar Panel Performance Monitor on
# Raspberry Pi OS. Run as the pi user (or any user with sudo).
#
# What it does:
#   1. Updates the OS
#   2. Installs i2c-tools, python3-venv, python3-pip
#   3. Enables the I²C interface (adds dtparam=i2c_arm=on to /boot/config.txt)
#   4. Creates a Python virtual environment in .venv
#   5. Installs Python dependencies from src/requirements.txt
#   6. Verifies the INA219 responds on I²C bus 1 (expects 0x40)
#
# Reboot is required after enabling I²C before i2cdetect will work.

set -euo pipefail

echo "[1/6] Updating Raspberry Pi OS..."
sudo apt update
sudo apt full-upgrade -y

echo "[2/6] Installing system packages..."
sudo apt install -y i2c-tools python3-venv python3-pip

echo "[3/6] Enabling I²C interface..."
if ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/firmware/config.txt /boot/config.txt 2>/dev/null || true
    echo "I²C enabled. A reboot is required before i2cdetect will find the sensor."
else
    echo "I²C already enabled in config.txt."
fi

echo "[4/6] Creating virtual environment and installing Python packages..."
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r src/requirements.txt

echo "[5/6] Detecting INA219 on I²C bus 1 (expect address 0x40)..."
if command -v i2cdetect >/dev/null 2>&1; then
    sudo i2cdetect -y 1 || echo "i2cdetect ran but reported an error (reboot may be needed)."
else
    echo "i2cdetect not available yet; run 'sudo i2cdetect -y 1' after reboot."
fi

echo "[6/6] Done."
echo ""
echo "Next steps:"
echo "  - Reboot the Pi if you just enabled I²C for the first time."
echo "  - Wire the INA219 and solar panel per docs/03_wiring_table.md."
echo "  - Start the dashboard: ./scripts/start.sh  (or: source .venv/bin/activate && python src/app.py)"
echo "  - Open http://<raspberry-pi-ip-address>:5000 from another device."
