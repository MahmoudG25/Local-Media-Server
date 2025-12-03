from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFileDialog, QMessageBox,
    QDialog, QListWidget, QDialogButtonBox, QFormLayout
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont

from config import AppConfig
from server import ServerThread, ServerSignals

class UploadDialog(QDialog):
    """Dialog to approve or reject uploaded files."""
    
    def __init__(self, upload_info: dict, config: AppConfig, parent=None):
        super().__init__(parent)
        self.upload_info = upload_info
        self.config = config
        self.approved = False
        
        self.setWindowTitle("New Upload Request")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("New Upload Request")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Info
        form = QFormLayout()
        form.addRow("From:", QLabel(self.upload_info.get("client_ip", "Unknown")))
        form.addRow("Folder:", QLabel(self.upload_info.get("target_folder", "/")))
        form.addRow("Time:", QLabel(self.upload_info.get("time", "")))
        layout.addLayout(form)
        
        # Files list
        layout.addWidget(QLabel("Files:"))
        self.file_list = QListWidget()
        for name in self.upload_info.get("display_names", []):
            self.file_list.addItem(name)
        layout.addWidget(self.file_list)
        
        # Buttons
        button_box = QDialogButtonBox()
        
        approve_btn = QPushButton("Approve")
        approve_btn.setStyleSheet("background-color: #22c55e; color: white; padding: 8px 20px;")
        approve_btn.clicked.connect(self.on_approve)
        
        reject_btn = QPushButton("Reject")
        reject_btn.setStyleSheet("background-color: #ef4444; color: white; padding: 8px 20px;")
        reject_btn.clicked.connect(self.on_reject)
        
        button_box.addButton(approve_btn, QDialogButtonBox.AcceptRole)
        button_box.addButton(reject_btn, QDialogButtonBox.RejectRole)
        
        layout.addWidget(button_box)
    
    def on_approve(self):
        """Approve all uploaded files."""
        pending_root = self.config.get_pending_dir()
        
        for rel_path_str in self.upload_info.get("pending_relpaths", []):
            pending_path = (pending_root / rel_path_str).resolve()
            if not pending_path.exists():
                continue
            
            rel_inside = pending_path.relative_to(pending_root)
            dest = self.config.base_dir / rel_inside
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Handle file name conflicts
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                counter = 1
                while dest.exists():
                    dest = dest.parent / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            pending_path.replace(dest)
        
        QMessageBox.information(self, "Success", "Files approved and moved to main folder.")
        self.approved = True
        self.accept()
    
    def on_reject(self):
        """Reject and delete all uploaded files."""
        reply = QMessageBox.question(
            self, "Confirm Rejection",
            "Are you sure you want to reject and delete these files?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            pending_root = self.config.get_pending_dir()
            
            for rel_path_str in self.upload_info.get("pending_relpaths", []):
                pending_path = (pending_root / rel_path_str).resolve()
                if pending_path.exists() and pending_path.is_file():
                    pending_path.unlink()
            
            QMessageBox.information(self, "Rejected", "Files were rejected and deleted.")
            self.reject()


class MainWindow(QMainWindow):
    """Main window for the Local Media Server GUI."""
    
    def __init__(self):
        super().__init__()
        self.server_thread: Optional[ServerThread] = None
        self.signals = ServerSignals()
        self.config: Optional[AppConfig] = None
        
        self.setWindowTitle("Local Media Server")
        self.setMinimumSize(600, 350)
        
        self.init_ui()
        
        # Connect signal for upload requests
        self.signals.upload_request.connect(self.on_upload_request)
    
    def init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Folder selection
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel("Folder Path:"))
        self.folder_input = QLineEdit()
        self.folder_input.setText(str(Path(__file__).parent / "files"))
        folder_layout.addWidget(self.folder_input)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.browse_btn)
        layout.addLayout(folder_layout)
        
        # Host
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Host / IP:"))
        self.host_input = QLineEdit("0.0.0.0")
        self.host_input.setMaximumWidth(200)
        host_layout.addWidget(self.host_input)
        host_layout.addStretch()
        layout.addLayout(host_layout)
        
        # Port
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.port_input = QLineEdit("4142")
        self.port_input.setMaximumWidth(100)
        port_layout.addWidget(self.port_input)
        port_layout.addStretch()
        layout.addLayout(port_layout)
        
        # Password
        password_layout = QHBoxLayout()
        password_layout.addWidget(QLabel("Password (Basic Auth):"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMaximumWidth(200)
        password_layout.addWidget(self.password_input)
        password_layout.addStretch()
        layout.addLayout(password_layout)
        
        # Hint
        hint = QLabel("If you set a password: username = user\nIf left empty: no password required.")
        hint.setStyleSheet("color: gray; font-size: 10pt;")
        layout.addWidget(hint)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Server")
        self.start_btn.setStyleSheet("background-color: #22c55e; color: white; padding: 10px; font-size: 11pt;")
        self.start_btn.clicked.connect(self.start_server)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Server")
        self.stop_btn.setStyleSheet("background-color: #ef4444; color: white; padding: 10px; font-size: 11pt;")
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        layout.addLayout(button_layout)
        
        # Status
        self.status_label = QLabel("Server status: stopped")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # URL
        self.url_label = QLabel("")
        self.url_label.setStyleSheet("color: green;")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.url_label)
        
        layout.addStretch()
    
    def browse_folder(self):
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)
    
    def start_server(self):
        """Start the Flask server."""
        if self.server_thread and self.server_thread.isRunning():
            QMessageBox.information(self, "Info", "Server is already running.")
            return
        
        folder = self.folder_input.text().strip()
        host = self.host_input.text().strip()
        port_str = self.port_input.text().strip()
        password = self.password_input.text()
        
        if not folder:
            QMessageBox.critical(self, "Error", "Please select a folder first.")
            return
        
        try:
            port = int(port_str)
        except ValueError:
            QMessageBox.critical(self, "Error", "Port must be a valid number.")
            return
        
        base_dir = Path(folder)
        if not base_dir.exists() or not base_dir.is_dir():
            QMessageBox.critical(self, "Error", "Invalid folder path.")
            return
        
        # Create config
        self.config = AppConfig(
            base_dir=base_dir,
            host=host or "0.0.0.0",
            port=port,
            password=password or ""
        )
        
        # Create directories
        base_dir.mkdir(exist_ok=True)
        self.config.get_pending_dir().mkdir(exist_ok=True)
        
        # Start server thread
        self.server_thread = ServerThread(self.config, self.signals)
        self.server_thread.start()
        
        self.status_label.setText("Server status: running")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        
        # Get local IP for better display
        local_ip = self.get_local_ip()
        display_host = local_ip if host == "0.0.0.0" else host
        url_display = f"http://{display_host}:{port}"
        self.url_label.setText(f"Open in browser: {url_display}")
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
    
    def stop_server(self):
        """Stop the Flask server."""
        if not self.server_thread or not self.server_thread.isRunning():
            QMessageBox.information(self, "Info", "Server is already stopped.")
            return
        
        self.status_label.setText("Server status: stopping...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        
        self.server_thread.stop()
        self.server_thread.wait()
        
        self.status_label.setText("Server status: stopped")
        self.status_label.setStyleSheet("color: blue; font-weight: bold;")
        self.url_label.setText("")
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def get_local_ip(self) -> str:
        """Get the local IP address of this machine."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    @Slot(dict)
    def on_upload_request(self, upload_info: dict):
        """Handle upload request signal from server."""
        if not self.config:
            return
        
        dialog = UploadDialog(upload_info, self.config, self)
        dialog.exec()
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.server_thread and self.server_thread.isRunning():
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "Server is still running. Do you want to stop it and exit?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.server_thread.stop()
                self.server_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
