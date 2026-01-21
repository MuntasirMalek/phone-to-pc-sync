#!/usr/bin/env python3
"""
Phone PC Sync
Sync files, text, and photos between your Android phone and your PC.
Camera to clipboard: Snap a photo → Ctrl+V on your computer.
Works on Mac, Windows, and Linux. 100% private via your own WiFi.
"""

import http.server
import os
import socket
import platform
import json
import urllib.parse
import mimetypes
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

PORT = 8766
SYSTEM = platform.system()
DOWNLOADS_FOLDER = str(Path.home() / "Downloads")

# In-memory text sync storage
synced_text = ""

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
    
    # Incomplete/temporary download files
    if ext in ['crdownload', 'part', 'tmp', 'download', 'partial']:
        return '⏳'  # In progress
    
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


def copy_image_to_clipboard(image_path):
    """Copy an image to clipboard. Returns (success, error_message)."""
    try:
        if SYSTEM == 'Darwin':  # macOS
            # Use TIFF format which works for both PNG and JPEG
            applescript = f'''
            set theFile to POSIX file "{image_path}"
            set theImage to read theFile as TIFF picture
            set the clipboard to theImage
            '''
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, None
            
            # Fallback: using NSPasteboard via AppleScript
            fallback_script = f'''
            use framework "AppKit"
            set theImage to current application's NSImage's alloc()'s initWithContentsOfFile:"{image_path}"
            set thePasteboard to current application's NSPasteboard's generalPasteboard()
            thePasteboard's clearContents()
            thePasteboard's writeObjects:{{theImage}}
            '''
            result2 = subprocess.run(
                ['osascript', '-e', fallback_script],
                capture_output=True,
                text=True
            )
            if result2.returncode == 0:
                return True, None
            return False, result.stderr
            
        elif SYSTEM == 'Windows':
            # PowerShell command to copy image to clipboard
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            $image = [System.Drawing.Image]::FromFile("{image_path}")
            [System.Windows.Forms.Clipboard]::SetImage($image)
            '''
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True, None
            return False, result.stderr
            
        elif SYSTEM == 'Linux':
            # Use xclip for Linux (most common)
            try:
                with open(image_path, 'rb') as f:
                    result = subprocess.run(
                        ['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i'],
                        stdin=f,
                        capture_output=True
                    )
                if result.returncode == 0:
                    return True, None
            except FileNotFoundError:
                pass
            
            # Try xsel as fallback
            try:
                with open(image_path, 'rb') as f:
                    result = subprocess.run(
                        ['xsel', '--clipboard', '--input', '--type', 'image/png'],
                        stdin=f,
                        capture_output=True
                    )
                if result.returncode == 0:
                    return True, None
            except FileNotFoundError:
                pass
            
            return False, "Install xclip: sudo apt install xclip"
            
        else:
            return False, f"Unsupported OS: {SYSTEM}"
            
    except Exception as e:
        return False, str(e)

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
        """Handle file upload and text sync."""
        global synced_text
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # Handle text sync
        if path == '/text':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    text_data = self.rfile.read(content_length).decode('utf-8')
                    synced_text = text_data
                    print(f"📝 Text synced: {len(text_data)} characters")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'length': len(synced_text)}).encode())
            except Exception as e:
                print(f"❌ Text sync error: {e}")
                self.send_error(500, str(e))
            return
        
        # Handle clipboard image (camera paster feature)
        if path == '/clipboard':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                
                if content_length == 0:
                    self.send_error(400, "No image data received")
                    return
                
                # Read the image data
                image_data = self.rfile.read(content_length)
                
                # Save to temp file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_path = os.path.join(tempfile.gettempdir(), f"clipboard_photo_{timestamp}.png")
                
                with open(temp_path, 'wb') as f:
                    f.write(image_data)
                
                # Copy to clipboard (cross-platform)
                success, error = copy_image_to_clipboard(temp_path)
                
                if success:
                    print(f"✅ Photo copied to clipboard! ({len(image_data)} bytes)")
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b"Photo copied to clipboard!")
                else:
                    print(f"❌ Clipboard error: {error}")
                    self.send_error(500, f"Clipboard error: {error}")
                    
            except Exception as e:
                print(f"❌ Clipboard error: {e}")
                self.send_error(500, str(e))
            return
        
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
        elif path == '/text':
            self.serve_synced_text()
        elif path.startswith('/download/'):
            filename = urllib.parse.unquote(path[10:])
            self.serve_file_download(filename)
        else:
            self.send_error(404)
    
    def serve_synced_text(self):
        """Serve the synced text."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'text': synced_text}).encode())
    
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
            
            # Encode filename for Content-Disposition header (RFC 5987 for Unicode support)
            try:
                # Try ASCII first
                filename.encode('ascii')
                content_disposition = f'attachment; filename="{filename}"'
            except UnicodeEncodeError:
                # Use RFC 5987 encoding for Unicode filenames
                encoded_filename = urllib.parse.quote(filename, safe='')
                content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
            
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Content-Disposition', content_disposition)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Filename')
            self.send_header('Access-Control-Expose-Headers', 'Content-Disposition, Content-Length')
            self.send_header('Cache-Control', 'no-cache')
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
    <title>Phone PC Sync</title>

    <!-- App Icon - Folder with Sync Badge -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' fill='%23fafafa'/%3E%3Cpath d='M15 25h25l5-8h35v8h0v45H15V25z' fill='%23222'/%3E%3Cpath d='M15 32h65v38H15z' fill='%23333'/%3E%3Ccircle cx='72' cy='62' r='18' fill='%232563eb'/%3E%3Cpath d='M72 52 L78 58 L72 58 L72 52 M66 66 L72 72 L72 66 L66 66' fill='white'/%3E%3Cpath d='M72 52 C79 52 84 57 84 64' stroke='white' stroke-width='3' fill='none'/%3E%3Cpath d='M72 72 C65 72 60 67 60 60' stroke='white' stroke-width='3' fill='none'/%3E%3C/svg%3E">
    <link rel="apple-touch-icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' fill='%23fff'/%3E%3Cpath d='M15 25h25l5-8h35v8h0v45H15V25z' fill='%23222'/%3E%3Cpath d='M15 32h65v38H15z' fill='%23333'/%3E%3Ccircle cx='72' cy='62' r='18' fill='%232563eb'/%3E%3Cpath d='M72 52 L78 58 L72 58 L72 52 M66 66 L72 72 L72 66 L66 66' fill='white'/%3E%3Cpath d='M72 52 C79 52 84 57 84 64' stroke='white' stroke-width='3' fill='none'/%3E%3Cpath d='M72 72 C65 72 60 67 60 60' stroke='white' stroke-width='3' fill='none'/%3E%3C/svg%3E">

    
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

        /* Text Sync Section */
        .text-sync-area {
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
            padding: 16px;
        }

        .text-sync-textarea {
            width: 100%;
            min-height: 120px;
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 12px;
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 14px;
            resize: vertical;
            outline: none;
            transition: border-color 0.2s;
        }

        .text-sync-textarea:focus {
            border-color: #2563eb;
        }

        .text-sync-textarea::placeholder {
            color: #aaa;
        }

        .text-sync-buttons {
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }

        .text-btn {
            flex: 1;
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #e0e0e0;
            background: #f5f5f5;
            color: #444;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.15s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }

        .text-btn:active {
            background: #e8e8e8;
        }

        .text-btn.primary {
            background: #222;
            color: white;
            border-color: #222;
        }

        .text-btn.primary:active {
            background: #444;
        }

        .text-btn.success {
            background: #22c55e;
            color: white;
            border-color: #22c55e;
        }

        .text-char-count {
            text-align: right;
            font-size: 11px;
            color: #aaa;
            margin-top: 8px;
        }

        /* Hint at bottom */
        .hint {
            margin-top: auto;
            padding-top: 30px;
            font-size: 11px;
            color: #bbb;
            text-align: center;
            line-height: 1.8;
        }

        /* Tab Navigation */
        .tab-nav {
            display: flex;
            gap: 0;
            margin-bottom: 25px;
            background: #f0f0f0;
            border-radius: 12px;
            padding: 4px;
        }

        .tab-btn {
            flex: 1;
            padding: 12px 8px;
            border: none;
            background: transparent;
            font-size: 13px;
            font-weight: 500;
            color: #666;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.15s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }

        .tab-btn.active {
            background: white;
            color: #222;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .tab-btn:active {
            transform: scale(0.98);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* Camera Section Styles */
        .camera-area {
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06);
            padding: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .preview-area {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            height: 30vh;
            margin-bottom: 20px;
        }

        #cameraPreview {
            max-width: 100%;
            max-height: 30vh;
            border-radius: 8px;
            display: none;
            box-shadow: 0 10px 40px rgba(0,0,0,0.12);
            object-fit: contain;
            transition: transform 0.2s ease;
        }

        .camera-placeholder {
            color: #ccc;
            font-size: 13px;
            letter-spacing: 1px;
        }

        .camera-controls {
            display: none;
            gap: 12px;
            margin-bottom: 20px;
        }

        .rotate-btn, .crop-btn, .camera-send-btn {
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            font-family: inherit;
            transition: all 0.15s;
        }

        .rotate-btn, .crop-btn {
            background: #f0f0f0;
            border: 1px solid #ddd;
            color: #333;
        }

        .rotate-btn:active, .crop-btn:active {
            background: #e0e0e0;
        }

        .camera-send-btn {
            background: #222;
            border: none;
            color: white;
        }

        .camera-send-btn:active {
            background: #444;
        }

        #cameraStatus {
            height: 24px;
            font-size: 13px;
            color: #888;
            margin-bottom: 20px;
        }

        #cameraStatus.success { color: #22c55e; }
        #cameraStatus.error { color: #ef4444; }

        .shutter-wrap {
            position: relative;
            width: 80px;
            height: 80px;
        }

        .shutter {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            border: 4px solid #222;
            background: white;
            cursor: pointer;
            position: relative;
            transition: transform 0.1s;
        }

        .shutter::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: #222;
            transition: all 0.15s;
        }

        .shutter:active {
            transform: scale(0.92);
        }

        .shutter:active::after {
            width: 48px;
            height: 48px;
            background: #444;
        }

        .shutter.flash::after {
            background: #22c55e;
        }

        .gallery-link {
            margin-top: 20px;
            font-size: 13px;
            color: #888;
            text-decoration: underline;
            cursor: pointer;
            background: none;
            border: none;
            font-family: inherit;
        }

        .camera-hint {
            margin-top: 30px;
            font-size: 11px;
            color: #bbb;
            text-align: center;
            line-height: 1.8;
        }

        /* Crop Overlay */
        #cropOverlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.95);
            z-index: 1000;
            display: none;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .crop-container {
            position: relative;
            max-width: 90%;
            max-height: 60vh;
        }

        #cropImage {
            max-width: 100%;
            max-height: 60vh;
            display: block;
        }

        .crop-box {
            position: absolute;
            border: 2px solid #fff;
            box-shadow: 0 0 0 9999px rgba(0,0,0,0.5);
            cursor: move;
            touch-action: none;
        }

        .resize-handle {
            position: absolute;
            bottom: -8px;
            right: -8px;
            width: 24px;
            height: 24px;
            background: #fff;
            border-radius: 50%;
            cursor: nwse-resize;
            touch-action: none;
        }

        .crop-actions {
            display: flex;
            gap: 12px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="app">

        <!-- Tab Navigation (mobile only) -->
        <div class="tab-nav" id="tabNav" style="display: none;">
            <button class="tab-btn active" data-tab="files">📁 Files</button>
            <button class="tab-btn" data-tab="camera">📸 Camera</button>
            <button class="tab-btn" data-tab="text">📝 Text</button>
        </div>

        <!-- Files Tab Content -->
        <div class="tab-content active" id="filesTab">
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
        </div>

        <!-- Camera Tab Content -->
        <div class="tab-content" id="cameraTab">
            <div class="camera-area">
                <div class="preview-area">
                    <img id="cameraPreview">
                    <span class="camera-placeholder" id="cameraPlaceholder">Your photo will appear here</span>
                </div>

                <div class="camera-controls" id="cameraControls">
                    <button class="rotate-btn" id="rotateBtn">↻</button>
                    <button class="crop-btn" id="cropBtn">✂ Crop</button>
                    <button class="camera-send-btn" id="cameraSendBtn">Send to Clipboard</button>
                </div>

                <div id="cameraStatus"></div>

                <input type="file" id="cameraInput" accept="image/*" capture>
                <input type="file" id="galleryInput" accept="image/*">

                <div class="shutter-wrap">
                    <button class="shutter" id="shutterBtn" aria-label="Take photo"></button>
                </div>

                <button class="gallery-link" id="galleryBtn">or choose from gallery</button>

                <div class="camera-hint">
                    Take a photo → Paste on your computer<br>
                    <strong>Ctrl+V</strong> (Windows/Linux) or <strong>Cmd+V</strong> (Mac)
                </div>
            </div>
        </div>

        <!-- Crop Overlay -->
        <div id="cropOverlay">
            <div class="crop-container" id="cropContainer">
                <img id="cropImage">
                <div class="crop-box" id="cropBox">
                    <div class="resize-handle" id="resizeHandle"></div>
                </div>
            </div>
            <div class="crop-actions">
                <button class="rotate-btn" id="cropCancel">Cancel</button>
                <button class="camera-send-btn" id="cropApply">Apply Crop</button>
            </div>
        </div>

        <!-- Text Tab Content -->
        <div class="tab-content" id="textTab">
            <div class="section">
                <div class="section-title">Text Sync</div>
                <div class="text-sync-area">
                    <textarea class="text-sync-textarea" id="syncTextarea" placeholder="Type or paste text here to sync between devices..."></textarea>
                    <div class="text-char-count"><span id="charCount">0</span> characters</div>
                    <div class="text-sync-buttons">
                        <button class="text-btn primary" id="syncTextBtn">🔄 Sync</button>
                    </div>
                </div>
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

            const uploadSectionTitle = document.getElementById('uploadSectionTitle');
            const downloadSectionTitle = document.getElementById('downloadSectionTitle');
            const hintText = document.getElementById('hintText');
            const downloadSection = document.getElementById('downloadSection');

            if (isDesktop) {
                // Desktop: Hide downloads section
                uploadSectionTitle.textContent = 'Send to Phone';
                downloadSection.style.display = 'none';
                hintText.innerHTML = 'Pick files here → Download them on your phone<br>Or open this URL on your phone to send files to your PC';
                
                // Show Text Sync section on Desktop
                document.getElementById('textTab').style.display = 'block';
            } else {
                // Mobile: Show both sections
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
            const target = !isDesktop ? 'PC' : 'Phone';
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
                    item.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const filename = decodeURIComponent(item.dataset.filename);
                        downloadFile(filename);
                        return false;
                    };
                });

            } catch (e) {
                macFilesEl.innerHTML = '<div class="empty-state">Could not load files</div>';
            }
        }

        let isDownloading = false;
        function downloadFile(filename) {
            // Prevent duplicate downloads
            if (isDownloading) return;
            isDownloading = true;
            
            // Direct download - the server handles Unicode filenames properly
            const link = document.createElement('a');
            link.href = `/download/${encodeURIComponent(filename)}`;
            link.download = filename;
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            // Reset after 2 seconds to allow new downloads
            setTimeout(() => { isDownloading = false; }, 2000);
        }

        // ========== TEXT SYNC FUNCTIONALITY ==========
        const syncTextarea = document.getElementById('syncTextarea');
        const charCount = document.getElementById('charCount');
        const syncTextBtn = document.getElementById('syncTextBtn');

        // Update character count
        syncTextarea.addEventListener('input', () => {
            charCount.textContent = syncTextarea.value.length;
        });

        // Sync text to server
        syncTextBtn.onclick = async () => {
            const originalText = syncTextBtn.innerHTML;
            syncTextBtn.disabled = true;
            syncTextBtn.innerHTML = '<span class="spinner"></span>Syncing...';

            try {
                const res = await fetch('/text', {
                    method: 'POST',
                    body: syncTextarea.value,
                    headers: { 'Content-Type': 'text/plain' }
                });

                if (res.ok) {
                    syncTextBtn.classList.add('success');
                    syncTextBtn.textContent = '✓ Synced!';
                    showStatus('Text synced successfully', 'success');
                    if (navigator.vibrate) navigator.vibrate(50);
                    
                    setTimeout(() => {
                        syncTextBtn.classList.remove('success');
                        syncTextBtn.innerHTML = originalText;
                    }, 1500);
                } else {
                    throw new Error('Sync failed');
                }
            } catch (e) {
                showStatus('Failed to sync text', 'error');
                syncTextBtn.innerHTML = originalText;
            }
            
            syncTextBtn.disabled = false;
        };

        // Load synced text from server
        async function loadSyncedText() {
            try {
                const res = await fetch('/text');
                const data = await res.json();
                if (data.text) {
                    syncTextarea.value = data.text;
                    charCount.textContent = data.text.length;
                }
            } catch (e) {
                console.log('Could not load synced text');
            }
        }

        // ========== TAB NAVIGATION ==========
        const tabNav = document.getElementById('tabNav');
        const tabBtns = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        function switchTab(tabId) {
            tabBtns.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.tab === tabId);
            });
            tabContents.forEach(content => {
                content.classList.toggle('active', content.id === tabId + 'Tab');
            });
        }

        tabBtns.forEach(btn => {
            btn.onclick = () => switchTab(btn.dataset.tab);
        });

        // ========== CAMERA FUNCTIONALITY ==========
        const cameraInput = document.getElementById('cameraInput');
        const galleryInput = document.getElementById('galleryInput');
        const cameraPreview = document.getElementById('cameraPreview');
        const cameraPlaceholder = document.getElementById('cameraPlaceholder');
        const cameraControls = document.getElementById('cameraControls');
        const cameraStatus = document.getElementById('cameraStatus');
        const shutterBtn = document.getElementById('shutterBtn');
        const galleryBtn = document.getElementById('galleryBtn');
        const rotateBtn = document.getElementById('rotateBtn');
        const cropBtn = document.getElementById('cropBtn');
        const cameraSendBtn = document.getElementById('cameraSendBtn');
        
        // Crop elements
        const cropOverlay = document.getElementById('cropOverlay');
        const cropImage = document.getElementById('cropImage');
        const cropBox = document.getElementById('cropBox');
        const cropCancel = document.getElementById('cropCancel');
        const cropApply = document.getElementById('cropApply');
        const resizeHandle = document.getElementById('resizeHandle');
        
        let currentCameraFile = null;
        let rotation = 0;
        let previewUrl = null;

        shutterBtn.onclick = () => cameraInput.click();
        galleryBtn.onclick = () => galleryInput.click();

        function cleanupCamera() {
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
                previewUrl = null;
            }
        }

        function resetCameraUI() {
            cleanupCamera();
            currentCameraFile = null;
            rotation = 0;
            cameraPreview.style.display = 'none';
            cameraPreview.style.transform = 'rotate(0deg)';
            cameraPreview.src = '';
            cameraPlaceholder.style.display = 'block';
            cameraControls.style.display = 'none';
        }

        function loadCameraImage(file) {
            if (!file) return;
            
            cleanupCamera();
            currentCameraFile = file;
            rotation = 0;
            
            previewUrl = URL.createObjectURL(file);
            cameraPreview.src = previewUrl;
            cameraPreview.style.display = 'block';
            cameraPreview.style.transform = 'rotate(0deg)';
            cameraPlaceholder.style.display = 'none';
            cameraControls.style.display = 'flex';
            cameraStatus.textContent = '';
            cameraStatus.className = '';
        }

        rotateBtn.onclick = () => {
            rotation = (rotation + 90) % 360;
            cameraPreview.style.transform = `rotate(${rotation}deg)`;
        };

        // Crop functionality
        cropBtn.onclick = () => {
            if (!currentCameraFile) return;
            cropImage.src = previewUrl;
            cropOverlay.style.display = 'flex';
            
            cropImage.onload = () => {
                const rect = cropImage.getBoundingClientRect();
                const size = Math.min(rect.width, rect.height) * 0.8;
                cropBox.style.width = size + 'px';
                cropBox.style.height = size + 'px';
                cropBox.style.left = ((rect.width - size) / 2) + 'px';
                cropBox.style.top = ((rect.height - size) / 2) + 'px';
            };
        };

        cropCancel.onclick = () => {
            cropOverlay.style.display = 'none';
        };

        cropApply.onclick = async () => {
            const imgRect = cropImage.getBoundingClientRect();
            const boxRect = cropBox.getBoundingClientRect();
            
            const scaleX = cropImage.naturalWidth / imgRect.width;
            const scaleY = cropImage.naturalHeight / imgRect.height;
            
            const cropData = {
                x: (boxRect.left - imgRect.left) * scaleX,
                y: (boxRect.top - imgRect.top) * scaleY,
                width: boxRect.width * scaleX,
                height: boxRect.height * scaleY
            };
            
            currentCameraFile = await applyCrop(currentCameraFile, cropData);
            
            cleanupCamera();
            previewUrl = URL.createObjectURL(currentCameraFile);
            cameraPreview.src = previewUrl;
            cameraPreview.style.transform = 'rotate(0deg)';
            rotation = 0;
            
            cropOverlay.style.display = 'none';
        };

        // Crop box drag and resize
        let isDragging = false;
        let isResizing = false;
        let startX, startY, startLeft, startTop, startW, startH;

        resizeHandle.addEventListener('touchstart', (e) => {
            isResizing = true;
            const touch = e.touches[0];
            startX = touch.clientX;
            startY = touch.clientY;
            startW = cropBox.offsetWidth;
            startH = cropBox.offsetHeight;
            e.preventDefault();
            e.stopPropagation();
        });

        cropBox.addEventListener('touchstart', (e) => {
            if (isResizing) return;
            isDragging = true;
            const touch = e.touches[0];
            startX = touch.clientX;
            startY = touch.clientY;
            startLeft = cropBox.offsetLeft;
            startTop = cropBox.offsetTop;
            e.preventDefault();
        });

        document.addEventListener('touchmove', (e) => {
            if (!isDragging && !isResizing) return;
            const touch = e.touches[0];
            const imgRect = cropImage.getBoundingClientRect();
            
            if (isResizing) {
                const dx = touch.clientX - startX;
                const dy = touch.clientY - startY;
                let newW = Math.max(50, startW + dx);
                let newH = Math.max(50, startH + dy);
                newW = Math.min(newW, imgRect.width - cropBox.offsetLeft);
                newH = Math.min(newH, imgRect.height - cropBox.offsetTop);
                cropBox.style.width = newW + 'px';
                cropBox.style.height = newH + 'px';
            } else if (isDragging) {
                const dx = touch.clientX - startX;
                const dy = touch.clientY - startY;
                const boxW = cropBox.offsetWidth;
                const boxH = cropBox.offsetHeight;
                let newLeft = Math.max(0, Math.min(imgRect.width - boxW, startLeft + dx));
                let newTop = Math.max(0, Math.min(imgRect.height - boxH, startTop + dy));
                cropBox.style.left = newLeft + 'px';
                cropBox.style.top = newTop + 'px';
            }
        });

        document.addEventListener('touchend', () => {
            isDragging = false;
            isResizing = false;
        });

        async function applyCrop(file, crop) {
            return new Promise((resolve) => {
                const img = new Image();
                const url = URL.createObjectURL(file);
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    canvas.width = crop.width;
                    canvas.height = crop.height;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, crop.x, crop.y, crop.width, crop.height, 0, 0, crop.width, crop.height);
                    canvas.toBlob((blob) => {
                        URL.revokeObjectURL(url);
                        resolve(blob);
                    }, 'image/png');
                };
                img.src = url;
            });
        }

        async function rotateImage(file, degrees) {
            return new Promise((resolve, reject) => {
                const img = new Image();
                const url = URL.createObjectURL(file);
                
                img.onload = () => {
                    try {
                        const canvas = document.createElement('canvas');
                        const ctx = canvas.getContext('2d');
                        
                        if (degrees === 90 || degrees === 270) {
                            canvas.width = img.height;
                            canvas.height = img.width;
                        } else {
                            canvas.width = img.width;
                            canvas.height = img.height;
                        }
                        
                        ctx.translate(canvas.width / 2, canvas.height / 2);
                        ctx.rotate(degrees * Math.PI / 180);
                        ctx.drawImage(img, -img.width / 2, -img.height / 2);
                        
                        canvas.toBlob((blob) => {
                            URL.revokeObjectURL(url);
                            resolve(blob);
                        }, 'image/png');
                    } catch (e) {
                        URL.revokeObjectURL(url);
                        reject(e);
                    }
                };
                
                img.onerror = () => {
                    URL.revokeObjectURL(url);
                    reject(new Error('Failed to load image'));
                };
                
                img.src = url;
            });
        }

        cameraSendBtn.onclick = async () => {
            if (!currentCameraFile) return;
            
            cameraSendBtn.disabled = true;
            cameraStatus.textContent = 'Sending...';
            cameraStatus.className = 'loading';
            
            try {
                let blob = currentCameraFile;
                
                if (rotation !== 0) {
                    blob = await rotateImage(currentCameraFile, rotation);
                }
                
                const res = await fetch('/clipboard', {
                    method: 'POST',
                    body: blob,
                    headers: { 'Content-Type': 'image/png' }
                });
                
                if (res.ok) {
                    cameraStatus.textContent = '✓ Copied to clipboard!';
                    cameraStatus.className = 'success';
                    shutterBtn.classList.add('flash');
                    setTimeout(() => shutterBtn.classList.remove('flash'), 300);
                    if (navigator.vibrate) navigator.vibrate(50);
                    cameraControls.style.display = 'none';
                    currentCameraFile = null;
                } else {
                    cameraStatus.textContent = 'Failed - tap to retry';
                    cameraStatus.className = 'error';
                }
            } catch (e) {
                cameraStatus.textContent = 'No connection';
                cameraStatus.className = 'error';
            } finally {
                cameraSendBtn.disabled = false;
            }
        };

        cameraInput.onchange = (e) => { loadCameraImage(e.target.files[0]); e.target.value = ''; };
        galleryInput.onchange = (e) => { loadCameraImage(e.target.files[0]); e.target.value = ''; };

        // ========== UPDATED INITIALIZATION ==========
        function initApp() {
            updateUIForDevice();
            loadMacFiles();
            loadSyncedText();
            
            // Show tabs on mobile only
            if (!isDesktop) {
                tabNav.style.display = 'flex';
            }
        }

        // Initialize
        initApp();
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
    print("📱 Phone PC Sync")
    print("="*50)
    print(f"\n🌐 Server running at: http://{local_ip}:{PORT}")
    print(f"\n📱 Open this URL on your phone's browser")
    print(f"📂 Files will be saved to: {DOWNLOADS_FOLDER}")
    print(f"📸 Camera photos will be copied to clipboard")
    print("\n" + "="*50)
    print("Waiting for connections...\n")

    server = http.server.HTTPServer(('0.0.0.0', PORT), FileTransferHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
