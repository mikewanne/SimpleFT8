#!/usr/bin/env python3
"""SimpleFT8 — Minimaler FT8/FT4 Client für macOS.

DA1MHH / Mike — Herne, Ruhrgebiet — 2026
"""

import sys
import os
import subprocess
import time
import fcntl
import atexit
import signal
from pathlib import Path

APP_VERSION = "0.97.10"

# ── Single-Instance-Lock — verhindert ZWEI gleichzeitige Apps ──
# Mike-Anweisung 2026-05-05 (mehrfach!): nur EINE Instanz darf laufen.
# Doppelte Instanzen ruinieren Statistik (doppelte Decoder-Eintraege),
# lassen UI/Encoder out-of-sync (doppelte Frequenz, doppelte Slots) und
# fuehren zu Falsch-Diagnosen.
_LOCK_FILE = Path.home() / ".simpleft8" / "simpleft8.lock"
_lock_fd = None  # globale fcntl-Lock-Datei, leben bis Prozess-Ende

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


def _release_lock_on_exit():
    """Lock-Release bei Prozess-Ende (atexit + Signal-Handler)."""
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
    """Bei SIGTERM/SIGINT: Lock freigeben + sauber beenden."""
    _release_lock_on_exit()
    sys.exit(0)


_simpleft8_window_pids_cache: set[int] | None = None


def _get_simpleft8_window_pids() -> set[int]:
    """Cached osascript-Query: PIDs aller Prozesse mit "SimpleFT8" im Window-Title.

    Mike-Vorschlag 10.05.2026 (Primaer-Strategie nach 5x verkackten
    Doppel-Instanz-Bugs): macOS System Events fragt direkt nach Fenstern.
    Robust gegen Pfad-Leerzeichen, Wrapper-Scripts, lsof-Permission-Fails.

    Cache wird in _kill_all_simpleft8_instances einmal pro Lauf gesetzt
    und in _is_simpleft8_pid genutzt — verhindert 100x osascript-Aufruf
    beim Filter ueber alle pgrep-Kandidaten.
    """
    global _simpleft8_window_pids_cache
    if _simpleft8_window_pids_cache is not None:
        return _simpleft8_window_pids_cache
    pids: set[int] = set()
    try:
        result = subprocess.run(
            ["osascript", "-e",
             '''tell application "System Events"
                set foundPIDs to {}
                repeat with proc in (every process whose visible is true)
                    try
                        repeat with w in (every window of proc)
                            set wTitle to name of w as string
                            if wTitle contains "SimpleFT8" then
                                set end of foundPIDs to (unix id of proc as string)
                                exit repeat
                            end if
                        end repeat
                    end try
                end repeat
                set AppleScript's text item delimiters to ","
                return foundPIDs as string
            end tell'''],
            capture_output=True, text=True, timeout=5,
        )
        for token in result.stdout.strip().split(","):
            token = token.strip()
            if token.isdigit():
                pids.add(int(token))
    except Exception:
        pass
    _simpleft8_window_pids_cache = pids
    return pids


def _is_simpleft8_pid(pid: int) -> bool:
    """Prueft ob PID eine SimpleFT8-Instanz ist — 4-Wege-Check.

    Wichtig: pgrep auf 'python.*main\\.py' findet ALLE main.py-Apps im System
    (z.B. Websdr-Cockpit). Nur Prozesse die wirklich SimpleFT8 sind duerfen
    gekillt werden!

    Bug 10.05.2026: 13079 lief 4 Tage parallel zu neuer v0.96.2 — Wurzel:
    - ps -o command zeigt nur 'python main.py' (kein "SimpleFT8" im argv)
    - lsof CWD truncated bei Leerzeichen ("KI N8N Projekte" → "n/.../KI")
    → beide Wege failen, alte Instanz unter dem Radar.

    Fix: 4 Wege parallel — EIN Treffer reicht:
    1. PRIMAER: osascript Window-Title-Check (Mike-Vorschlag, robustest)
    2. ps -o command — argv enthaelt 'SimpleFT8' (greift bei abs. Pfaden)
    3. lsof CWD — kann bei Leerzeichen brechen, bleibt als Defense-in-Depth
    4. Lockfile-PID-Match
    """
    # Weg 1: Window-Title-Check (cached osascript-Query)
    if pid in _get_simpleft8_window_pids():
        return True

    # Weg 2: ps -o command (voller argv inkl. python-pfad + script-pfad)
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=2,
        )
        if "SimpleFT8" in result.stdout:
            return True
    except Exception:
        pass

    # Weg 3: lsof CWD-Check (legacy, kann bei Leerzeichen brechen)
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("n") and "SimpleFT8" in line:
                return True
    except Exception:
        pass

    # Weg 4: Lockfile-PID-Match
    try:
        if _LOCK_FILE.exists():
            content = _LOCK_FILE.read_text().strip()
            if content == str(pid):
                return True
    except Exception:
        pass

    return False


def _kill_all_simpleft8_instances():
    """ALLE laufenden SimpleFT8-Instanzen finden und killen.

    Strategie:
    1. pgrep mit breitem Pattern (main.py + start_simpleft8) — findet Kandidaten
    2. CWD-Filter via lsof: nur Prozesse mit CWD in /SimpleFT8/ killen
       → schuetzt andere main.py-Apps (Websdr, JimBob etc.) vor Kollateral-Kill
    """
    my_pid = os.getpid()
    found_any = False
    patterns = [
        r"python.*main\.py",
        r"python.*start_simpleft8",
    ]
    # Sammle alle eindeutigen Kandidaten-PIDs aus allen Patterns
    candidate_pids = set()
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
                candidate_pids.add(pid)
        except Exception as e:
            print(f"[SingleInstance] pgrep-Fehler fuer '{pattern}': {e}")

    # Filtere: nur PIDs mit CWD in SimpleFT8 sind echte Geschwister
    simpleft8_pids = []
    for pid in candidate_pids:
        try:
            os.kill(pid, 0)  # alive?
        except ProcessLookupError:
            continue
        if _is_simpleft8_pid(pid):
            simpleft8_pids.append(pid)
        else:
            # Andere main.py-App (Websdr o.ae.) — NICHT killen
            pass

    for pid in simpleft8_pids:
        print(f"[SingleInstance] Killing SimpleFT8 PID {pid}")
        try:
            os.kill(pid, signal.SIGTERM)
            found_any = True
        except ProcessLookupError:
            pass

    if found_any:
        time.sleep(1.5)  # SIGTERM-Pause
        # Hartes SIGKILL fuer Zaehe
        for pid in simpleft8_pids:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            print(f"[SingleInstance] Hard-kill PID {pid}")
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(1.0)


def acquire_single_instance_lock():
    """⛔ Single-Instance-Lock — robust gegen jede Race-Bedingung.

    Strategie (Mike-Anweisung 2026-05-05, mehrfach!):
    1. pgrep auf ALLE laufenden SimpleFT8-Instanzen (main.py + Wrapper)
    2. SIGTERM auf alle, warten, dann SIGKILL fuer Zaehe
    3. Lock-Datei loeschen (war von toten Instanzen)
    4. fcntl.flock() atomar holen — verhindert dass zwei gleichzeitig
       startende Apps beide nach dem Kill rein-rennen
    5. Eigene PID in Lock-Datei schreiben

    Garantie nach Rueckkehr: GENAU EINE Instanz von SimpleFT8 am Laufen
    — diese. Egal ob alte Instanzen Lock-Datei hatten oder nicht.
    """
    global _lock_fd

    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    # SCHRITT 1: ALLE laufenden Instanzen via pgrep killen — nicht nur die
    # in der Lock-Datei. Belt-and-suspenders gegen Crashes / Wrapper-Mix.
    _kill_all_simpleft8_instances()

    # SCHRITT 2: stale Lock-Datei entfernen (alle Inhaber sind jetzt tot)
    try:
        _LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    # SCHRITT 3: atomar Lock holen (5 Versuche fuer Race-Sicherheit zwischen
    # zwei gleichzeitig startenden Apps)
    for attempt in range(5):
        _lock_fd = open(_LOCK_FILE, "a+")
        try:
            fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _lock_fd.seek(0)
            _lock_fd.truncate()
            _lock_fd.write(str(os.getpid()))
            _lock_fd.flush()
            os.fsync(_lock_fd.fileno())
            print(f"[SingleInstance] Lock geholt — PID {os.getpid()} (Versuch {attempt + 1})")
            return
        except BlockingIOError:
            _lock_fd.close()
            _lock_fd = None
            print(f"[SingleInstance] Lock-Race Versuch {attempt + 1} — warte 0.5s")
            time.sleep(0.5)
            # Erneut killen falls eine zweite App genau jetzt rein-gerannt ist
            _kill_all_simpleft8_instances()

    print("[SingleInstance] FATAL: konnte Lock nach 5 Versuchen nicht holen — Abbruch")
    sys.exit(1)


# Cleanup bei Exit + Signal-Handler fuer SIGTERM/SIGINT
atexit.register(_release_lock_on_exit)
signal.signal(signal.SIGTERM, _signal_release_and_exit)
signal.signal(signal.SIGINT, _signal_release_and_exit)


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


def _show_hardware_warning(app) -> bool:
    """Pflicht-Acknowledgment beim App-Start: ANT1 = TX-only, ANT2 = RX-only.

    Schuetzt vor versehentlichem TX auf ANT2 (Regenrinne ~15m, NICHT fuer
    Sendeleistung ausgelegt — Hardware-Schaden moeglich bei 100W TX).
    Returnt True wenn User OK klickt, False bei Abbruch (App beendet sich).
    """
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    )
    from PySide6.QtCore import Qt

    dlg = QDialog()
    dlg.setWindowTitle("Hardware-Sicherheitshinweis")
    dlg.setModal(True)
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dlg.setFixedSize(540, 300)
    dlg.setStyleSheet("""
        QDialog { background-color: #1a1a2e; }
        QLabel { background-color: transparent; color: #CCC; }
    """)

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(28, 24, 28, 20)
    lay.setSpacing(14)

    # Header
    header = QLabel("⚠  Hardware-Hinweis")
    header.setStyleSheet(
        "color: #FFB000; font-family: Menlo; font-size: 16px; font-weight: bold;"
    )
    lay.addWidget(header)

    # Body: ANT1/ANT2 Regel
    body = QLabel(
        "<span style='color:#00DDFF; font-weight:bold;'>ANT1</span> = IMMER die TX-Antenne. "
        "Kann nicht anders gesetzt werden.<br><br>"
        "<span style='color:#00DDFF; font-weight:bold;'>ANT2</span> = IMMER nur Hilfs-Empfangsantenne. "
        "Wird von der App <b>NIEMALS</b> zum Senden genutzt."
    )
    body.setStyleSheet(
        "color: #CCC; font-family: Menlo; font-size: 12px; line-height: 1.5;"
    )
    body.setWordWrap(True)
    lay.addWidget(body)

    # Haftungs-Disclaimer (Machbarkeitsstudie / Hobby-Projekt)
    disclaimer = QLabel(
        "SimpleFT8 ist eine private Machbarkeitsstudie. Nutzung auf eigene "
        "Gefahr — fuer Schaeden an Hardware, Antennen oder Funkgeraeten "
        "wird keine Haftung uebernommen."
    )
    disclaimer.setStyleSheet(
        "color: #888; font-family: Menlo; font-size: 11px; "
        "padding: 8px; background-color: rgba(60,60,80,0.25); "
        "border: 1px solid #333; border-radius: 4px;"
    )
    disclaimer.setWordWrap(True)
    lay.addWidget(disclaimer)

    lay.addStretch()

    # Button-Reihe
    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)
    btn_cancel = QPushButton("Abbrechen")
    btn_cancel.setStyleSheet(
        "QPushButton { background-color: #333; color: #AAA; border: none; "
        "border-radius: 4px; padding: 8px 20px; font-family: Menlo; "
        "font-size: 12px; font-weight: bold; }"
        "QPushButton:hover { background-color: #444; color: #DDD; }"
    )
    btn_cancel.clicked.connect(dlg.reject)
    btn_ok = QPushButton("OK — verstanden")
    btn_ok.setStyleSheet(
        "QPushButton { background-color: #0066AA; color: white; border: none; "
        "border-radius: 4px; padding: 8px 20px; font-family: Menlo; "
        "font-size: 12px; font-weight: bold; }"
        "QPushButton:hover { background-color: #0088CC; }"
    )
    btn_ok.setDefault(True)
    btn_ok.clicked.connect(dlg.accept)
    btn_row.addStretch()
    btn_row.addWidget(btn_cancel)
    btn_row.addWidget(btn_ok)
    lay.addLayout(btn_row)

    return dlg.exec() == QDialog.Accepted


def main():
    # ⛔ Single-Instance-Lock ZUERST (atomar, killt alte Instanzen).
    # Mike-Anweisung 2026-05-05: nur EINE Instanz darf laufen.
    acquire_single_instance_lock()
    # Belt-and-suspenders: kill_old_instances raeumt zusaetzlich Ports
    # (UDP:4991/TCP:4992) und macOS Dock-Icons auf.
    kill_old_instances()

    from PySide6.QtWidgets import QApplication
    from config.settings import Settings
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("SimpleFT8")
    app.setOrganizationName("DA1MHH")

    # Pflicht-Acknowledgment Hardware-Schutz (ANT1=TX, ANT2=RX-only)
    if not _show_hardware_warning(app):
        sys.exit(0)

    settings = Settings()

    # P21 v0.96.8: Debug-Log Init + Cleanup (Mike-Spec 10.05.2026)
    from core import debug_log as _dbg
    n_deleted = _dbg.cleanup_old_files(keep_days=1)
    if n_deleted:
        print(f"[Debug-Log] {n_deleted} alte Datei(en) geloescht")
    _dbg.set_enabled(settings.get("debug_log_enabled", False))

    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
