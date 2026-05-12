# P38 — PID-Recycling-Schutz im Starter (DeepSeek-R1-Review)

## Auftrag

Kleiner Bash-Script-Bugfix in einem FT8-Hobby-Tool. Pruefe V2 auf:
1. Bash-Stolpersteine (Quoting, Subshell, Whitespace in Pfaden)
2. macOS-spezifische Probleme (`ps -o command=` Format, AppleScript-Race)
3. Edge-Cases die ich uebersehen habe
4. KISS-Check

Kurze Antwort. KP-Findings KRITISCH/SOLLTE/KOENNTE/OK.

---

## Bug

`starter.command:36-41` blockt legitimen App-Neustart wenn macOS die freie
SimpleFT8-PID an eine andere App (z.B. Chrome) recycled hat:

```bash
if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    RUNNING_PID="$LOCK_PID"   # falsch wenn PID jetzt zu Chrome gehoert
fi
```

Mike-Screenshot zeigt: Lock-PID 23196 → kill -0 success → Dialog
„SimpleFT8 laeuft bereits" — aber Process-Info zeigt
`/Applications/Google Chrome.app/...`. Eindeutig PID-Recycling.

## V2-Fix

```bash
if [ -z "$RUNNING_PID" ] && [ -f "$HOME/.simpleft8/simpleft8.lock" ]; then
    LOCK_PID=$(cat "$HOME/.simpleft8/simpleft8.lock" 2>/dev/null)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        # P38: PID-Recycling-Schutz
        PROC_CMD=$(ps -p "$LOCK_PID" -o command= 2>/dev/null)
        if echo "$PROC_CMD" | grep -q "SimpleFT8.*main\.py"; then
            RUNNING_PID="$LOCK_PID"
        else
            # PID recycled — stale Lock loeschen
            rm -f "$HOME/.simpleft8/simpleft8.lock"
        fi
    fi
fi
```

## Akzeptanzkriterien

- AK1: SimpleFT8 laeuft → Starter blockt (Status quo)
- AK2: SimpleFT8-PID an Chrome recycled → Starter erkennt, Lock loeschen,
  starten (BUGFIX)
- AK3: PID gar nicht aktiv → `kill -0` fail → Lock ignoriert (Status quo)
- AK4: Window-Title-Match-Pfad (Primaerstrategie Z.17-32) unveraendert

## V2-Self-Review (bereits geprueft)

1. Race kill-0 ↔ ps -p: Edge-Case fuehrt zu „recycled"-Pfad → Lock
   loeschen + starten. Korrekt.
2. grep-Pattern: `SimpleFT8.*main\.py` — falsche Matches unwahrscheinlich.
3. Wrapper-Fall: Lock-PID kommt aus `os.getpid()` in main.py → ps -p
   zeigt main.py-Cmdline → grep matcht.
4. macOS `ps -o command=` POSIX-Standard.

## Frage an R1

1. Bash-Pitfalls in Fix uebersehen?
2. `grep -q` Output-Verschlucken sicher?
3. Sollte `rm -f` zusaetzlich Race-protected sein (`flock` oder so)?
4. Bessere KISS-Variante?
