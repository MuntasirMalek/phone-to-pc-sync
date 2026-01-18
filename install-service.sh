#!/bin/bash

# Downloads Sync - Service Installer for macOS/Linux
# This script installs Downloads Sync as a background service

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="downloadssync"

echo ""
echo "📁 Downloads Sync - Service Installer"
echo "======================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "   Install it from: https://www.python.org/"
    exit 1
fi

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - use launchd
    PLIST_PATH="$HOME/Library/LaunchAgents/com.$SERVICE_NAME.plist"
    
    # Stop existing service if running
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    
    # Create plist
    cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.$SERVICE_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPT_DIR/server.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/$SERVICE_NAME.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/$SERVICE_NAME.error.log</string>
</dict>
</plist>
EOF

    # Load the service
    launchctl load "$PLIST_PATH"
    
    echo "✅ Service installed and started!"
    echo ""
    echo "📍 The service will auto-start on login."
    echo ""
    echo "To stop the service:"
    echo "   launchctl unload $PLIST_PATH"
    echo ""

elif [[ "$OSTYPE" == "linux"* ]]; then
    # Linux - use systemd user service
    SERVICE_DIR="$HOME/.config/systemd/user"
    SERVICE_FILE="$SERVICE_DIR/$SERVICE_NAME.service"
    
    mkdir -p "$SERVICE_DIR"
    
    # Stop existing service if running
    systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
    
    # Create service file
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Downloads Sync
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $SCRIPT_DIR/server.py
WorkingDirectory=$SCRIPT_DIR
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

    # Reload and start
    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME"
    systemctl --user start "$SERVICE_NAME"
    
    echo "✅ Service installed and started!"
    echo ""
    echo "📍 The service will auto-start on login."
    echo ""
    echo "To stop the service:"
    echo "   systemctl --user stop $SERVICE_NAME"
    echo ""
    echo "To disable auto-start:"
    echo "   systemctl --user disable $SERVICE_NAME"
    echo ""

else
    echo "❌ Unsupported operating system: $OSTYPE"
    exit 1
fi

# Get and display the URL
sleep 1
python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(('8.8.8.8', 80))
print(f'🌐 Open on your phone: http://{s.getsockname()[0]}:8766')
s.close()
" 2>/dev/null || echo "🌐 Server running on port 8766"

echo ""
