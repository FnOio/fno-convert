import sys
from PyQt6.QtWidgets import QApplication
from fno_convert.visualize import PY2RDFWindow

def main():
    app = QApplication(sys.argv)  # Create the application instance
    window = PY2RDFWindow()       # Create the main window
    window.show()                 # Show the window
    sys.exit(app.exec())          # Start the event loop

if __name__ == "__main__":
    main()