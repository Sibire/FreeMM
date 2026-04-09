"""Auto-installer and launcher for DIYgitizer desktop app.

Run this script to:
1. Install all required Python packages
2. Launch the GUI
"""

import subprocess
import sys
import os

REQUIREMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")


def install_deps():
    print("Checking / installing dependencies...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS, "--quiet"
    ])
    print("Dependencies OK.")


def launch():
    main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    os.execv(sys.executable, [sys.executable, main_py])


if __name__ == "__main__":
    try:
        install_deps()
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        print("Try running: pip install -r requirements.txt")
        sys.exit(1)
    launch()
