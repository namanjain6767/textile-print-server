# Thermal Printer Network Server

A cross-platform Python print server that allows any device on your network to print to a USB thermal printer.

## Features

- Works on Windows and Linux
- Supports USB, Serial, and Windows Printer drivers
- Exposes HTTP API for network printing
- mDNS support - access via `printserver.local`
- Works with any browser/device on the same network
- No USB drivers needed on mobile devices
- Auto-start on boot (Linux systemd service)

## Quick Start

### Windows (Recommended: Use Pre-built EXE)

1. Download `ThermalPrintServer.exe` from the releases
2. Connect your thermal printer via USB
3. Run `ThermalPrintServer.exe`
4. Done! Access at `http://YOUR-IP:9100`

### Windows (From Source)

1. Install Python 3.8+ from https://python.org

2. Navigate to the print-server folder and set up virtual environment:
```bash
cd print-server
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Run the server:
```bash
python print_server.py
```

### Linux (Recommended: Auto-Install Script)

The installer automatically:
- Installs Python and dependencies
- Sets up USB permissions (udev rules)
- **Blacklists the `usblp` kernel module** (allows direct USB access like Zadig/WinUSB on Windows)
- Creates a systemd service for auto-start
- Configures everything for your printer

```bash
# Navigate to linux folder and run installer
cd print-server/linux
sudo ./install.sh
```

After installation:
```bash
# Start the service
sudo systemctl start thermal-print-server

# Check status
thermal-print-status

# View logs
journalctl -u thermal-print-server -f
```

### Linux (Quick Run - No Install)

For testing without installing as a service:
```bash
cd print-server/linux
chmod +x run.sh
./run.sh
```

### Linux (Manual Setup)

1. Install dependencies:
```bash
# Debian/Ubuntu
sudo apt install python3 python3-pip python3-venv libusb-1.0-0

# Fedora/RHEL
sudo dnf install python3 python3-pip libusb1

# Arch Linux
sudo pacman -S python python-pip libusb
```

2. Set up virtual environment:
```bash
cd print-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Add udev rules for USB printer access:
```bash
sudo ./linux/install.sh
# Or manually add rules - see linux/install.sh for full list
```

4. Run the server:
```bash
./venv/bin/python print_server.py
```

## Usage

1. Connect your thermal printer via USB to the computer
2. Activate venv: `.\venv\Scripts\Activate.ps1` (Windows) or `source venv/bin/activate` (Linux)
3. Run `python print_server.py`
4. The server will display:
   - Network URL: `http://192.168.x.x:9100`
   - mDNS Name: `http://printserver.local:9100`
5. In your web app, the default is `printserver.local` - just connect!

## API Endpoints

### GET /
Health check and service discovery. Returns:
```json
{
  "service": "Thermal Print Server",
  "version": "1.0.0",
  "printer": "Thermal Printer H58",
  "connected": true,
  "ip": "192.168.1.100"
}
```

### GET /status
Get printer status:
```json
{
  "printer": "Thermal Printer H58",
  "connected": true
}
```

### GET /reconnect
Try to reconnect to the printer.

### POST /print
Print receipts. Send JSON body:
```json
{
  "entries": [
    {
      "markaLotNumber": "ABC-123",
      "serialNumber": 1,
      "color": "Red",
      "numbers": [10.5, 20.3, 15.2],
      "total": 46.0
    }
  ]
}
```

### POST /print-raw
Send raw ESC/POS bytes:
```json
{
  "data": [27, 64, 72, 101, 108, 108, 111, 10]
}
```

## Troubleshooting

### Windows: "Printer not found"
- Make sure the printer is connected and turned on
- Check Device Manager for the printer
- **Use Zadig to install WinUSB driver** (required for USB access):
  1. Download Zadig from https://zadig.akeo.ie/
  2. Connect printer and open Zadig
  3. Select your printer from the dropdown
  4. Set driver to WinUSB and click "Replace Driver"

### Linux: "Access denied" or "Resource busy"
- The installer automatically blacklists the `usblp` kernel module
- If you installed manually, blacklist it yourself:
  ```bash
  sudo tee /etc/modprobe.d/thermal-printer-blacklist.conf << EOF
  blacklist usblp
  EOF
  sudo rmmod usblp 2>/dev/null  # Unload if currently loaded
  sudo update-initramfs -u      # Make permanent
  ```
- Run the udev rules command from the installer
- Add your user to the `lp` group: `sudo usermod -a -G lp $USER`
- Log out and back in (or reboot)

### "No module named win32print"
```bash
pip install pywin32
```

### "No module named usb"
```bash
pip install pyusb
```

## Auto-start on Boot

### Windows
1. Create a shortcut to `print_server.py`
2. Press Win+R, type `shell:startup`
3. Move the shortcut to the Startup folder

### Linux (systemd)
```bash
sudo tee /etc/systemd/system/print-server.service << EOF
[Unit]
Description=Thermal Print Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/print_server.py
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable print-server
sudo systemctl start print-server
```

## Building Standalone Executable

You can build a standalone `.exe` that runs on any Windows machine without Python installed.

### Build Steps

1. Make sure you have the virtual environment activated:
```bash
.\venv\Scripts\Activate.ps1   # Windows
source venv/bin/activate       # Linux
```

2. Install PyInstaller (included in requirements.txt):
```bash
pip install -r requirements.txt
```

3. Run the build script:
```bash
python build.py
```

4. The executable will be created at `dist/ThermalPrintServer.exe`

### Distribution

Just copy `ThermalPrintServer.exe` to any Windows machine and run it!

## Auto-Update System

The print server includes automatic update checking:

1. On startup, it checks GitHub for new releases
2. If a new version is found, it downloads and installs automatically
3. The server restarts with the new version

### Publishing Updates

1. Update the `VERSION` variable in `print_server.py`
2. Run `python build.py` to create new executable
3. Create a new release on GitHub with tag matching the version (e.g., `v1.1.0`)
4. Upload `dist/ThermalPrintServer.exe` as a release asset

### Configuration

In `print_server.py`:
```python
VERSION = "1.0.0"                                    # Current version
GITHUB_REPO = "your-username/textile-erp-print-server"  # Your GitHub repo
UPDATE_CHECK_ENABLED = True                          # Enable/disable auto-update
```

