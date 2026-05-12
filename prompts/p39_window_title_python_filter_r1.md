# P39 — Window-Title-Check Process-Name-Filter (DeepSeek-R1-Review)

## Auftrag

Pruefe V2 fuer kleinen AppleScript-Bugfix in einem FT8-Hobby-Tool.
Fokus:
1. AppleScript-Syntax stimmt?
2. Process-Name-Pruefung auf macOS sicher (Python-App vs python3-CLI)?
3. Edge-Cases die ich uebersehe?
4. KISS-Check (gibt es einfachere Loesung)?

Kurze Antwort. KP-Findings KRITISCH/SOLLTE/KOENNTE/OK.

---

## Bug (12.05.2026, gerade live verifiziert)

`starter.command:17-32` osascript matcht jeden visible Prozess dessen
Fenster-Titel „SimpleFT8" enthaelt. Mike-Live-Check:

```
PID=23196 | proc=Google Chrome
title=mikewanne/SimpleFT8: Autonomous FT8/FT4/FT2 client for FlexRadio... - Google Chrome
```

→ Chrome-Tab mit GitHub-Repo wird faelschlich als „SimpleFT8 laeuft" interpretiert.

Vorgaenger-Fix P38 (PID-Recycling-Schutz im Lock-Fallback) ist korrekt,
greift aber NICHT — weil die osascript-Primaerstrategie schon vorher
falsch matcht. P39 fixt die eigentliche Wurzel.

## V2-Fix (`starter.command:17-32`)

```applescript
RUNNING_PID=$(osascript -e 'tell application "System Events"
    set foundPID to ""
    repeat with proc in (every process whose visible is true)
        set procName to (name of proc as string)
        -- Nur Python-Prozesse pruefen (filtert Browser/Editor mit
        -- "SimpleFT8" im Window-Titel raus, z.B. GitHub-Tabs)
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
```

## Akzeptanzkriterien

- AK1: Chrome/Safari/Firefox mit „SimpleFT8" im Tab-Titel → kein Match (BUGFIX)
- AK2: SimpleFT8 laeuft (Python-Prozess mit "SimpleFT8" im Fenster-Titel)
  → Match wie bisher (Status quo)
- AK3: Lock-Fallback P38-Pfad unveraendert
- AK4: macOS-Process-Namen „Python" / „python3" / „python3.12" gematcht
- AK5: Wrapper-Fall (`start_simpleft8_nokill.py`) — Process-Name bleibt
  „Python" durch venv-binary

## V2-Self-Review

1. macOS-Process-Name: Python-App heisst im System Events „Python"
   wenn Bundle (Doppelklick), „python3.x" wenn CLI direkt.
   `is "Python" or starts with "python"` deckt beide ab.
2. PyInstaller-Bundle in Zukunft? Heute irrelevant, Pattern erweitern
   wenn noetig.
3. AppleScript-Syntax `name of proc as string` ist Standard-API.
4. Mike's Live-Test: GitHub-Tab offen → osascript returnt leer →
   SimpleFT8 startet ohne Banner. Eigentlicher Erfolgs-Test.

## Frage an R1

1. AppleScript-Pitfalls (z.B. `procName starts with "python"` Match
   gegen „Python Launcher.app" oder andere ungewollte)?
2. Edge: SimpleFT8 startet ueber `./venv/bin/python3 main.py` — wie
   heisst der Process in System Events?
3. Sollte zusaetzlich der Command-Line gegrept werden (Belt-and-suspenders)?
4. KISS-Bewertung: simplere Loesung moeglich?
