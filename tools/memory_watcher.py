#!/usr/bin/env python3
"""Memory-Watcher für SimpleFT8 P30-Diagnose.

Sampelt alle 60s:
- SimpleFT8-PID (filter: cmdline enthält "SimpleFT8" + "main.py")
- RSS, VMS, Threads via `ps`
- Aktueller Modus aus heutigem debug_<datum>.log (parsed)

Schreibt CSV-artige Zeilen + Markdown-Events nach
  ~/.simpleft8/memory_watch.log

Erkennt automatisch:
- App-Restart (PID-Wechsel)            -> ■■■ APP RESTART ■■■
- App-Stop / -Start                    -> ■■■ APP STARTED/STOPPED ■■■
- Modus-/Band-/Scoring-/Adaptive-Wechsel -> ▼▼▼ CHANGE ▼▼▼

Start als Daemon:
  cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
  nohup ./venv/bin/python3 tools/memory_watcher.py > /dev/null 2>&1 &

Stop:
  pkill -f memory_watcher.py

Auswerten (morgen / in 3 Tagen):
  tail -200 ~/.simpleft8/memory_watch.log
  grep -E "CHANGE|RESTART|STOPPED" ~/.simpleft8/memory_watch.log
"""

from __future__ import annotations

import datetime as dt
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

LOG_DIR = Path.home() / ".simpleft8"
OUT_LOG = LOG_DIR / "memory_watch.log"
INTERVAL_S = 60

# Pattern für Modus-Wechsel im debug_<date>.log
RE_BAND = re.compile(r"\[BAND\] _on_band_changed -> (\w+) \(alt: (\w+), rx_mode=(\w+)\)")
RE_DIV_EN = re.compile(r"\[DIV-EN\] _enable_diversity scoring=(\w+)")
RE_DYNAMIC = re.compile(r"\[DYNAMIC\] (reset|deactivate)")
RE_RX_MODE = re.compile(r"_on_rx_mode_changed.*?(\w+)\s*$", re.IGNORECASE)


def find_simpleft8_pid() -> int | None:
    """Finde SimpleFT8-Hauptprozess.

    Strategie: Alle Prozesse mit `main.py` im command -> Working-Directory
    via `lsof -p PID -d cwd` prüfen -> nur PIDs mit "SimpleFT8" im cwd.
    Robust gegen verkürzte cmdlines (z.B. wenn aus venv gestartet)."""
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid,command"],
            capture_output=True, text=True, timeout=5
        ).stdout
    except Exception:
        return None

    candidates: list[int] = []
    for line in out.splitlines():
        if ("main.py" not in line
                or "memory_watcher" in line
                or "grep" in line):
            continue
        try:
            candidates.append(int(line.strip().split()[0]))
        except (ValueError, IndexError):
            continue

    for pid in candidates:
        try:
            cwd_out = subprocess.run(
                ["lsof", "-p", str(pid), "-d", "cwd", "-Fn"],
                capture_output=True, text=True, timeout=5
            ).stdout
        except Exception:
            continue
        # lsof -Fn liefert "n<path>" Zeilen
        for cwd_line in cwd_out.splitlines():
            if cwd_line.startswith("n") and "SimpleFT8" in cwd_line:
                return pid
    return None


def get_mem_info(pid: int) -> dict | None:
    """RSS (KB), VMS (KB), Threads via ps. None wenn Prozess weg.

    Threads via `ps -M -p PID | wc -l` minus 1 (Header-Zeile), weil
    macOS `ps -o nlwp` leer liefert."""
    try:
        out = subprocess.run(
            ["ps", "-o", "rss=,vsz=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        return None
    if not out:
        return None
    parts = out.split()
    if len(parts) < 2:
        return None
    try:
        rss = int(parts[0])
        vms = int(parts[1])
    except ValueError:
        return None

    # Threads separat via ps -M
    threads = 0
    try:
        t_out = subprocess.run(
            ["ps", "-M", "-p", str(pid)],
            capture_output=True, text=True, timeout=5
        ).stdout
        # Header-Zeile + Thread-Zeilen → count - 1
        n_lines = len([ln for ln in t_out.splitlines() if ln.strip()])
        threads = max(0, n_lines - 1)
    except Exception:
        pass

    return {"rss_kb": rss, "vms_kb": vms, "threads": threads}


def get_state_from_debug_log() -> dict:
    """Letzte Modus-/Band-/Scoring-/Adaptive-Werte aus debug_<heute>.log."""
    today = dt.date.today().strftime("%Y-%m-%d")
    log = LOG_DIR / f"debug_{today}.log"
    state = {"band": "?", "mode": "?", "scoring": "?", "adaptive": "?"}
    if not log.exists():
        return state
    try:
        with open(log, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 100_000))  # letzte ~100 KB
            tail = f.read().decode("utf-8", errors="ignore")
    except Exception:
        return state

    # Sequenziell durchgehen — späterer Match überschreibt früheren
    for line in tail.splitlines():
        m = RE_BAND.search(line)
        if m:
            state["band"] = m.group(1)
            state["mode"] = m.group(3)  # rx_mode aus dem BAND-Log
        m = RE_DIV_EN.search(line)
        if m:
            state["mode"] = "diversity"
            state["scoring"] = m.group(1)
        m = RE_DYNAMIC.search(line)
        if m:
            state["adaptive"] = "on" if m.group(1) == "reset" else "off"
    return state


def write_line(text: str) -> None:
    with open(OUT_LOG, "a") as f:
        f.write(text + "\n")
        f.flush()


_running = True


def _handle_sigterm(signum, frame):
    global _running
    _running = False


def main() -> int:
    LOG_DIR.mkdir(exist_ok=True)
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    write_line(f"# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    write_line(f"# memory_watcher gestartet {dt.datetime.now()}")
    write_line(f"# Intervall: {INTERVAL_S}s, Log: {OUT_LOG}")
    write_line(f"# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    last_pid: int | None = None
    last_state: dict | None = None

    while _running:
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pid = find_simpleft8_pid()

        # PID-Wechsel-Events (App-Start/Stop/Restart)
        if pid != last_pid:
            if last_pid is None and pid is not None:
                write_line(f"{now} | ■■■ APP STARTED (PID {pid}) ■■■")
            elif last_pid is not None and pid is None:
                write_line(f"{now} | ■■■ APP STOPPED (war PID {last_pid}) ■■■")
                last_state = None
            elif last_pid is not None and pid is not None:
                write_line(f"{now} | ■■■ APP RESTART: PID {last_pid} -> {pid} ■■■")
                last_state = None
            last_pid = pid

        if pid is None:
            write_line(f"{now} | PID=- | RSS=- | VMS=- | Th=- | NO_SIMPLEFT8")
        else:
            mem = get_mem_info(pid)
            if mem is None:
                write_line(f"{now} | PID={pid} | ERROR=cannot_read_mem")
            else:
                state = get_state_from_debug_log()

                # State-Change-Events
                if last_state and state != last_state:
                    changed = []
                    for k in ("band", "mode", "scoring", "adaptive"):
                        if last_state.get(k) != state.get(k):
                            changed.append(f"{k}:{last_state.get(k)}->{state.get(k)}")
                    if changed:
                        write_line(f"{now} | ▼▼▼ CHANGE: {', '.join(changed)} ▼▼▼")
                last_state = state

                rss_mb = mem["rss_kb"] / 1024
                vms_mb = mem["vms_kb"] / 1024
                write_line(
                    f"{now} | PID={pid} | RSS={rss_mb:>6.0f}MB | "
                    f"VMS={vms_mb:>7.0f}MB | Th={mem['threads']:>2} | "
                    f"Band={state['band']:>4} | Mode={state['mode']:>9} | "
                    f"Scoring={state['scoring']:>8} | Adaptive={state['adaptive']}"
                )

        # Schlaf mit Abbruch-Check (Schritte von 1s damit auch kleine
        # INTERVAL_S-Werte korrekt funktionieren — Bug-Fix vs `// 5 = 0`)
        for _ in range(INTERVAL_S):
            if not _running:
                break
            time.sleep(1)

    write_line(f"# memory_watcher gestoppt {dt.datetime.now()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
