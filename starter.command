#!/bin/bash
# SimpleFT8 Starter — Doppelklick im Finder oeffnet Terminal + startet App.
# Endung .command sorgt dafuer dass macOS Finder das Script in Terminal startet.
#
# Single-Instance-Schutz (3 Schichten, P133+Hotfix 26.05.2026):
# 1. Lockfile-PID-Check (atomar, mit PID-Recycling-Schutz) — Mike-Spec:
#    automatisch killen statt abort
# 2. osascript Window-Title-Check — Backup fuer Instanzen ohne Lock
# 3. Python fcntl.flock — atomare Lock-Garantie als letzte Schicht
#
# Hotfix 26.05.: Schicht „lsof-CWD-Final-Sweep" entfernt — sie killte
# fremde Python-Prozesse (pytest, IDE-Tools) mit cwd im App-Dir und ueber
# die Eltern-Kette sogar den Starter selbst (Exit 144). Selber
# Fehlerklassen-Bug wie pgrep vor P132. lsof-Identifikation gehoert in
# Python (siehe acquire_single_instance_lock in main.py) wo Logik
# praeziser ist (nur PIDs aus Lockfile).

APP_DIR="/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
LOCK_FILE="$HOME/.simpleft8/simpleft8.lock"
cd "$APP_DIR" || { echo "App-Verzeichnis nicht gefunden: $APP_DIR"; exit 1; }

# Helper: Kill PID mit grace (SIGTERM, 1.5s warten, SIGKILL).
kill_with_grace() {
    local pid="$1"
    kill -TERM "$pid" 2>/dev/null
    sleep 1.5
    if kill -0 "$pid" 2>/dev/null; then
        echo "[Starter] PID $pid zaeh — SIGKILL"
        kill -KILL "$pid" 2>/dev/null
    fi
}

# ── SCHICHT 1: Lockfile-PID-Check (R1-empfohlen, Race-sicher) ──────
# Mike-Spec 26.05.: automatisch killen ohne Dialog. PID-Recycling-Schutz
# verhindert Kollateral-Kill recycelter PIDs (z.B. Chrome).
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        # PID lebt — pruefen ob es wirklich SimpleFT8 ist (PID-Recycling)
        PROC_CMD=$(ps -p "$LOCK_PID" -o command= 2>/dev/null)
        if echo "$PROC_CMD" | grep -qE "Python|python|SimpleFT8"; then
            echo "[Starter] Lockfile zeigt lebende Instanz PID $LOCK_PID → killen"
            kill_with_grace "$LOCK_PID"
        else
            echo "[Starter] Lockfile-PID $LOCK_PID ist recycled ($PROC_CMD) — stale Lock"
        fi
    fi
    # Stale-Lock immer entfernen (Inhaber ist jetzt tot oder war es schon)
    rm -f "$LOCK_FILE"
fi

# ── SCHICHT 2: osascript Window-Title-Check ────────────────────────
# osascript returnt PID des Prozesses dessen Fenster "SimpleFT8" im Titel
# hat (oder leer wenn keine App lauft).
#
# P39 (12.05.2026): Nur Python-Prozesse pruefen — sonst matcht jeder
# Browser-Tab mit "SimpleFT8" im Titel (z.B. GitHub-Repo) faelschlich.
# Wenn SimpleFT8 mal als PyInstaller-.app gebundelt wird, heisst der
# Process "SimpleFT8" — dann Filter um `contains "SimpleFT8"` ergaenzen.
RUNNING_PID=$(osascript -e 'tell application "System Events"
    set foundPID to ""
    repeat with proc in (every process whose visible is true)
        set procName to (name of proc as string)
        if procName is "Python" or procName starts with "python" then
            try
                repeat with w in (every window of proc)
                    set wTitle to name of w as string
                    if wTitle contains "SimpleFT8" then
                        set foundPID to (unix id of proc as string)
                        exit repeat
                    end if
                end repeat
            end try
            if foundPID is not "" then exit repeat
        end if
    end repeat
    return foundPID
end tell' 2>/dev/null)

if [ -n "$RUNNING_PID" ]; then
    echo "[Starter] osascript: Fenster-Instanz PID $RUNNING_PID → killen"
    kill_with_grace "$RUNNING_PID"
fi

# Sauber — App starten (python3 blockiert Terminal solange App laeuft)
# Letzte Schicht ist Python fcntl.flock in main.py (P132).
echo "[Starter] Sauber — starte SimpleFT8 v$(grep '^APP_VERSION' main.py | head -1 | cut -d'"' -f2)"
./venv/bin/python3 main.py
EXIT_CODE=$?
# Wenn App mit Fehler endete (z.B. acquire_single_instance_lock failed):
# Terminal offen halten damit Mike die Fehlermeldung sieht.
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "⛔ SimpleFT8 endete mit Exit-Code $EXIT_CODE"
    echo "Drücke Enter zum Schliessen (oder warte 30s) ..."
    read -t 30 -r _ || true
fi
exit $EXIT_CODE
