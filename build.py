#!/usr/bin/env python3
"""
Build script for creating standalone executable of Thermal Print Server
"""

import subprocess
import sys
import os
import shutil

def main():
    print("=" * 50)
    print("  Building Thermal Print Server Executable")
    print("=" * 50)
    print()
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Clean previous builds
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            print(f"Cleaning {folder}/...")
            shutil.rmtree(folder)
    
    # Build command
    build_cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',                    # Single executable
        '--console',                    # Show console window
        '--name', 'ThermalPrintServer', # Output name
        '--icon', 'NONE',               # No icon (can add later)
        # Hidden imports for packages that PyInstaller might miss
        '--hidden-import', 'usb',
        '--hidden-import', 'usb.core',
        '--hidden-import', 'usb.util',
        '--hidden-import', 'usb.backend',
        '--hidden-import', 'usb.backend.libusb1',
        '--hidden-import', 'libusb',
        '--hidden-import', 'zeroconf',
        '--hidden-import', 'serial',
        '--hidden-import', 'serial.tools.list_ports',
        # Collect all data from these packages
        '--collect-all', 'libusb',
        '--collect-all', 'zeroconf',
        # Main script
        'print_server.py'
    ]
    
    print()
    print("Building executable...")
    print()
    
    result = subprocess.run(build_cmd)
    
    if result.returncode == 0:
        print()
        print("=" * 50)
        print("  Build Complete!")
        print("=" * 50)
        print()
        print(f"  Executable: dist/ThermalPrintServer.exe")
        print()
        print("  To distribute:")
        print("  1. Copy dist/ThermalPrintServer.exe to target machine")
        print("  2. Run it - no Python installation required!")
        print()
        print("  To publish update to GitHub:")
        print("  1. Update VERSION in print_server.py")
        print("  2. Run this build script")
        print("  3. Create a new release on GitHub")
        print("  4. Upload dist/ThermalPrintServer.exe as release asset")
        print()
    else:
        print()
        print("Build failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
