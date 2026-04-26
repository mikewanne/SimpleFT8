#!/usr/bin/env python3
"""SimpleFT8 — Minimaler FT8/FT4 Client für macOS.

DA1MHH / Mike — Herne, Ruhrgebiet — 2026
"""

import sys
import os
import subprocess
from pathlib import Path

APP_VERSION = "0.64"

# Projektverzeichnis in den Python-Pfad aufnehmen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── File Logging: stdout+stderr in ~/.simpleft8/simpleft8.log ──────────────
_LOG_DIR = Path.home() / ".simpleft8"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = open(_LOG_DIR / "simpleft8.log", "a", buffering=1)


class _Tee:
    """Leitet Ausgabe gleichzeitig an Terminal und Logdatei."""
    def __init__(self, primary, secondary):
        self._p = primary
        self._s = secondary

    def write(self, obj):
        self._p.write(obj)
        self._s.write(obj)

    def flush(self):
        self._p.flush()
        self._s.flush()

    def isatty(self):
        return self._p.isatty()


sys.stdout = _Tee(sys.__stdout__, _log_file)
sys.stderr = _Tee(sys.__stderr__, _log_file)


def kill_old_instances():
    """ALLE alten SimpleFT8-Instanzen sauber beenden inkl. macOS Fenster/Dock.

    1. macOS 'quit app' — schliesst Fenster + Dock-Icon sauber
    2. SIGKILL auf alle SimpleFT8 Python-Prozesse
    3. Ports 4991/4992 freigeben
    4. Warten + verifizieren dass alles weg ist
    """
    import time
    my_pid = os.getpid()

    # 1. macOS: Python-App sauber beenden (schliesst Dock-Icon!)
    subprocess.run(
        ["osascript", "-e", 'quit app "Python"'],
        capture_output=True, timeout=5,
    )
    time.sleep(1)

    # 2. Alle SimpleFT8-Prozesse per SIGKILL beenden
    for attempt in range(3):
        found = False
        for pattern in ["SimpleFT8/main.py", "SimpleFT8/tests/"]:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", pattern],
                    capture_output=True, text=True,
                )
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    pid = int(line)
                    if pid != my_pid:
                        os.kill(pid, 9)
                        found = True
            except (ProcessLookupError, Exception):
                pass

        # 3. Prozesse auf Radio-Ports killen
        for port in ["UDP:4991", "TCP:4992"]:
            try:
                result = subprocess.run(
                    ["lsof", "-ti", port],
                    capture_output=True, text=True,
                )
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    pid = int(line)
                    if pid != my_pid:
                        os.kill(pid, 9)
                        found = True
            except (ProcessLookupError, Exception):
                pass

        if not found:
            break
        time.sleep(1)

    # 4. Verifizieren
    time.sleep(1)
    try:
        result = subprocess.run(
            ["lsof", "-ti", "UDP:4991"],
            capture_output=True, text=True,
        )
        if result.stdout.strip():
            print("[SimpleFT8] WARNUNG: Port 4991 noch belegt!")
        else:
            print("[SimpleFT8] Alte Instanzen beendet — Ports frei")
    except Exception:
        print("[SimpleFT8] Cleanup fertig")


def main():
    kill_old_instances()

    from PySide6.QtWidgets import QApplication
    from config.settings import Settings
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("SimpleFT8")
    app.setOrganizationName("DA1MHH")

    settings = Settings()
    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
