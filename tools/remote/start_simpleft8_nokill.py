#!/usr/bin/env python3
"""Wrapper um SimpleFT8 ohne kill_old_instances zu starten.
Fuer Background-Launch von Bash (osascript wuerde sonst die App killen).

⛔ WICHTIG (Mike-Anweisung 2026-05-05): Single-Instance-Lock MUSS auch
hier aktiv sein — sonst kann ueber diesen Wrapper eine zweite Instanz
parallel zur normalen main.py laufen (das war der Bug heute!).
"""
import sys
import os
import time
import fcntl
import atexit
import signal

PROJECT = "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

# File-Logging wie in main.py
from pathlib import Path
_LOG_DIR = Path.home() / ".simpleft8"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = open(_LOG_DIR / "simpleft8.log", "a", buffering=1)


class _Tee:
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


# ── Single-Instance-Lock (kopiert aus main.py — Mike-Anweisung) ─────
_LOCK_FILE = Path.home() / ".simpleft8" / "simpleft8.lock"
_lock_fd = None


def _release_lock_on_exit():
    global _lock_fd
    if _lock_fd is not None:
        try:
            fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_UN)
            _lock_fd.close()
        except Exception:
            pass
        _lock_fd = None
    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _signal_release_and_exit(signum, frame):
    _release_lock_on_exit()
    sys.exit(0)


def _kill_all_simpleft8_instances():
    """ALLE laufenden SimpleFT8-Instanzen via pgrep finden und killen."""
    import subprocess
    my_pid = os.getpid()
    found_any = False
    patterns = [
        r"python.*main\.py",
        r"python.*start_simpleft8",
    ]
    for pattern in patterns:
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True, text=True,
            )
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                try:
                    pid = int(line)
                except ValueError:
                    continue
                if pid == my_pid:
                    continue
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                print(f"[SingleInstance] Killing rogue PID {pid} (Wrapper, matched '{pattern}')")
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                found_any = True
        except Exception:
            pass

    if found_any:
        time.sleep(1.5)
        for pattern in patterns:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", pattern],
                    capture_output=True, text=True,
                )
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        pid = int(line)
                    except ValueError:
                        continue
                    if pid == my_pid:
                        continue
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        continue
                    print(f"[SingleInstance] Hard-kill PID {pid} (Wrapper)")
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            except Exception:
                pass
        time.sleep(1.0)


def _acquire_single_instance_lock():
    """⛔ Robust gegen jede Race-Bedingung — pgrep+kill ZUERST, dann Lock."""
    global _lock_fd
    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    _kill_all_simpleft8_instances()

    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    for attempt in range(5):
        _lock_fd = open(_LOCK_FILE, "a+")
        try:
            fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_fd.seek(0)
            _lock_fd.truncate()
            _lock_fd.write(str(os.getpid()))
            _lock_fd.flush()
            os.fsync(_lock_fd.fileno())
            print(f"[SingleInstance] Lock geholt — PID {os.getpid()} (Versuch {attempt + 1}, Wrapper)")
            return
        except BlockingIOError:
            _lock_fd.close()
            _lock_fd = None
            print(f"[SingleInstance] Lock-Race Versuch {attempt + 1} — warte 0.5s (Wrapper)")
            time.sleep(0.5)
            _kill_all_simpleft8_instances()

    print("[SingleInstance] FATAL: konnte Lock nach 5 Versuchen nicht holen (Wrapper)")
    sys.exit(1)


atexit.register(_release_lock_on_exit)
signal.signal(signal.SIGTERM, _signal_release_and_exit)
signal.signal(signal.SIGINT, _signal_release_and_exit)

# ⛔ Lock holen BEVOR Qt initialisiert wird
_acquire_single_instance_lock()

print("[SimpleFT8] Wrapper-Start ohne kill_old_instances (mit Single-Instance-Lock)")

from PySide6.QtWidgets import QApplication
from config.settings import Settings
from ui.main_window import MainWindow
from main import _show_hardware_warning

app = QApplication(sys.argv)
app.setApplicationName("SimpleFT8")
app.setOrganizationName("DA1MHH")

if not _show_hardware_warning(app):
    sys.exit(0)

settings = Settings()
window = MainWindow(settings)
window.show()

sys.exit(app.exec())
