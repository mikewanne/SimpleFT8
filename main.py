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

APP_VERSION = "0.98.64"

# ── P43: Activity Monitor zeigt Prozess-Namen statt nur "Python" ──
# Bei der P30-Memory-Leak-Diagnose 12.05. konnte Mike SimpleFT8 nicht
# von Qwen3-TTS unterscheiden — beide erschienen als "Python".
try:
    import setproctitle
    setproctitle.setproctitle(f"SimpleFT8 v{APP_VERSION}")
except ImportError:
    pass  # setproctitle ist optional — App laeuft auch ohne

# ── Single-Instance-Lock — verhindert ZWEI gleichzeitige Apps ──
# Mike-Anweisung 2026-05-05 (mehrfach!): nur EINE Instanz darf laufen.
# Doppelte Instanzen ruinieren Statistik (doppelte Decoder-Eintraege),
# lassen UI/Encoder out-of-sync (doppelte Frequenz, doppelte Slots) und
# fuehren zu Falsch-Diagnosen.
_LOCK_FILE = Path.home() / ".simpleft8" / "simpleft8.lock"
_lock_fd = None  # globale fcntl-Lock-Datei, leben bis Prozess-Ende

# Projektverzeichnis in den Python-Pfad aufnehmen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── File Logging mit Tages-Rotation (P20) ──────────────────────────────
# simpleft8.log ist Symlink → simpleft8-YYYY-MM-DD.log (heute).
# Logs >7 Tage werden automatisch geloescht; Mike's Pre-Rotation-
# Historie landet dauerhaft in ~/.simpleft8/archive/.
from core.log_setup import setup_main_log
_LOG_DIR = Path.home() / ".simpleft8"
_log_path, _log_file = setup_main_log(_LOG_DIR)

# ── P52 (v0.97.41): 90-Tage-Rolling-Window fuer statistics/ ──────────
# Stats-Toggle wurde entfernt — Stats sind immer an. Damit Disk-
# P116 (v0.98.01): FIFO-Sliding-Window pro (Modus, Band, Proto, Stunde)-
# Bucket loest 90-Tage-Datum-Cleanup (P52) ab. Saisonale Anpassung +
# Pause-Robustheit (Mike-Anforderung 24.05.). Default N=30. Antenna_QSO
# bleibt 90-Tage-Datum-basiert (Tages-Format). Bandpilot-Cache wird
# invalidiert wenn Files geloescht wurden. Fail-silent.
from core.stats_cleanup import (
    prune_stats_to_max_per_bucket,
    cleanup_antenna_qso_older_than_days,
    invalidate_bandpilot_cache_if_needed,
)
try:
    _STATS_DIR = Path(__file__).parent / "statistics"
    _deleted_buckets = prune_stats_to_max_per_bucket(
        _STATS_DIR, max_per_bucket=30)
    _deleted_qso = cleanup_antenna_qso_older_than_days(
        _STATS_DIR, days=90)
    if _deleted_buckets or _deleted_qso:
        print(f"[Stats-Cleanup] {_deleted_buckets} Files via FIFO gekuerzt, "
              f"{_deleted_qso} antenna_qso Files >90d geloescht")
    invalidate_bandpilot_cache_if_needed(_deleted_buckets)
except Exception as _e:
    print(f"[Stats-Cleanup] Fehler ignoriert: {_e}")


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


def _get_app_dir() -> str:
    """App-Verzeichnis (resolved, Bundle-aware).

    Bei PyInstaller/py2app-Bundles wird `sys.executable` statt
    `__file__` genutzt. Aktuell laeuft SimpleFT8 nicht als Bundle,
    aber Vorbereitung fuer spaeteren Fork.
    """
    if getattr(sys, 'frozen', False):
        return str(Path(sys.executable).parent.resolve())
    return str(Path(__file__).parent.resolve())


def _kill_pid_with_grace(pid: int, grace_s: float = 1.5):
    """SIGTERM, warten, dann SIGKILL falls noch da. Idempotent."""
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"[SingleInstance] SIGTERM PID {pid}")
    except ProcessLookupError:
        return
    time.sleep(grace_s)
    try:
        os.kill(pid, 0)  # lebt noch?
        os.kill(pid, signal.SIGKILL)
        print(f"[SingleInstance] SIGKILL PID {pid} (zaeh)")
    except ProcessLookupError:
        pass


def _pid_has_cwd_in_app_dir(pid: int, app_dir: str) -> bool:
    """Prueft via lsof ob PID cwd im (oder unter dem) App-Verzeichnis hat.

    P132 (26.05.2026): ersetzt 4-Wege-Check der osascript+ps+lsof+lock
    kombinierte. CWD-Vergleich ist deterministisch, setproctitle-immun,
    Pfad-Leerzeichen-immun (lsof -Fn ist newline-getrennt).
    """
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True, text=True, timeout=2,
        )
    except Exception:
        return False
    for line in result.stdout.splitlines():
        if not line.startswith("n"):
            continue
        cwd = line[1:]
        if cwd == app_dir or cwd.startswith(app_dir + "/"):
            return True
    return False


# Backward-Compat-Alias fuer Tests + externe Aufrufer
_is_simpleft8_pid = lambda pid: _pid_has_cwd_in_app_dir(pid, _get_app_dir())


def _read_pid_from_lock(lock_path: Path) -> int | None:
    """PID aus Lock-Datei lesen. None bei leerem/unguetigem Inhalt."""
    try:
        content = lock_path.read_text().strip()
        return int(content) if content else None
    except (FileNotFoundError, ValueError, OSError):
        return None


def _kill_stale_lockfile_owner(app_dir: str, my_pid: int) -> bool:
    """Lockfile-PID lesen, pruefen ob legitime SimpleFT8-Instanz, killen.

    Genau 1 PID (kein Sweep). Wird in zwei Pfaden gerufen:
    a) Nach erfolgreichem flock-Erwerb: faengt alte App-Versionen ab
       die kein flock hielten (P134 R1-Catch 26.05.2026).
    b) Nach flock-Blockade: killt den aktuellen Lock-Inhaber.

    Returns True wenn eine alte Instanz gekillt wurde, False sonst.

    Rest-Risiko (P134 Final-R1 26.05., GELB-Hinweis):
    PID-Reuse-Edge-Case — eine tote SimpleFT8-PID koennte vom OS
    wiederverwendet werden fuer einen fremden Prozess der zufaellig
    cwd im App-Dir hat. Dann wuerde der cwd-Check ihn als legitim
    erkennen und killen. Praktisch extrem unwahrscheinlich (PID-Reuse
    selten + CWD-Koinzidenz) und in Kauf genommen gegen die viel
    groessere Gefahr eines Sweeps der ALLE Fremd-Procs killt.
    """
    old_pid = _read_pid_from_lock(_LOCK_FILE)
    if not old_pid or old_pid == my_pid:
        return False
    try:
        os.kill(old_pid, 0)  # lebt?
    except ProcessLookupError:
        return False  # PID tot, Lockfile-Inhalt stale
    if not _pid_has_cwd_in_app_dir(old_pid, app_dir):
        # Fremder Prozess — NICHT killen, das waere der pgrep-Klassen-Bug
        print(f"[SingleInstance] PID {old_pid} lebt aber cwd nicht im "
              f"App-Dir — fremder Prozess, lasse in Ruhe")
        return False
    print(f"[SingleInstance] Alt-Instanz PID {old_pid} (cwd-match) → killen")
    _kill_pid_with_grace(old_pid)
    return True


def acquire_single_instance_lock():
    """Single-Instance-Lock — robust gegen Race + setproctitle + Zombies.

    P132 (26.05.2026, Mike-Field-Bug 4 Zombies seit 6 Tagen):
    Komplette Neukonzeption nach Tech-Schuld-Erkennung. Alte pgrep-
    basierte Identifikation war fundamental falsch — matched main.py-
    Apps anderer Projekte (Websdr/JimBob), brach durch P43-setproctitle
    der cmdline ueberschreibt.

    P134 (26.05.2026, Mike-Field-Bug „starter wird beendet"):
    lsof-CWD-Backup-Sweep entfernt — killte fremde Python-Prozesse
    (pytest, IDE, Parent-Bash). Selber Fehlerklassen-Bug wie pgrep.
    Stattdessen: nach flock-Erfolg zielgerichtete 1-PID-Pruefung des
    Lockfile-Inhabers (R1-Catch: faengt alte App-Versionen ab, die
    kein flock hielten).

    Strategie (KISS, atomar):
    1. fcntl.flock LOCK_EX|LOCK_NB ATOMAR holen
       (verhindert Doppel-Start-Race zwischen 2 gleichzeitigen Apps)
       Bei Erfolg: Lockfile-PID pruefen — wenn andere SimpleFT8-PID
       lebt + cwd-match → killen (P134 R1-Catch alte Version ohne flock)
    2. Falls Lock blockiert: alte PID lesen, pruefen ob lebt + cwd
       im App-Dir → SimpleFT8-Zombie → killen, Lock uebernehmen
    3. Eigene PID in Lock-Datei schreiben
    4. atexit + signal-Handler fuer sauberen Lock-Release

    Garantie: nach Rueckkehr ist diese die einzige SimpleFT8-Instanz.
    Identifikation: ausschliesslich via cwd-Match (setproctitle-immun)
    und IMMER auf zielgerichtete PIDs aus dem Lockfile — niemals Sweep.
    """
    global _lock_fd

    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    app_dir = _get_app_dir()
    my_pid = os.getpid()

    # SCHRITT 1: Lock-File oeffnen + fcntl atomar holen
    _lock_fd = open(_LOCK_FILE, "a+")
    try:
        fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # P134 R1-Catch: flock frei heisst nicht dass keine andere
        # SimpleFT8-Instanz laeuft — alte Versionen vor v0.98.13 hielten
        # kein flock. Zielgerichtete 1-PID-Pruefung des Lockfile-Inhalts.
        _kill_stale_lockfile_owner(app_dir, my_pid)
    except BlockingIOError:
        # SCHRITT 2: Lock blockiert — Inhaber killen, Lock uebernehmen
        _lock_fd.close()
        _lock_fd = None
        if _kill_stale_lockfile_owner(app_dir, my_pid):
            time.sleep(0.5)
        _LOCK_FILE.unlink(missing_ok=True)

        # Lock erneut versuchen (3x mit 0.5s Pause)
        for attempt in range(3):
            _lock_fd = open(_LOCK_FILE, "a+")
            try:
                fcntl.flock(_lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                _lock_fd.close()
                _lock_fd = None
                time.sleep(0.5)
        if _lock_fd is None:
            print("[SingleInstance] FATAL: Lock nach 3 Retries nicht erhaeltlich")
            sys.exit(1)

    # SCHRITT 3: Eigene PID in Lock-Datei schreiben
    _lock_fd.seek(0)
    _lock_fd.truncate()
    _lock_fd.write(str(my_pid))
    _lock_fd.flush()
    os.fsync(_lock_fd.fileno())
    print(f"[SingleInstance] Lock geholt — PID {my_pid}, app_dir={app_dir}")


# SCHRITT 4: Cleanup bei Exit + Signal-Handler fuer SIGTERM/SIGINT
atexit.register(_release_lock_on_exit)
signal.signal(signal.SIGTERM, _signal_release_and_exit)
signal.signal(signal.SIGINT, _signal_release_and_exit)


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
    # P64 Intent-Klausel (v0.97.37): Höhe 340 → 400 für erweiterten
    # Disclaimer-Text. R1-F2 empfiehlt 400px Puffer gegen HiDPI-
    # Font-Substitution (gegenüber V2-Vorschlag 380).
    dlg.setFixedSize(540, 400)
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

    # P64 Intent-Klausel (v0.97.37): Lizenz + Hobby-Funker-Intent
    # explizit für eventuelle GitHub-Veröffentlichung.
    # Mike-Wortlaut bewusst persönlich gehalten (kein Anwalts-Stil).
    disclaimer = QLabel(
        "Dieses Projekt entstand als persönliches Bastel-Tool für meinen "
        "eigenen Funkbetrieb (DA1MHH). Der Quellcode steht unter MIT-Lizenz "
        "zur freien Verwendung — die Nutzung erfolgt jedoch ausschließlich "
        "auf eigene Gefahr. Keine Gewährleistung, keine Haftung für "
        "Hardware-Defekte, Funklizenz-Verstöße oder andere Folgen. "
        "ANT1 = TX-Antenne (immer). ANT2 = nur RX (NIEMALS TX, "
        "Regenrinne nicht für Sendeleistung geeignet)."
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
    # ⛔ Single-Instance-Lock ZUERST (P132 v0.98.13 KISS-Refactor):
    # fcntl.flock atomar + lsof-CWD-Backup + Port-Cleanup in einer
    # Funktion. Mike-Anweisung 2026-05-05: nur EINE Instanz darf laufen.
    # Garantie: setproctitle-immun, cwd-basierte Identifikation,
    # false-positive-frei fuer andere main.py-Apps.
    acquire_single_instance_lock()

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

    # P152 (v0.98.35, 28.05.2026): Weak-Decode-Log Cleanup (always-on, 7 Tage).
    from core import weak_decode_log as _wdl
    _n_weak = _wdl.cleanup_old_files(keep_days=7)
    if _n_weak:
        print(f"[Weak-Decode-Log] {_n_weak} alte Datei(en) geloescht")

    window = MainWindow(settings)
    window.show()
    # Bundle L (v0.97.38, 15.05.-10.06.2026): Fenster auf Display 3
    # für Remote-Fernwartung. ⛔ NACH 10.06.2026 ENTFERNEN.
    window.move_to_remote_display()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
