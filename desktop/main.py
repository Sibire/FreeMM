"""DIYgitizer Desktop App — entry point."""

import sys
import os

# Ensure app package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DIYgitizer")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
