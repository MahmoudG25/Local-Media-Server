import sys
from PySide6.QtWidgets import QApplication
from gui import MainWindow

def main():
    """Entry point for the Local Media Server application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Local Media Server")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
