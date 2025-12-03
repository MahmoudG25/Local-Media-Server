# 🎬 Local Media Server

<div align="center">

**A modern, beautiful media streaming server with PySide6 GUI**

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![PySide6](https://img.shields.io/badge/PySide6-6.0-purple.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

Stream your local media files with a premium, Netflix-style web interface

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Screenshots](#-screenshots) • [Tech Stack](#-tech-stack)

</div>

---

## ✨ Features

### 🎨 **Modern Web Interface**
- **Premium UI** - Netflix/Plex-inspired design with smooth animations
- **Glass Morphism** - Frosted glass effects and backdrop blur
- **Dark/Light Themes** - Seamless theme switching with localStorage persistence
- **Responsive Design** - Perfect on mobile, tablet, and desktop (1-5 column grid)

### 🎬 **Media Playback**
- **Video Streaming** - HTML5 video player with range request support
- **Image Viewer** - Modal lightbox with keyboard navigation
- **Wake Lock API** - Prevents screen sleep during video playback
- **Auto-detection** - Automatic file type recognition

### 🔐 **Security & Control**
- **Password Protection** - Optional authentication for web access
- **Upload Approval** - Admin approval system for uploaded files
- **Path Security** - Protection against path traversal attacks
- **Admin Panel** - Dedicated GUI for server management

### 🖥️ **Desktop GUI (PySide6)**
- **Modern Interface** - Clean Qt Widgets UI
- **Server Control** - Start/stop server with live status
- **Upload Management** - Approve/reject file uploads
- **Configuration** - Easy host, port, and password settings
- **System Tray** - Background operation support

### 📁 **File Management**
- **Browse Folders** - Navigate directory structure
- **Search & Filter** - Find files by name, type, size, or date
- **Multiple Formats** - Videos, images, audio, documents
- **Batch Upload** - Multiple file upload support
- **File Operations** - Download, stream, delete (admin only)

---

## 🚀 Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Local-Media-Server.git
   cd Local-Media-Server
   ```

2. **Create virtual environment** (recommended)
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

---

## 📖 Usage

### Starting the Server

#### Option 1: GUI Application (Recommended)
```bash
python main.py
```
- Select your media folder
- Configure host (default: `0.0.0.0`) and port (default: `5000`)
- Set optional password
- Click "Start Server"
- Access via the displayed URL

#### Option 2: Command Line (Future)
```bash
python -m server --host 0.0.0.0 --port 5000
```

### Accessing the Web Interface

1. **Local Access**: `http://localhost:5000`
2. **Network Access**: `http://YOUR_IP:5000`
3. **With Password**: Enter credentials when prompted

### Using the Interface

**Browse Files**
- Click folders to navigate
- Use breadcrumbs to go back
- Search by filename

**Play Media**
- Click "Play" on videos → Opens fullscreen player
- Click "View" on images → Opens lightbox viewer
- Use arrow keys to navigate images

**Upload Files**
- Click "Choose Files" in upload card
- Select one or multiple files
- Files go to `_pending_uploads` folder
- Admin approves/rejects via GUI

**Filters**
- Type: All, Video, Image, Audio, Other
- Sort: Name, Size, Date
- Order: Ascending/Descending

---

## 📸 Screenshots

### Main Interface (Dark Theme)
Beautiful card-based layout with gradient accents and smooth shadows.

### Video Player
Fullscreen HTML5 player with custom controls and wake lock support.

### Image Lightbox
Modal viewer with navigation and file information.

### Admin GUI
PySide6 desktop application for server management.

---

## 🛠️ Tech Stack

### Backend
- **Flask** - Web framework
- **Werkzeug** - WSGI utilities
- **Python** - Core language

### Frontend
- **HTML5** - Semantic markup
- **CSS3** - Modern styling with variables
- **Vanilla JavaScript** - No framework dependencies
- **Inter Font** - Professional typography

### Desktop GUI
- **PySide6** - Qt for Python
- **Qt Widgets** - Native UI components
- **QThread** - Background server operation

### Features
- **Screen Wake Lock API** - Prevents sleep during playback
- **Local Storage** - Theme persistence
- **Responsive Grid** - CSS Grid & Flexbox
- **Glass Morphism** - Backdrop blur effects

---

## 📁 Project Structure

```
Local-Media-Server/
├── main.py                 # Application entry point
├── server.py              # Flask server & threading
├── gui.py                 # PySide6 GUI
├── config.py              # Configuration dataclass
├── utils.py               # File utilities & security
├── requirements.txt       # Python dependencies
├── templates/
│   ├── index.html        # Main file browser
│   └── player.html       # Video player page
├── static/
│   ├── css/
│   │   └── main.css      # Complete styling
│   └── js/
│       ├── theme.js      # Theme switcher
│       └── app.js        # Image viewer & wake lock
└── files/                # Media files directory
    └── _pending_uploads/ # Pending approval
```

---

## 🎨 Customization

### Change Port
Edit in GUI or modify `config.py`:
```python
default_port = 5000
```

### Modify Colors
Edit CSS variables in `static/css/main.css`:
```css
:root {
  --color-primary: #6366f1;
  --color-secondary: #8b5cf6;
}
```

### Add File Types
Extend `utils.py` file type detection:
```python
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov'}
IMAGE_EXTENSIONS = {'.jpg', '.png', '.gif', '.webp'}
```

---

## 🔒 Security Features

- ✅ **Path Traversal Protection** - Validates all file paths
- ✅ **Base Directory Restriction** - Can't access files outside media folder
- ✅ **Optional Password Auth** - HTTP Basic Authentication
- ✅ **Upload Approval System** - Admin reviews all uploads
- ✅ **Secure Defaults** - Safe configuration out of the box

---

## 🌐 Network Access

### Allow Network Access
1. Set host to `0.0.0.0` (default)
2. Configure firewall to allow port `5000`
3. Find your local IP:
   ```bash
   # Windows
   ipconfig
   
   # macOS/Linux
   ifconfig
   ```
4. Access from other devices: `http://YOUR_IP:5000`

### Use with Dynamic DNS
For external access, configure DDNS and port forwarding on your router.

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# macOS/Linux
lsof -i :5000
kill -9 <PID>
```

### CSS Not Loading
- Hard refresh: `Ctrl+F5` (Windows) or `Cmd+Shift+R` (Mac)
- Clear browser cache
- Check browser console for errors

### Upload Not Working
- Check file permissions
- Ensure `_pending_uploads` folder exists
- Verify admin authentication

### Video Won't Play
- Check video codec (H.264 recommended)
- Try different browser
- Check file permissions

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 🙏 Acknowledgments

- **Flask** - Excellent web framework
- **PySide6** - Powerful Qt bindings
- **Inter Font** - Beautiful typography
- **Bootstrap Icons** - UI icons (optional)

---

## 📬 Contact

**Project Link**: [https://github.com/yourusername/Local-Media-Server](https://github.com/yourusername/Local-Media-Server)

**Issues**: [https://github.com/yourusername/Local-Media-Server/issues](https://github.com/yourusername/Local-Media-Server/issues)

---

<div align="center">

**Made with ❤️ for media enthusiasts**

⭐ Star this repo if you find it useful!

</div>
