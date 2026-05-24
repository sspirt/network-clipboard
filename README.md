# Local Network Clipboard
A secure, cross-platform local network clipboard synchronization tool built with Python. It allows seamless, encrypted text sharing between Windows and macOS devices in the same local network, sitting quietly in your system tray
## Key Features
- **End-to-End Encryption:** All transmitted clipboard data is encrypted using AES-128 (Fernet) based on a SHA-256 hashed pre-shared key (password)
- **Multi-Format Data Transfer:** Seamlessly synchronizes not only plain text but also handles secure file transfers across connected devices
- **Clipboard History:** Keeps track of previously synced items, allowing you to quickly access your clipboard logs without losing older data
- **System Tray Integration:** Runs entirely in the background with convenient system tray controls and OS-native desktop notifications
- **Zero-Config Discovery:** Simple direct IP connections for robust peer-to-peer data transfer
---
## Installation & Running from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/sspirt/network-clipboard.git
   ```
2. Install dependencies:
    ```bash
   pip install -r requirements.txt
    ```
3. Run the application:
    ```bash
   python app.py
    ```
---
## Standalone Releases
You can download pre-compiled single-file binaries for your OS from the **Releases** section
### 🪟 Windows
- Download the zipped archive `Network-Clipboard-Windows.zip` from **Releases**
- Extract the folder and run `Network Clipboard.exe`
### 🍏 macOS
- Download the disk image file `Network-Clipboard-macOS.dmg` from **Releases**
- Double-click the `.dmg` file to mount it, then drag and drop **Network Clipboard** into your **Applications** folder

Due to macOS Gatekeeper security policies for unidentified developers, the first launch might be blocked
- **Fix 1:** Right-click the app in your **Applications** folder, select **Open**, and then click **Open** again in the confirmation dialog
- **Fix 2:** If it still refuses to launch, open **Terminal** and run the following command to strip the quarantine flag
   ```bash
   xattr -cr "/Applications/Network Clipboard.app"
   ```
---
## Building from Source
If you want to modify the code or compile the binaries yourself, you can use **PyInstaller**
```bash
pip install pyinstaller
```