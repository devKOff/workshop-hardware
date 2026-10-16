#!/bin/bash
# RF Spectrum Visualizer v3.1 - Raspberry Pi 3B+ Installation Script
# Installs system and Python dependencies for simulation and hardware modes.
#
# Usage:
#   ./install_raspberry_pi.sh          # Simulation mode dependencies only
#   ./install_raspberry_pi.sh hardware # Include hardware mode (pyrf24) dependencies
#
# Requirements: Raspberry Pi 3B+, Raspberry Pi OS, Python 3

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

MODE="${1:-sim}"

echo "=============================================="
echo "RF Spectrum Visualizer v3.1 - Raspberry Pi Setup"
echo "=============================================="
echo ""

# Check for python3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed."
    echo "Install with: sudo apt update && sudo apt install python3 python3-pip python3-tk"
    exit 1
fi

echo "[1/5] Checking Python..."
python3 --version

# Verify project files
echo ""
echo "[2/5] Verifying project files..."
if [ ! -f "src/rf_spectrum_visualizer/__init__.py" ]; then
    echo "ERROR: src/rf_spectrum_visualizer package not found."
    echo "Run this script from the rf_spectrum_visualizer_v3.1 directory."
    exit 1
fi
echo "Project files verified."

# Install system dependencies
echo ""
echo "[3/5] Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip python3-tk python3-matplotlib

# Install Python dependencies from requirements.txt
echo ""
echo "[4/5] Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Hardware mode additional dependencies
if [ "$MODE" = "hardware" ]; then
    echo ""
    echo "[5/5] Installing hardware mode dependencies (pyrf24, spidev)..."
    sudo apt install -y python3-spidev
    python3 -m pip install pyrf24 || true
    echo ""
    echo "NOTE: Hardware mode also requires SPI to be enabled:"
    echo "  sudo raspi-config  -> Interface Options -> SPI -> Enable"
    echo "  Then reboot."
else
    echo ""
    echo "[5/5] Simulation mode setup complete."
fi

echo ""
echo "=============================================="
echo "Setup complete!" -ForegroundColor Cyan 2>/dev/null || echo "Setup complete!"
echo "=============================================="
echo ""
echo "To launch in simulation mode:"
echo "  ./run_raspberry_pi.sh"
echo "  or: python3 run_sim.py"
echo ""
if [ "$MODE" = "hardware" ]; then
    echo "To launch in hardware mode (nRF24L01+):"
    echo "  ./run_raspberry_pi.sh hardware"
fi
echo ""
echo "To run tests:"
echo "  python3 -m pytest tests/"
echo ""
echo "Hardware mode requires SPI enabled and pyrf24 installed."
echo "See docs/HARDWARE_SETUP.md for wiring and details."
echo ""
