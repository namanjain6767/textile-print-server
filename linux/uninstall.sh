#!/bin/bash
#
# Thermal Print Server - Linux Uninstaller
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}"
echo "=================================================="
echo "   Thermal Print Server - Uninstaller"
echo "=================================================="
echo -e "${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo ./uninstall.sh)${NC}"
    exit 1
fi

echo "This will remove:"
echo "  - /opt/thermal-print-server"
echo "  - Systemd service"
echo "  - USB udev rules"
echo "  - usblp blacklist"
echo "  - Helper scripts"
echo ""
read -p "Are you sure? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Stopping service..."
systemctl stop thermal-print-server 2>/dev/null || true
systemctl disable thermal-print-server 2>/dev/null || true

echo "Removing files..."
rm -f /etc/systemd/system/thermal-print-server.service
rm -f /etc/udev/rules.d/99-thermal-printer.rules
rm -f /etc/modprobe.d/thermal-printer-blacklist.conf
rm -f /usr/local/bin/thermal-print-server
rm -f /usr/local/bin/thermal-print-status
rm -rf /opt/thermal-print-server

systemctl daemon-reload
udevadm control --reload-rules

echo ""
echo -e "${GREEN}✓ Uninstallation complete${NC}"
echo ""
echo -e "${YELLOW}Note: The usblp kernel module was blacklisted during install.${NC}"
echo -e "${YELLOW}If you want to restore normal USB printer functionality:${NC}"
echo -e "  sudo modprobe usblp"
echo -e "  sudo update-initramfs -u"
