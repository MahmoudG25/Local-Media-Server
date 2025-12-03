# Local Media Server

A modern, lightweight local media server with a Flask backend and PySide6 GUI for streaming, uploading, and managing media files.

## Features

- **Browse & Stream**: Browse folders, stream videos, view images, download files
- **Upload with Approval**: Files are uploaded to a pending folder and require admin approval
- **Basic Authentication**: Optional password protection for the web interface
- **Desktop GUI**: Modern PySide6 interface to control the server
- **Range Requests**: Support for video seeking and partial content delivery
- **Security**: Path traversal protection and base directory enforcement

## Installation

1. **Install Python 3.8+** (if not already installed)

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. **Start the GUI**:
   ```bash
   python main.py
   ```

2. **Configure**:
   - Select a folder to serve (or use the default `files` folder)
   - Set host (default: `0.0.0.0` for all interfaces)
   - Set port (default: `4142`)
   - Optionally set a password for authentication

3. **Start Server**: Click "Start Server"

4. **Access**: Open the displayed URL in your browser (e.g., `http://192.168.1.100:4142`)

## Project Structure

```
Local-Media-Server/
├── config.py          # Configuration dataclass
├── utils.py           # File utilities and security checks
├── server.py          # Flask server and routes
├── gui.py             # PySide6 GUI (MainWindow, UploadDialog)
├── main.py            # Application entry point
├── requirements.txt   # Python dependencies
├── templates/         # HTML templates for web interface
│   ├── index.html
│   └── player.html
└── static/            # CSS and JS for web interface
    ├── css/
    │   └── main.css
    └── js/
        └── theme.js
```

## Architecture

### Modular Design

- **`config.py`**: Holds application configuration in a dataclass
- **`utils.py`**: File system utilities, security validation, and helpers
- **`server.py`**: Flask application factory, routes, and server thread
- **`gui.py`**: PySide6 GUI with signals for thread-safe communication
- **`main.py`**: Entry point that initializes Qt and starts the application

### Thread-Safe Communication

The Flask server runs in a `QThread` to avoid blocking the GUI. When files are uploaded:
1. Flask route receives the upload
2. Saves files to the pending directory
3. Emits a Qt Signal (`upload_request`)
4. GUI receives the signal in the main thread
5. Opens an `UploadDialog` for the admin to approve/reject

### Security

- All file paths are validated to prevent directory traversal (`..`)
- Files must stay within the configured `base_dir`
- Pending uploads are isolated in `_pending_uploads/`
- Admin-only operations (delete, approve/reject) check if the request is from localhost

## Usage

### Web Interface

- **Browse**: Navigate folders and files
- **Filter**: Search by name, filter by type (video/image/audio/other)
- **Sort**: By name, size, or date
- **Play**: Stream videos in the browser
- **Download**: Download any file
- **Upload**: Upload files (requires admin approval)

### Admin Features (Localhost Only)

- **Approve/Reject Uploads**: Pending uploads appear in a notification section
- **Delete Files**: Delete files from the library

### GUI

- **Start/Stop Server**: Control server lifecycle
- **Status Display**: Real-time server status
- **Upload Notifications**: Popup dialog when files are uploaded
- **Clean Shutdown**: Warns if server is running when closing

## Development

### Adding New Routes

Edit `server.py` and add routes inside the `create_app()` method.

### Customizing the GUI

Edit `gui.py` to modify the MainWindow or UploadDialog appearance and behavior.

### Running Without GUI

You can import `ServerThread` and run it programmatically:

```python
from config import AppConfig
from server import ServerThread, ServerSignals
from pathlib import Path

config = AppConfig(base_dir=Path("files"), host="0.0.0.0", port=4142)
signals = ServerSignals()
thread = ServerThread(config, signals)
thread.start()
```

## Dependencies

- **Flask**: Web framework
- **Werkzeug**: WSGI utilities (comes with Flask)
- **PySide6**: Qt bindings for Python (GUI)

## License

This project is provided as-is for personal use.
