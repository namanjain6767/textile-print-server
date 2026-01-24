# Linux Installation

This folder contains scripts to install and run the Thermal Print Server on Linux.

## Quick Install (Recommended)

```bash
cd print-server/linux
sudo ./install.sh
```

This will:
- Install Python and USB dependencies
- Set up a virtual environment
- Blacklist the `usblp` kernel module (allows direct USB access)
- Install udev rules for USB printer permissions
- Create a systemd service for auto-start
- Create helper commands

## Quick Run (No Install)

For testing without installing as a service:

```bash
cd print-server/linux
./run.sh
```

Note: You may need to run with `sudo` for USB access if udev rules aren't installed.

## Commands After Install

```bash
# Start the service
sudo systemctl start thermal-print-server

# Stop the service
sudo systemctl stop thermal-print-server

# Check status
thermal-print-status

# View live logs
journalctl -u thermal-print-server -f

# Run manually (for debugging)
thermal-print-server
```

## Uninstall

```bash
cd print-server/linux
sudo ./uninstall.sh
```

## Troubleshooting

### USB Access Denied

The installer blacklists the `usblp` kernel module automatically. If you still have issues:

```bash
# Check if usblp is loaded
lsmod | grep usblp

# If loaded, unload it
sudo rmmod usblp

# Verify it's blacklisted
cat /etc/modprobe.d/thermal-printer-blacklist.conf
```

### Printer Not Found

1. Check USB connection: `lsusb`
2. Verify permissions: `ls -la /dev/bus/usb/*/*`
3. Make sure you're in the right groups: `groups`
4. Try logging out and back in after install

### Service Won't Start

```bash
# Check service status
sudo systemctl status thermal-print-server

# View logs
journalctl -u thermal-print-server -e

# Try running manually to see errors
/opt/thermal-print-server/venv/bin/python /opt/thermal-print-server/print_server.py
```
