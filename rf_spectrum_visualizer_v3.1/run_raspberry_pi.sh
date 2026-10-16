#!/bin/bash
# RF Spectrum Visualizer v3.1 - Raspberry Pi 3B+ Launch Script
# Supports both simulation mode (default) and hardware mode (nRF24L01+ via pyrf24).
#
# Usage:
#   ./run_raspberry_pi.sh          # Simulation mode
#   ./run_raspberry_pi.sh hardware # Hardware mode (requires pyrf24 + SPI enabled)

cd "$(dirname "$0")"

# Check for Python3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed."
    echo "Install with: sudo apt update && sudo apt install python3 python3-pip python3-tk python3-matplotlib"
    exit 1
fi

# Check that src/ directory exists
if [ ! -f "src/rf_spectrum_visualizer/__init__.py" ]; then
    echo "ERROR: src/rf_spectrum_visualizer package not found."
    echo "Please run this script from the rf_spectrum_visualizer_v3.1 directory."
    exit 1
fi

MODE="${1:-sim}"

if [ "$MODE" = "hardware" ]; then
    echo "Starting RF Spectrum Visualizer v3.1 (Hardware Mode - nRF24L01+)..."
    echo "Ensure SPI is enabled and pyrf24 is installed."
    echo ""
else
    echo "Starting RF Spectrum Visualizer v3.1 (Simulation Mode)..."
fi

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Checking dependencies..."
    python3 -m pip install -r requirements.txt 2>/dev/null || true
fi

# Launch the application
python3 main.py

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "The application exited with error code $EXIT_CODE."
fi
exit $EXIT_CODE
