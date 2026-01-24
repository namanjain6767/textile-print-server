#!/bin/bash
#
# Thermal Print Server - Linux Installer
# Installs dependencies, USB rules, and sets up systemd service
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "=================================================="
echo "   Thermal Print Server - Linux Installer"
echo "=================================================="
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo ./install_linux.sh)${NC}"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
INSTALL_DIR="/opt/thermal-print-server"
SERVICE_NAME="thermal-print-server"

echo -e "${YELLOW}Installing for user: ${ACTUAL_USER}${NC}"
echo ""

# Detect package manager
if command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt"
    echo -e "${GREEN}✓ Detected Debian/Ubuntu system${NC}"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
    echo -e "${GREEN}✓ Detected Fedora/RHEL system${NC}"
elif command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
    echo -e "${GREEN}✓ Detected Arch Linux system${NC}"
elif command -v zypper &> /dev/null; then
    PKG_MANAGER="zypper"
    echo -e "${GREEN}✓ Detected openSUSE system${NC}"
else
    echo -e "${RED}✗ Unsupported package manager${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}[1/6] Installing system dependencies...${NC}"

case $PKG_MANAGER in
    apt)
        apt-get update -qq
        apt-get install -y python3 python3-pip python3-venv libusb-1.0-0 libusb-1.0-0-dev usbutils
        ;;
    dnf)
        dnf install -y python3 python3-pip libusb1 libusb1-devel usbutils
        ;;
    pacman)
        pacman -Sy --noconfirm python python-pip libusb usbutils
        ;;
    zypper)
        zypper install -y python3 python3-pip libusb-1_0-0 libusb-1_0-devel usbutils
        ;;
esac

echo -e "${GREEN}✓ System dependencies installed${NC}"

echo ""
echo -e "${BLUE}[2/6] Creating installation directory...${NC}"

mkdir -p "$INSTALL_DIR"
cp print_server.py "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/" 2>/dev/null || echo "pyusb>=1.2.1
pyserial>=3.5
zeroconf>=0.131.0" > "$INSTALL_DIR/requirements.txt"

chown -R "$ACTUAL_USER:$ACTUAL_USER" "$INSTALL_DIR"
echo -e "${GREEN}✓ Created $INSTALL_DIR${NC}"

echo ""
echo -e "${BLUE}[3/6] Setting up Python virtual environment...${NC}"

cd "$INSTALL_DIR"
sudo -u "$ACTUAL_USER" python3 -m venv venv
sudo -u "$ACTUAL_USER" ./venv/bin/pip install --upgrade pip
sudo -u "$ACTUAL_USER" ./venv/bin/pip install -r requirements.txt

echo -e "${GREEN}✓ Python environment ready${NC}"

echo ""
echo -e "${BLUE}[4/6] Installing USB printer rules...${NC}"

# Create udev rules for common thermal printers
cat > /etc/udev/rules.d/99-thermal-printer.rules << 'EOF'
# Thermal Printer USB Rules
# Allows non-root users to access USB thermal printers

# Generic Printer Class (Class 7)
SUBSYSTEM=="usb", ATTR{bDeviceClass}=="07", MODE="0666", GROUP="plugdev"

# HOP/Hoin Printers (common thermal printer brand)
SUBSYSTEM=="usb", ATTR{idVendor}=="0416", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="6868", MODE="0666", GROUP="plugdev"

# Epson Printers
SUBSYSTEM=="usb", ATTR{idVendor}=="04b8", MODE="0666", GROUP="plugdev"

# Star Micronics
SUBSYSTEM=="usb", ATTR{idVendor}=="0519", MODE="0666", GROUP="plugdev"

# SNBC Printers
SUBSYSTEM=="usb", ATTR{idVendor}=="154f", MODE="0666", GROUP="plugdev"

# Citizen Printers
SUBSYSTEM=="usb", ATTR{idVendor}=="1d90", MODE="0666", GROUP="plugdev"

# Bixolon Printers
SUBSYSTEM=="usb", ATTR{idVendor}=="1504", MODE="0666", GROUP="plugdev"

# Generic POS Printers
SUBSYSTEM=="usb", ATTR{idVendor}=="0483", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0525", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="1fc9", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0fe6", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="20d1", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0dd4", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="4b43", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="1a86", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTR{idVendor}=="0cf3", MODE="0666", GROUP="plugdev"

# USB-Serial adapters (for serial thermal printers)
SUBSYSTEM=="tty", ATTRS{idVendor}=="067b", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", MODE="0666", GROUP="dialout"
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", MODE="0666", GROUP="dialout"
EOF

# Add user to necessary groups
usermod -aG plugdev "$ACTUAL_USER" 2>/dev/null || true
usermod -aG dialout "$ACTUAL_USER" 2>/dev/null || true
usermod -aG lp "$ACTUAL_USER" 2>/dev/null || true

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

echo -e "${GREEN}✓ USB rules installed${NC}"

echo ""
echo -e "${BLUE}[5/6] Creating systemd service...${NC}"

cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Thermal Print Server
After=network.target

[Service]
Type=simple
User=${ACTUAL_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/print_server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Environment
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}

echo -e "${GREEN}✓ Systemd service created${NC}"

echo ""
echo -e "${BLUE}[6/6] Creating helper scripts...${NC}"

# Create start script
cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
cd /opt/thermal-print-server
./venv/bin/python print_server.py
EOF
chmod +x "$INSTALL_DIR/start.sh"

# Create status script
cat > "$INSTALL_DIR/status.sh" << 'EOF'
#!/bin/bash
echo "=== Thermal Print Server Status ==="
systemctl status thermal-print-server --no-pager
echo ""
echo "=== Recent Logs ==="
journalctl -u thermal-print-server -n 20 --no-pager
EOF
chmod +x "$INSTALL_DIR/status.sh"

# Create symlinks for easy access
ln -sf "$INSTALL_DIR/start.sh" /usr/local/bin/thermal-print-server
ln -sf "$INSTALL_DIR/status.sh" /usr/local/bin/thermal-print-status

chown -R "$ACTUAL_USER:$ACTUAL_USER" "$INSTALL_DIR"

echo -e "${GREEN}✓ Helper scripts created${NC}"

echo ""
echo -e "${GREEN}"
echo "=================================================="
echo "   Installation Complete!"
echo "=================================================="
echo -e "${NC}"
echo ""
echo "The print server has been installed to: $INSTALL_DIR"
echo ""
echo -e "${YELLOW}Commands:${NC}"
echo "  Start service:    sudo systemctl start thermal-print-server"
echo "  Stop service:     sudo systemctl stop thermal-print-server"
echo "  View status:      thermal-print-status"
echo "  Run manually:     thermal-print-server"
echo "  View logs:        journalctl -u thermal-print-server -f"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "  1. Plug in your thermal printer via USB"
echo "  2. You may need to log out and back in for USB permissions"
echo "  3. Start the service: sudo systemctl start thermal-print-server"
echo ""
echo -e "${BLUE}The server will be available at:${NC}"
echo "  http://$(hostname -I | awk '{print $1}'):9100"
echo ""
