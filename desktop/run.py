#!/usr/bin/env python3
"""DIYgitizer Desktop App — entry point.

Usage:
    python run.py
"""

import sys
import os
import traceback
import logging
from datetime import datetime

# Ensure the desktop directory is on the path so 'diygitizer' package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Crash log setup ───────────────────────────────────────────────────

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "diygitizer.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("diygitizer")

# Also log to console
_console = logging.StreamHandler(sys.stderr)
_console.setLevel(logging.WARNING)
_console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
logging.getLogger().addHandler(_console)


def _crash_log(exc_type, exc_value, exc_tb):
    """Write unhandled exceptions to the crash log and stderr."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    crash_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    crash_file = os.path.join(LOG_DIR, f"crash_{crash_time}.txt")

    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    # Write dedicated crash file
    try:
        with open(crash_file, "w") as f:
            f.write(f"DIYgitizer crash — {crash_time}\n")
            f.write(f"Python {sys.version}\n")
            f.write(f"Platform: {sys.platform}\n")
            f.write("=" * 60 + "\n\n")
            f.write(tb_text)
    except Exception:
        pass

    # Also write to the main log
    logger.critical("Unhandled exception:\n%s", tb_text)

    # Print to stderr so the user sees it
    print(f"\n{'=' * 60}", file=sys.stderr)
    print("DIYgitizer crashed. Details:", file=sys.stderr)
    print(tb_text, file=sys.stderr)
    print(f"Crash log saved to: {crash_file}", file=sys.stderr)
    print(f"Full log: {LOG_FILE}", file=sys.stderr)
    print(f"{'=' * 60}\n", file=sys.stderr)


sys.excepthook = _crash_log

# ── Dependency check ──────────────────────────────────────────────────

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

    logger.info("DIYgitizer starting")

    app = QApplication(sys.argv)
    app.setApplicationName("DIYgitizer")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    logger.info("Main window shown")
    ret = app.exec_()
    logger.info("DIYgitizer exiting (code %d)", ret)
    sys.exit(ret)


if __name__ == "__main__":
    main()
