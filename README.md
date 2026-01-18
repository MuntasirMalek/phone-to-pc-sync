# 📁 Downloads Sync

Sync files between your Android Download and your computer's Downloads folder.  
⚡ Lightning fast · 🔒 100% private via your own WiFi · ☁️ No cloud

## ✨ Features

- 📱 **Phone → PC**: Pick files from Android → instantly appear in your PC Downloads
- 💻 **PC → Phone**: Tap any PC file → downloads to your Android
- 🔒 **Private**: Everything stays on your local network
- 💻 **Cross-platform**: Works on Mac, Windows, and Linux

## 🚀 Quick Start

### 1. Download

```bash
git clone https://github.com/MuntasirMalek/phone-to-pc-sync.git
cd phone-to-pc-sync
```

Or [Download ZIP](https://github.com/MuntasirMalek/phone-to-pc-sync/archive/refs/heads/main.zip) and extract it.

### 2. Install & Start (runs in background)

**Mac:**
```bash
./install-service.sh
```

**Windows:**
```
install-service.bat
```
(Or double-click `install-service.bat` - run as Administrator)

**Linux:**
```bash
./install-service.sh
```

All platforms: Installs as a background service that auto-starts on login!

You'll see a URL like:
```
🌐 Server running at: http://192.168.X.X:8766
```

### 3. Open on Your Phone

1. Open your phone's browser
2. Go to the URL shown (e.g., `http://192.168.1.100:8766`)
3. Bookmark it for quick access!

### 4. Transfer Files!

**Phone → PC:**
1. Tap the + button
2. Select files from your phone
3. Tap "Send"
4. Files appear in your PC's Downloads folder!

**PC → Phone:**
1. Scroll down to see your PC's Downloads files
2. Tap any file to download it to your phone

### 5. Stop / Uninstall

**Mac (background service):**
```bash
launchctl unload ~/Library/LaunchAgents/com.downloadssync.plist
```

**Windows (background service):**
Delete `DownloadsSync.vbs` from:
```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```
Then restart or end the Python process in Task Manager.

**Linux (systemd):**
```bash
systemctl --user stop downloadssync
systemctl --user disable downloadssync
```

## 📱 Pro Tips

### Add to Home Screen

**iOS Safari:**
1. Tap the Share button
2. Tap "Add to Home Screen"
3. Tap "Add"

**Android Chrome:**
1. Tap the ⋮ menu
2. Tap "Add to Home screen"
3. Tap "Add"

Now it works like a native app!

## 🔧 Requirements

- Python 3.6+
- Both devices on the same WiFi network

## 🛡️ Privacy

- **No cloud**: All transfers happen directly over your local network
- **No accounts**: No sign-up, no login, no tracking
- **No internet**: Works even if your WiFi has no internet access
- Only accessible from devices on your local network

## 🐛 Troubleshooting

**Can't connect from phone?**
- Ensure both devices are on the same WiFi network
- Try disabling VPN on your phone
- Check if your firewall allows port 8766

**Files not appearing?**
- Check your PC's Downloads folder (`~/Downloads`)
- Refresh the file list on your phone

## 📄 License

MIT License - Use it however you want!
