#!/bin/bash
#
# Thermal Print Server - Quick Run Script
# Use this for testing without installing as a service
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}"
echo "=================================================="
echo "   Thermal Print Server - Quick Start"
echo "=================================================="
echo -e "${NC}"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install pyusb pyserial zeroconf
    echo ""
fi

# Check for USB permissions
if [ ! -f "/etc/udev/rules.d/99-thermal-printer.rules" ]; then
    echo -e "${YELLOW}Warning: USB rules not installed.${NC}"
    echo "For USB printer access, run: sudo ./install_linux.sh"
    echo "Or run this script with sudo for direct USB access."
    echo ""
fi

echo "Starting server..."
echo ""
./venv/bin/python print_server.py
