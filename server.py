#!/usr/bin/env python3
"""
Downloads Sync
Sync files between your Android Download and your PC's Downloads folder.
Works on Mac, Windows, and Linux. 100% private via your own WiFi.
"""

import http.server
import os
import socket
import platform
import json
import urllib.parse
import mimetypes
from datetime import datetime
from pathlib import Path

PORT = 8766
SYSTEM = platform.system()
DOWNLOADS_FOLDER = str(Path.home() / "Downloads")

# File type icons for the UI
FILE_ICONS = {
    'image': '🖼️',
    'video': '🎬',
    'audio': '🎵',
    'pdf': '📄',
    'document': '📝',
    'archive': '📦',
    'code': '💻',
    'default': '📄'
}

def get_file_icon(filename):
    """Get appropriate icon for file type."""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico']:
        return FILE_ICONS['image']
    elif ext in ['mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v']:
        return FILE_ICONS['video']
    elif ext in ['mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg']:
        return FILE_ICONS['audio']
    elif ext == 'pdf':
        return FILE_ICONS['pdf']
    elif ext in ['doc', 'docx', 'txt', 'rtf', 'odt', 'md', 'csv', 'xlsx', 'xls']:
        # Differentiate document types
        if ext in ['csv', 'xlsx', 'xls']:
            return '📊'  # Spreadsheet
        elif ext in ['doc', 'docx']:
            return '📘'  # Word doc
        elif ext == 'md':
            return '📋'  # Markdown
        elif ext == 'txt':
            return '📝'  # Text
        else:
            return FILE_ICONS['document']
    elif ext in ['zip', 'rar', '7z', 'tar', 'gz', 'bz2']:
        return FILE_ICONS['archive']
    elif ext in ['py', 'js', 'ts', 'tsx', 'jsx', 'html', 'css', 'json', 'xml', 'yaml', 'yml', 
                  'sh', 'bat', 'java', 'c', 'cpp', 'h', 'hpp', 'go', 'rs', 'rb', 'php', 'sql',
                  'swift', 'kt', 'kts', 'toml', 'ini', 'conf', 'vue', 'svelte', 'scss', 'sass',
                  'less', 'r', 'lua', 'pl', 'pm', 'ps1', 'psm1', 'dockerfile', 'makefile']:
        return FILE_ICONS['code']
    else:
        return FILE_ICONS['default']

def format_file_size(size_bytes):
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != 'B' else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def get_files_list():
    """Get list of files in Downloads folder."""
    files = []
    try:
        for entry in os.scandir(DOWNLOADS_FOLDER):
            # Skip hidden files/folders (starting with .)
            if entry.name.startswith('.'):
                continue
            if entry.is_file():
                stat = entry.stat()
                files.append({
                    'name': entry.name,
                    'size': stat.st_size,
                    'size_formatted': format_file_size(stat.st_size),
                    'modified': stat.st_mtime,
                    'icon': get_file_icon(entry.name)
                })
        # Sort by modification time, newest first
        files.sort(key=lambda x: x['modified'], reverse=True)
    except Exception as e:
        print(f"Error listing files: {e}")
    return files


class FileTransferHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        """Handle file upload from phone."""
        try:
            content_type = self.headers.get('Content-Type', '')
            content_length = int(self.headers.get('Content-Length', 0))
            
            if content_length == 0:
                self.send_error(400, "No file data received")
                return
            
            # Get filename from header or generate one
            filename = self.headers.get('X-Filename', '')
            if filename:
                filename = urllib.parse.unquote(filename)
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"phone_file_{timestamp}"
            
            # Sanitize filename
            filename = os.path.basename(filename)
            
            # Read file data
            file_data = self.rfile.read(content_length)
            
            # Save to Downloads folder
            file_path = os.path.join(DOWNLOADS_FOLDER, filename)
            
            # Handle duplicate filenames
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(file_path):
                file_path = os.path.join(DOWNLOADS_FOLDER, f"{base}_{counter}{ext}")
                counter += 1
            
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            saved_name = os.path.basename(file_path)
            print(f"✅ File saved: {saved_name} ({format_file_size(len(file_data))})")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'filename': saved_name,
                'size': len(file_data)
            }).encode())
            
        except Exception as e:
            print(f"❌ Upload error: {e}")
            self.send_error(500, str(e))
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/':
            self.serve_html()
        elif path == '/files':
            self.serve_files_list()
        elif path.startswith('/download/'):
            filename = urllib.parse.unquote(path[10:])
            self.serve_file_download(filename)
        else:
            self.send_error(404)
    
    def serve_files_list(self):
        """Serve JSON list of files."""
        files = get_files_list()
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(files).encode())
    
    def serve_file_download(self, filename):
        """Serve a file for download."""
        # Sanitize filename to prevent directory traversal
        filename = os.path.basename(filename)
        file_path = os.path.join(DOWNLOADS_FOLDER, filename)
        
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(404, "File not found")
            return
        
        try:
            file_size = os.path.getsize(file_path)
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Stream file in chunks
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(65536)  # 64KB chunks
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            
            print(f"📤 Downloaded: {filename}")
            
        except Exception as e:
            print(f"❌ Download error: {e}")
            self.send_error(500, str(e))
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Filename')
        self.end_headers()

    def serve_html(self):
        """Serve the main HTML page."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

        html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#fafafa">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>📁</title>

    <!-- App Icon -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect x='0' y='0' width='100' height='100' fill='%23fafafa'/%3E%3Crect x='20' y='30' width='60' height='50' rx='4' fill='%23222'/%3E%3Crect x='20' y='20' width='30' height='15' rx='3' fill='%23222'/%3E%3C/svg%3E">
    <link rel="apple-touch-icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect x='0' y='0' width='100' height='100' fill='%23ffffff'/%3E%3Crect x='20' y='30' width='60' height='50' rx='4' fill='%23222222'/%3E%3Crect x='20' y='20' width='30' height='15' rx='3' fill='%23222222'/%3E%3C/svg%3E">

    <!-- Web Manifest -->
    <link rel="manifest" href="data:application/manifest+json,%7B%22short_name%22%3A%22DLSync%22%2C%22name%22%3A%22Downloads%20Sync%22%2C%22icons%22%3A%5B%7B%22src%22%3A%22data%3Aimage%2Fsvg%2Bxml%2C%253Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20viewBox%3D'0%200%20100%20100'%253E%253Crect%20x%3D'0'%20y%3D'0'%20width%3D'100'%20height%3D'100'%20fill%3D'%2523ffffff'%2F%253E%253Crect%20x%3D'20'%20y%3D'30'%20width%3D'60'%20height%3D'50'%20rx%3D'4'%20fill%3D'%2523222222'%2F%253E%253C%2Fsvg%253E%22%2C%22type%22%3A%22image%2Fsvg%2Bxml%22%2C%22sizes%22%3A%22any%22%7D%5D%2C%22start_url%22%3A%22.%22%2C%22display%22%3A%22standalone%22%2C%22theme_color%22%3A%22%23fafafa%22%2C%22background_color%22%3A%22%23fafafa%22%7D">
    
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        html, body {
            height: 100%;
            font-family: system-ui, -apple-system, sans-serif;
            background: #fafafa;
            overflow-x: hidden;
            touch-action: manipulation;
        }

        .app {
            min-height: 100%;
            display: flex;
            flex-direction: column;
            padding: 30px 20px 40px 20px;
            max-width: 500px;
            margin: 0 auto;
        }

        /* Header */
        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        .title {
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: #222;
        }

        /* Section styling */
        .section {
            margin-bottom: 30px;
        }

        .section-title {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .section-title::after {
            content: '';
            flex: 1;
            height: 1px;
            background: #e0e0e0;
        }

        /* Upload area */
        .upload-area {
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 30px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
        }

        .upload-btn {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            border: 4px solid #222;
            background: white;
            cursor: pointer;
            position: relative;
            transition: transform 0.1s;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .upload-btn::after {
            content: '+';
            font-size: 40px;
            font-weight: 300;
            color: #222;
            line-height: 1;
        }

        .upload-btn:active {
            transform: scale(0.92);
        }

        .upload-hint {
            margin-top: 15px;
            font-size: 12px;
            color: #888;
        }

        /* Pending files */
        .pending-files {
            width: 100%;
            margin-top: 20px;
        }

        .pending-file {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: #f5f5f5;
            border-radius: 10px;
            margin-bottom: 8px;
        }

        .pending-file-icon {
            font-size: 24px;
        }

        .pending-file-info {
            flex: 1;
            min-width: 0;
        }

        .pending-file-name {
            font-size: 14px;
            font-weight: 500;
            color: #222;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .pending-file-size {
            font-size: 12px;
            color: #888;
        }

        .pending-file-remove {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            border: none;
            background: #e0e0e0;
            color: #666;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .send-all-btn {
            width: 100%;
            padding: 14px;
            border-radius: 12px;
            border: none;
            background: #222;
            color: white;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 12px;
            transition: all 0.15s;
        }

        .send-all-btn:active {
            background: #444;
        }

        .send-all-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }

        .send-all-btn.success {
            background: #22c55e;
        }

        /* Mac files list */
        .mac-files {
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
            overflow: hidden;
        }

        .file-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 16px;
            border-bottom: 1px solid #f0f0f0;
            cursor: pointer;
            transition: background 0.15s;
        }

        .file-item:last-child {
            border-bottom: none;
        }

        .file-item:active {
            background: #f5f5f5;
        }

        .file-icon {
            font-size: 28px;
            width: 40px;
            text-align: center;
        }

        .file-info {
            flex: 1;
            min-width: 0;
        }

        .file-name {
            font-size: 14px;
            font-weight: 500;
            color: #222;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .file-meta {
            font-size: 12px;
            color: #888;
            margin-top: 2px;
        }

        .file-download {
            font-size: 18px;
            color: #888;
        }

        .empty-state {
            padding: 40px;
            text-align: center;
            color: #888;
            font-size: 13px;
        }

        .refresh-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            padding: 10px 16px;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            background: white;
            color: #666;
            font-size: 13px;
            cursor: pointer;
            margin: 15px auto 0 auto;
        }

        .refresh-btn:active {
            background: #f5f5f5;
        }

        /* Status messages */
        #status {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 20px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 500;
            opacity: 0;
            transition: opacity 0.3s;
            pointer-events: none;
            z-index: 100;
        }

        #status.show {
            opacity: 1;
        }

        #status.success {
            background: #22c55e;
            color: white;
        }

        #status.error {
            background: #ef4444;
            color: white;
        }

        #status.loading {
            background: #222;
            color: white;
        }

        /* Loading spinner */
        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        input[type="file"] { display: none; }

        /* Hint at bottom */
        .hint {
            margin-top: auto;
            padding-top: 30px;
            font-size: 11px;
            color: #bbb;
            text-align: center;
            line-height: 1.8;
        }
    </style>
</head>
<body>
    <div class="app">
        <div class="header">
            <div class="title" id="mainTitle">Files ↔ Phone</div>
        </div>

        <!-- Upload Section -->
        <div class="section" id="uploadSection">
            <div class="section-title" id="uploadSectionTitle">Send to Phone</div>
            <div class="upload-area">
                <button class="upload-btn" id="uploadBtn" aria-label="Choose files"></button>
                <div class="upload-hint">Tap to choose files</div>
                
                <div class="pending-files" id="pendingFiles"></div>
                <button class="send-all-btn" id="sendBtn" style="display: none;">Send</button>
            </div>
        </div>

        <!-- Download Section -->
        <div class="section" id="downloadSection">
            <div class="section-title" id="downloadSectionTitle">Download from PC</div>
            <div class="mac-files" id="macFiles">
                <div class="empty-state">Loading...</div>
            </div>

        </div>

        <input type="file" id="fileInput" multiple>

        <div id="status"></div>

        <div class="hint" id="hintText">
            Files sync between your phone and PC Downloads
        </div>
    </div>

    <script>
        const fileInput = document.getElementById('fileInput');
        const uploadBtn = document.getElementById('uploadBtn');
        const pendingFilesEl = document.getElementById('pendingFiles');
        const sendBtn = document.getElementById('sendBtn');
        const macFilesEl = document.getElementById('macFiles');

        const statusEl = document.getElementById('status');

        let pendingFiles = [];

        // Desktop detection - if true, hide downloads section
        const isDesktop = !(/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile/i.test(navigator.userAgent));
        


        // Update UI based on device
        function updateUIForDevice() {
            const mainTitle = document.getElementById('mainTitle');
            const uploadSectionTitle = document.getElementById('uploadSectionTitle');
            const downloadSectionTitle = document.getElementById('downloadSectionTitle');
            const hintText = document.getElementById('hintText');
            const downloadSection = document.getElementById('downloadSection');

            if (isDesktop) {
                // Desktop: Hide downloads section
                mainTitle.textContent = 'Files → Phone';
                uploadSectionTitle.textContent = 'Send to Phone';
                downloadSection.style.display = 'none';
                hintText.innerHTML = 'Pick files here → Download them on your phone<br>Or open this URL on your phone to send files to your PC';
            } else {
                // Mobile: Show both sections
                mainTitle.textContent = 'Files ↔ PC';
                uploadSectionTitle.textContent = 'Send to PC';
                downloadSectionTitle.textContent = 'Download from PC';
                downloadSection.style.display = 'block';
                hintText.innerHTML = 'Pick files from your phone → Send to PC<br>Tap files above to download from PC';
            }
        }

        // Utils
        function formatSize(bytes) {
            const units = ['B', 'KB', 'MB', 'GB'];
            let i = 0;
            while (bytes >= 1024 && i < units.length - 1) {
                bytes /= 1024;
                i++;
            }
            return `${bytes.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
        }

        function showStatus(message, type, duration = 3000) {
            statusEl.textContent = message;
            statusEl.className = `show ${type}`;
            if (duration > 0) {
                setTimeout(() => statusEl.className = '', duration);
            }
        }

        function getFileIcon(filename) {
            const ext = filename.toLowerCase().split('.').pop();
            const icons = {
                image: ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'],
                video: ['mp4', 'mov', 'avi', 'mkv', 'webm'],
                audio: ['mp3', 'wav', 'flac', 'aac', 'm4a'],
                pdf: ['pdf'],
                doc: ['doc', 'docx', 'txt', 'rtf', 'md'],
                archive: ['zip', 'rar', '7z', 'tar', 'gz']
            };
            
            for (const [type, exts] of Object.entries(icons)) {
                if (exts.includes(ext)) {
                    return { image: '🖼️', video: '🎬', audio: '🎵', pdf: '📄', doc: '📝', archive: '📦' }[type];
                }
            }
            return '📁';
        }

        // Upload handling
        uploadBtn.onclick = () => fileInput.click();

        fileInput.onchange = (e) => {
            const files = Array.from(e.target.files);
            files.forEach(file => {
                if (!pendingFiles.some(f => f.name === file.name && f.size === file.size)) {
                    pendingFiles.push(file);
                }
            });
            renderPendingFiles();
            fileInput.value = '';
        };

        function renderPendingFiles() {
            if (pendingFiles.length === 0) {
                pendingFilesEl.innerHTML = '';
                sendBtn.style.display = 'none';
                return;
            }

            pendingFilesEl.innerHTML = pendingFiles.map((file, i) => `
                <div class="pending-file">
                    <span class="pending-file-icon">${getFileIcon(file.name)}</span>
                    <div class="pending-file-info">
                        <div class="pending-file-name">${file.name}</div>
                        <div class="pending-file-size">${formatSize(file.size)}</div>
                    </div>
                    <button class="pending-file-remove" data-index="${i}">×</button>
                </div>
            `).join('');

            sendBtn.style.display = 'block';
            const target = isMobile ? 'PC' : 'Phone';
            sendBtn.textContent = `Send ${pendingFiles.length} file${pendingFiles.length > 1 ? 's' : ''} to ${target}`;

            // Add remove handlers
            pendingFilesEl.querySelectorAll('.pending-file-remove').forEach(btn => {
                btn.onclick = (e) => {
                    const idx = parseInt(e.target.dataset.index);
                    pendingFiles.splice(idx, 1);
                    renderPendingFiles();
                };
            });
        }

        sendBtn.onclick = async () => {
            if (pendingFiles.length === 0) return;

            sendBtn.disabled = true;
            sendBtn.innerHTML = '<span class="spinner"></span>Sending...';

            let successCount = 0;
            let failCount = 0;

            for (const file of pendingFiles) {
                try {
                    const res = await fetch(location.href, {
                        method: 'POST',
                        body: file,
                        headers: {
                            'Content-Type': file.type || 'application/octet-stream',
                            'X-Filename': encodeURIComponent(file.name)
                        }
                    });

                    if (res.ok) {
                        successCount++;
                    } else {
                        failCount++;
                    }
                } catch (e) {
                    failCount++;
                }
            }

            if (successCount > 0) {
                sendBtn.classList.add('success');
                sendBtn.textContent = `✓ ${successCount} file${successCount > 1 ? 's' : ''} sent!`;
                if (navigator.vibrate) navigator.vibrate(50);
                
                setTimeout(() => {
                    pendingFiles = [];
                    renderPendingFiles();
                    sendBtn.classList.remove('success');
                    loadMacFiles();
                }, 1500);
            }

            if (failCount > 0) {
                showStatus(`Failed to send ${failCount} file${failCount > 1 ? 's' : ''}`, 'error');
            }

            sendBtn.disabled = false;
        };

        // PC files listing
        async function loadMacFiles() {
            try {
                const res = await fetch('/files');
                const files = await res.json();

                if (files.length === 0) {
                    macFilesEl.innerHTML = '<div class="empty-state">No files in Downloads folder</div>';
                    return;
                }

                macFilesEl.innerHTML = files.slice(0, 50).map(file => `
                    <div class="file-item" data-filename="${encodeURIComponent(file.name)}">
                        <span class="file-icon">${file.icon}</span>
                        <div class="file-info">
                            <div class="file-name">${file.name}</div>
                            <div class="file-meta">${file.size_formatted}</div>
                        </div>
                        <span class="file-download">↓</span>
                    </div>
                `).join('');

                // Add download handlers
                macFilesEl.querySelectorAll('.file-item').forEach(item => {
                    item.onclick = () => {
                        const filename = decodeURIComponent(item.dataset.filename);
                        downloadFile(filename);
                    };
                });

            } catch (e) {
                macFilesEl.innerHTML = '<div class="empty-state">Could not load files</div>';
            }
        }

        function downloadFile(filename) {
            showStatus('Starting download...', 'loading', 0);
            
            const link = document.createElement('a');
            link.href = `/download/${encodeURIComponent(filename)}`;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            setTimeout(() => {
                showStatus(`Downloaded: ${filename}`, 'success');
            }, 500);
        }



        // Initialize
        updateUIForDevice();
        loadMacFiles();
    </script>
</body>
</html>'''
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def get_local_ip():
    """Get the local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"


def main():
    local_ip = get_local_ip()

    print("\n" + "="*50)
    print("📁 Downloads Sync")
    print("="*50)
    print(f"\n🌐 Server running at: http://{local_ip}:{PORT}")
    print(f"\n📱 Open this URL on your phone's browser")
    print(f"📂 Files will be saved to: {DOWNLOADS_FOLDER}")
    print("\n" + "="*50)
    print("Waiting for file transfers...\n")

    server = http.server.HTTPServer(('0.0.0.0', PORT), FileTransferHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
