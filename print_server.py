#!/usr/bin/env python3
"""
Thermal Printer Network Server
Runs on Windows/Linux machine with USB thermal printer connected.
Exposes HTTP API for network printing from any device.
"""

# Version info for auto-update
VERSION = "1.0.1"
GITHUB_REPO = "namanjain6767/textile-print-server"
UPDATE_CHECK_ENABLED = True

import socket
import json
import struct
import time
import sys
import os
import urllib.request
import tempfile
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Set up libusb DLL path for pyusb on Windows
def setup_libusb():
    """Setup libusb DLL path for both source and frozen (exe) execution"""
    try:
        # When running as exe, check if DLL is in the exe directory
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            exe_dir = os.path.dirname(sys.executable)
            possible_paths = [
                os.path.join(exe_dir, 'libusb-1.0.dll'),
                os.path.join(exe_dir, '_internal', 'libusb', '_platform', 'libusb-1.0.dll'),
            ]
            for dll_path in possible_paths:
                if os.path.exists(dll_path):
                    os.environ['PATH'] = os.path.dirname(dll_path) + os.pathsep + os.environ.get('PATH', '')
                    os.environ['LIBUSB_LIBRARY_PATH'] = dll_path
                    return True
        
        # Try the normal libusb package
        import libusb._platform
        dll_path = os.path.dirname(libusb._platform.DLL_PATH)
        os.environ['PATH'] = dll_path + os.pathsep + os.environ.get('PATH', '')
        os.environ['LIBUSB_LIBRARY_PATH'] = libusb._platform.DLL_PATH
        return True
    except Exception as e:
        print(f"  (libusb setup: {e})")
        return False

setup_libusb()

# ESC/POS Commands
ESC = 0x1B
GS = 0x1D

COMMANDS = {
    'INIT': bytes([ESC, 0x40]),
    'ALIGN_LEFT': bytes([ESC, 0x61, 0x00]),
    'ALIGN_CENTER': bytes([ESC, 0x61, 0x01]),
    'ALIGN_RIGHT': bytes([ESC, 0x61, 0x02]),
    'BOLD_ON': bytes([ESC, 0x45, 0x01]),
    'BOLD_OFF': bytes([ESC, 0x45, 0x00]),
    'DOUBLE_SIZE_ON': bytes([GS, 0x21, 0x30]),
    'NORMAL_SIZE': bytes([GS, 0x21, 0x00]),
    'LINE_FEED': bytes([0x0A]),
    'CUT_PAPER': bytes([GS, 0x56, 0x00]),
    'FEED_AND_CUT': bytes([ESC, 0x64, 0x03, GS, 0x56, 0x00]),
}

# Global printer connection
printer = None
printer_name = "Not Connected"

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def scan_all_usb_devices():
    """Scan and print all USB devices for debugging"""
    try:
        import usb.core
        import usb.backend.libusb1 as libusb1
        
        # Get the backend
        backend = libusb1.get_backend()
        if backend is None:
            print("libusb backend not available")
            return []
        
        print("\n=== Scanning all USB devices ===")
        devices = list(usb.core.find(find_all=True, backend=backend))
        if not devices:
            print("No USB devices found")
            return []
        
        for dev in devices:
            try:
                product = dev.product or "Unknown"
                print(f"  VID:0x{dev.idVendor:04x} PID:0x{dev.idProduct:04x} - {product}")
            except:
                print(f"  VID:0x{dev.idVendor:04x} PID:0x{dev.idProduct:04x}")
        print("================================\n")
        return devices
        
    except Exception as e:
        print(f"Scan error: {e}")
        return []

def find_printer_usb():
    """Find thermal printer via raw USB (for WinUSB driver)"""
    global printer, printer_name
    
    try:
        import usb.core
        import usb.util
        import usb.backend.libusb1 as libusb1
        
        # Get backend with DLL
        backend = libusb1.get_backend()
        if backend is None:
            print("libusb backend not found. Make sure libusb DLL is available.")
            return False
        
        # Scan all devices first for debugging
        devices = scan_all_usb_devices()
        if not devices:
            return False
        
        # Known thermal printer vendor IDs
        known_vids = [0x0483, 0x0416, 0x154F, 0x04B8, 0x0456, 0x6868, 0x0525, 0x1FC9, 0x0FE6, 0x20D1, 0x0DD4, 0x4B43, 0x1A86, 0x0CF3]
        
        # First, try to find by product name
        for dev in devices:
            try:
                product = (dev.product or "").lower()
                if 'printer' in product or 'thermal' in product or 'h58' in product:
                    print(f"Found printer by name: {dev.product}")
                    return connect_pyusb_printer(dev)
            except:
                continue
        
        # Try known vendor IDs
        for dev in devices:
            if dev.idVendor in known_vids:
                print(f"Found device with known printer VID: 0x{dev.idVendor:04x}")
                result = connect_pyusb_printer(dev)
                if result:
                    return True
        
        # Try all devices as last resort (skip known non-printers)
        skip_vids = [0x8087, 0x1D6B, 0x046D, 0x045E, 0x0B05, 0x1532]  # Intel, Linux, Logitech, Microsoft, ASUS, Razer
        for dev in devices:
            if dev.idVendor not in skip_vids:
                result = connect_pyusb_printer(dev)
                if result:
                    return True
        
        print("✗ No USB printer found")
        return False
        
    except ImportError as e:
        print(f"pyusb import error: {e}")
        return False
    except Exception as e:
        print(f"USB error: {e}")
        import traceback
        traceback.print_exc()
        return False

def connect_pyusb_printer(dev):
    """Connect to a USB device using pyusb"""
    global printer, printer_name
    import usb.core
    import usb.util
    
    try:
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except:
            pass
        
        try:
            dev.set_configuration()
        except usb.core.USBError as e:
            if "Resource busy" not in str(e) and "already set" not in str(e).lower():
                print(f"  Config error: {e}")
        
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]
        
        ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        
        if ep_out:
            printer = ep_out
            printer_name = dev.product or f"USB Printer (VID:0x{dev.idVendor:04x})"
            print(f"✓ Connected via pyusb: {printer_name}")
            return True
        return False
            
    except usb.core.USBError as e:
        print(f"  USB error: {e}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False

def find_printer_windows():
    """Find and connect to USB thermal printer on Windows"""
    global printer, printer_name
    
    # Try pyusb FIRST (for WinUSB driver from Zadig)
    if find_printer_usb():
        return True
    
    # Fall back to Windows printing API
    try:
        import win32print
        
        # Get default printer or find thermal printer
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        
        # Keywords that indicate a thermal/receipt printer
        thermal_keywords = ['thermal', 'pos', 'receipt', 'h58', 'hop', '58mm', '80mm', 'xprinter', 'epson tm', 'star tsp']
        
        # Keywords that indicate NOT a thermal printer (skip these)
        skip_keywords = ['onenote', 'pdf', 'xps', 'fax', 'microsoft', 'adobe', 'virtual', 'print to', 'send to']
        
        thermal_printer = None
        for p in printers:
            name = p[2].lower()
            
            # Skip known non-thermal printers
            if any(keyword in name for keyword in skip_keywords):
                continue
            
            # Look for thermal printer keywords
            if any(keyword in name for keyword in thermal_keywords):
                thermal_printer = p[2]
                break
        
        # If no thermal printer found by keywords, try to find any USB/Generic printer
        if not thermal_printer:
            for p in printers:
                name = p[2].lower()
                # Skip known non-thermal printers
                if any(keyword in name for keyword in skip_keywords):
                    continue
                # Accept USB or Generic printers
                if 'usb' in name or 'generic' in name:
                    thermal_printer = p[2]
                    break
        
        if thermal_printer:
            printer_name = thermal_printer
            printer = win32print.OpenPrinter(thermal_printer)
            print(f"✓ Connected to Windows printer: {thermal_printer}")
            return True
        else:
            print("✗ No thermal printer found (skipped non-thermal printers like OneNote, PDF, etc.)")
            print("  Please install WinUSB driver using Zadig for direct USB access")
            return False
            
    except ImportError:
        print("win32print not available")
        return False
    except Exception as e:
        print(f"Error connecting to Windows printer: {e}")
        return False

def find_printer_serial():
    """Find thermal printer via serial port"""
    global printer, printer_name
    try:
        import serial
        import serial.tools.list_ports
        
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if any(keyword in port.description.lower() for keyword in ['thermal', 'pos', 'printer', 'usb', 'serial']):
                try:
                    ser = serial.Serial(port.device, 9600, timeout=1)
                    printer = ser
                    printer_name = f"Serial: {port.device}"
                    print(f"✓ Connected to serial printer: {port.device}")
                    return True
                except:
                    continue
        
        # Try common ports
        for port_name in ['COM1', 'COM2', 'COM3', 'COM4', '/dev/ttyUSB0', '/dev/ttyACM0']:
            try:
                ser = serial.Serial(port_name, 9600, timeout=1)
                printer = ser
                printer_name = f"Serial: {port_name}"
                print(f"✓ Connected to serial port: {port_name}")
                return True
            except:
                continue
        
        print("✗ No serial printer found")
        return False
        
    except ImportError:
        print("pyserial not available")
        return False

def send_to_printer(data: bytes):
    """Send raw bytes to the printer"""
    global printer
    
    if printer is None:
        raise Exception("Printer not connected")
    
    try:
        # USB endpoint (pyusb) - has bEndpointAddress
        if hasattr(printer, 'bEndpointAddress'):
            printer.write(data)
        # Serial printer - has write and baudrate
        elif hasattr(printer, 'write') and hasattr(printer, 'baudrate'):
            printer.write(data)
        # Windows printer handle (integer from OpenPrinter)
        elif isinstance(printer, int):
            import win32print
            hJob = win32print.StartDocPrinter(printer, 1, ("Print Job", None, "RAW"))
            win32print.StartPagePrinter(printer)
            win32print.WritePrinter(printer, data)
            win32print.EndPagePrinter(printer)
            win32print.EndDocPrinter(printer)
        else:
            raise Exception("Unknown printer type")
            
        return True
    except Exception as e:
        print(f"Print error: {e}")
        raise

def format_line(left: str, right: str, width: int = 12) -> str:
    """Format a line with left and right text"""
    spaces = width - len(left) - len(right)
    if spaces < 1:
        return left + ' ' + right
    return left + ' ' * spaces + right

def print_receipt(entry: dict, settings: dict = None, is_last: bool = False):
    """Print a single receipt"""
    if settings is None:
        settings = {}
    
    custom_name = settings.get('customName')
    show_date = settings.get('showDate', False)
    white_space = settings.get('whiteSpace', 3)
    
    data = bytearray()
    
    # Initialize
    data.extend(COMMANDS['INIT'])
    
    # Custom name at top (if enabled)
    if custom_name:
        data.extend(COMMANDS['ALIGN_CENTER'])
        data.extend(COMMANDS['BOLD_ON'])
        data.extend(custom_name.encode('utf-8'))
        data.extend(COMMANDS['LINE_FEED'])
        data.extend(COMMANDS['BOLD_OFF'])
        data.extend(COMMANDS['ALIGN_LEFT'])
        data.extend(COMMANDS['LINE_FEED'])
    
    # Header: Marka+Lot and Serial #
    data.extend(COMMANDS['BOLD_ON'])
    data.extend(COMMANDS['DOUBLE_SIZE_ON'])
    header = format_line(entry['markaLotNumber'], f"#{entry['serialNumber']}", 12)
    data.extend(header.encode('utf-8'))
    data.extend(COMMANDS['LINE_FEED'])
    data.extend(COMMANDS['NORMAL_SIZE'])
    data.extend(COMMANDS['BOLD_OFF'])
    
    # Color
    data.extend(entry['color'].encode('utf-8'))
    data.extend(COMMANDS['LINE_FEED'])
    
    # Separator
    data.extend(b'------------------------')
    data.extend(COMMANDS['LINE_FEED'])
    
    # Numbers (right-aligned)
    data.extend(COMMANDS['ALIGN_RIGHT'])
    for num in entry['numbers']:
        data.extend(f"{num:.2f}".encode('utf-8'))
        data.extend(COMMANDS['LINE_FEED'])
    
    # Total line
    data.extend(b'--------')
    data.extend(COMMANDS['LINE_FEED'])
    data.extend(COMMANDS['BOLD_ON'])
    data.extend(COMMANDS['DOUBLE_SIZE_ON'])
    data.extend(f"{entry['total']:.2f}".encode('utf-8'))
    data.extend(COMMANDS['LINE_FEED'])
    data.extend(COMMANDS['NORMAL_SIZE'])
    data.extend(COMMANDS['BOLD_OFF'])
    
    # Reset alignment
    data.extend(COMMANDS['ALIGN_LEFT'])
    
    # Date at bottom (if enabled)
    if show_date:
        data.extend(COMMANDS['LINE_FEED'])
        data.extend(COMMANDS['ALIGN_CENTER'])
        from datetime import datetime
        date_str = datetime.now().strftime('%d-%m-%Y')
        data.extend(date_str.encode('utf-8'))
        data.extend(COMMANDS['LINE_FEED'])
        data.extend(COMMANDS['ALIGN_LEFT'])
    
    # Add white space (blank lines) before cut - not on last receipt
    if not is_last and white_space > 0:
        for _ in range(white_space):
            data.extend(COMMANDS['LINE_FEED'])
    
    # Feed and cut
    data.extend(COMMANDS['FEED_AND_CUT'])
    
    send_to_printer(bytes(data))

class PrintServerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for print server"""
    
    def _send_cors_headers(self):
        """Send CORS headers to allow cross-origin requests"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def _send_json_response(self, data: dict, status: int = 200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle preflight CORS requests"""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        
        if parsed.path == '/':
            # Health check / discovery endpoint
            self._send_json_response({
                'service': 'Thermal Print Server',
                'version': VERSION,
                'printer': printer_name,
                'connected': printer is not None,
                'ip': get_local_ip()
            })
        
        elif parsed.path == '/status':
            # Printer status
            self._send_json_response({
                'printer': printer_name,
                'connected': printer is not None,
                'version': VERSION
            })
        
        elif parsed.path == '/version':
            # Version info endpoint
            self._send_json_response({
                'version': VERSION,
                'repo': GITHUB_REPO
            })
        
        elif parsed.path == '/reconnect':
            # Try to reconnect printer
            connected = connect_printer()
            self._send_json_response({
                'success': connected,
                'printer': printer_name
            })
        
        else:
            self._send_json_response({'error': 'Not found'}, 404)
    
    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)
        
        if parsed.path == '/print':
            try:
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                data = json.loads(body.decode('utf-8'))
                
                entries = data.get('entries', [])
                if not entries:
                    self._send_json_response({'error': 'No entries to print'}, 400)
                    return
                
                # Get print settings
                settings = data.get('settings', {})
                entry_delay = settings.get('entryDelay', 0.5)
                
                # Print each entry
                for i, entry in enumerate(entries):
                    is_last = (i == len(entries) - 1)
                    print_receipt(entry, settings, is_last)
                    # Apply delay between entries (not after last one)
                    if not is_last:
                        time.sleep(entry_delay)
                
                self._send_json_response({
                    'success': True,
                    'printed': len(entries)
                })
                
            except Exception as e:
                self._send_json_response({
                    'success': False,
                    'error': str(e)
                }, 500)
        
        elif parsed.path == '/print-raw':
            # Print raw ESC/POS data
            try:
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                data = json.loads(body.decode('utf-8'))
                
                raw_data = bytes(data.get('data', []))
                send_to_printer(raw_data)
                
                self._send_json_response({'success': True})
                
            except Exception as e:
                self._send_json_response({
                    'success': False,
                    'error': str(e)
                }, 500)
        
        else:
            self._send_json_response({'error': 'Not found'}, 404)
    
    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[{self.log_date_time_string()}] {args[0]}")

def connect_printer():
    """Try to connect to printer using available methods"""
    if sys.platform == 'win32':
        return find_printer_windows()
    else:
        return find_printer_usb() or find_printer_serial()

def setup_mdns(port: int, local_ip: str):
    """Set up mDNS/Bonjour service advertisement"""
    try:
        from zeroconf import Zeroconf, ServiceInfo
        import socket
        
        # Create service info
        service_type = "_http._tcp.local."
        service_name = "Thermal Print Server._http._tcp.local."
        
        # Get hostname
        hostname = "printserver"
        
        service_info = ServiceInfo(
            service_type,
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties={
                'path': '/',
                'service': 'Thermal Print Server',
                'version': '1.0.0'
            },
            server=f"{hostname}.local."
        )
        
        zeroconf = Zeroconf()
        zeroconf.register_service(service_info)
        
        print(f"  mDNS Name:   http://{hostname}.local:{port}")
        
        return zeroconf, service_info
        
    except ImportError:
        print("  (mDNS not available - install zeroconf package)")
        return None, None
    except Exception as e:
        print(f"  (mDNS setup failed: {e})")
        return None, None

def check_for_updates():
    """Check GitHub for newer version and auto-update if available"""
    if not UPDATE_CHECK_ENABLED:
        return
    
    try:
        print("Checking for updates...")
        
        # Get latest release from GitHub API
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'ThermalPrintServer'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        latest_version = data.get('tag_name', '').lstrip('v')
        
        if not latest_version:
            print("  No releases found")
            return
        
        # Compare versions
        current_parts = [int(x) for x in VERSION.split('.')]
        latest_parts = [int(x) for x in latest_version.split('.')]
        
        is_newer = False
        for i in range(max(len(current_parts), len(latest_parts))):
            curr = current_parts[i] if i < len(current_parts) else 0
            latest = latest_parts[i] if i < len(latest_parts) else 0
            if latest > curr:
                is_newer = True
                break
            elif curr > latest:
                break
        
        if not is_newer:
            print(f"  You have the latest version (v{VERSION})")
            return
        
        print(f"  New version available: v{latest_version} (current: v{VERSION})")
        
        # Find the exe asset
        assets = data.get('assets', [])
        exe_asset = None
        for asset in assets:
            if asset['name'].endswith('.exe'):
                exe_asset = asset
                break
        
        if not exe_asset:
            print(f"  No executable found in release. Download manually from:")
            print(f"  https://github.com/{GITHUB_REPO}/releases/latest")
            return
        
        # Check if we're running as exe
        if not getattr(sys, 'frozen', False):
            print(f"  Running from source. Download exe from:")
            print(f"  https://github.com/{GITHUB_REPO}/releases/latest")
            return
        
        # Download and replace
        print(f"  Downloading update...")
        download_url = exe_asset['browser_download_url']
        
        # Get current exe path
        current_exe = sys.executable
        temp_exe = current_exe + '.new'
        backup_exe = current_exe + '.backup'
        
        # Download to temp file
        urllib.request.urlretrieve(download_url, temp_exe)
        
        print(f"  Installing update...")
        
        # Create updater batch script (Windows)
        if sys.platform == 'win32':
            updater_script = os.path.join(tempfile.gettempdir(), 'update_print_server.bat')
            with open(updater_script, 'w') as f:
                f.write(f'''@echo off
timeout /t 2 /nobreak > nul
if exist "{backup_exe}" del "{backup_exe}"
move "{current_exe}" "{backup_exe}"
move "{temp_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
''')
            print(f"  Update downloaded. Restarting...")
            os.startfile(updater_script)
            sys.exit(0)
        else:
            # Linux/Mac
            updater_script = '/tmp/update_print_server.sh'
            with open(updater_script, 'w') as f:
                f.write(f'''#!/bin/bash
sleep 2
mv "{current_exe}" "{backup_exe}"
mv "{temp_exe}" "{current_exe}"
chmod +x "{current_exe}"
"{current_exe}" &
rm "$0"
''')
            os.chmod(updater_script, 0o755)
            print(f"  Update downloaded. Restarting...")
            os.system(f'nohup {updater_script} &')
            sys.exit(0)
            
    except urllib.error.URLError as e:
        print(f"  Update check failed: Network error")
    except Exception as e:
        print(f"  Update check failed: {e}")

def main():
    """Main entry point"""
    PORT = 9100
    
    print("=" * 50)
    print("  Thermal Printer Network Server")
    print(f"  Version: {VERSION}")
    print("=" * 50)
    print()
    
    # Check for updates
    check_for_updates()
    print()
    
    # Connect to printer
    print("Searching for printer...")
    if connect_printer():
        print(f"Printer ready: {printer_name}")
    else:
        print("Warning: No printer connected. Will retry on print requests.")
    
    print()
    
    # Get local IP
    local_ip = get_local_ip()
    
    # Start HTTP server
    server = HTTPServer(('0.0.0.0', PORT), PrintServerHandler)
    
    print(f"Server started!")
    print(f"")
    print(f"  Local URL:   http://localhost:{PORT}")
    print(f"  Network URL: http://{local_ip}:{PORT}")
    
    # Set up mDNS
    zeroconf, service_info = setup_mdns(PORT, local_ip)
    
    print(f"")
    print(f"Use Network URL or mDNS Name in your app's Print Settings.")
    print(f"Press Ctrl+C to stop the server.")
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        if zeroconf and service_info:
            zeroconf.unregister_service(service_info)
            zeroconf.close()
        server.server_close()
        print("Server stopped.")

if __name__ == '__main__':
    main()
