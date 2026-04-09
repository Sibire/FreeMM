#!/usr/bin/env python3
"""DIYgitizer Desktop App — entry point.

Usage:
    python run.py
"""

import sys
import os

# Ensure the desktop directory is on the path so 'diygitizer' package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_missing = []


def _check(module_name, pip_name=None):
    """Try to import a module; record it if missing."""
    try:
        __import__(module_name)
    except ImportError:
        _missing.append(pip_name or module_name)


# Check required dependencies before doing anything else
_check("PyQt5", "PyQt5")
_check("numpy", "numpy")
_check("serial", "pyserial")

if _missing:
    print("=" * 60)
    print("DIYgitizer — missing required packages:")
    for pkg in _missing:
        print(f"  - {pkg}")
    print()
    print("Install them with:")
    print(f"  pip install {' '.join(_missing)}")
    print()
    print("Or install everything at once:")
    print("  pip install -r requirements.txt")
    print("=" * 60)
    sys.exit(1)


def main():
    from PyQt5.QtWidgets import QApplication
    from diygitizer.app import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("DIYgitizer")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
