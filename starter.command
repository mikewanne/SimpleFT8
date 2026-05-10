#!/bin/bash
# SimpleFT8 Starter — Doppelklick im Finder oeffnet Terminal + startet App.
# Endung .command sorgt dafuer dass macOS Finder das Script in Terminal startet.
#
# Single-Instance-Schutz (PRIMAERSTRATEGIE: Window-Title via osascript):
# Mike-Vorschlag 10.05.2026 nach 5x verkackten Doppel-Instanz-Bugs.
# osascript fragt System Events nach jedem Fenster mit "SimpleFT8" im Titel —
# robust gegen Pfad-Leerzeichen, Wrapper-Scripts, alte Python-Versionen,
# fehlende lsof-Permissions. Wenn Match gefunden → Dialog + Abbruch.

APP_DIR="/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
cd "$APP_DIR" || { echo "App-Verzeichnis nicht gefunden: $APP_DIR"; exit 1; }

# ── Single-Instance-Check via Window-Title ─────────────────────────
# osascript returnt PID des Prozesses dessen Fenster "SimpleFT8" im Titel
# hat (oder leer wenn keine App lauft).
RUNNING_PID=$(osascript -e 'tell application "System Events"
    set foundPID to ""
    repeat with proc in (every process whose visible is true)
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
    end repeat
    return foundPID
end tell' 2>/dev/null)

# Fallback: Lockfile-PID-Check (faengt Race-Condition wenn 2 Apps fast
# gleichzeitig starten und noch kein Fenster da ist)
if [ -z "$RUNNING_PID" ] && [ -f "$HOME/.simpleft8/simpleft8.lock" ]; then
    LOCK_PID=$(cat "$HOME/.simpleft8/simpleft8.lock" 2>/dev/null)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        RUNNING_PID="$LOCK_PID"
    fi
fi

if [ -n "$RUNNING_PID" ]; then
    PROC_INFO=$(ps -p "$RUNNING_PID" -o pid,etime,command 2>/dev/null | tail -1)
    MSG="SimpleFT8 läuft bereits (PID $RUNNING_PID).

$PROC_INFO

Bitte die laufende Instanz benutzen oder zuerst manuell beenden:
  pkill -9 -f \"SimpleFT8.*main.py\"
  rm -f ~/.simpleft8/simpleft8.lock"
    echo "$MSG"
    osascript -e "display dialog \"$MSG\" with title \"SimpleFT8 Starter\" buttons {\"OK\"} default button \"OK\" with icon stop" 2>/dev/null
    exit 1
fi

# Sauber — App starten
echo "[Starter] Keine laufende Instanz — starte SimpleFT8 v$(grep '^APP_VERSION' main.py | head -1 | cut -d'"' -f2)"
./venv/bin/python3 main.py
