# Bundle L R1 Review Request

Klein-Patch für SimpleFT8 v0.97.37 → v0.97.38. Zwei Mike-Wünsche
(zusammen ~10 Zeilen Code):

A) App-Hauptfenster automatisch auf Display 3 (Position 2944,0) bei
   jedem Start. Mike-Remote-Wunsch bis 10.06.2026.
B) „ohne Radio weiter"-Button im ConnectStatusDialog beendet die App
   (statt Demo-Modus zu starten).

## Lies zuerst

- `prompts/bundle_l_display3_bypass_v1.md`
- `prompts/bundle_l_display3_bypass_v2.md`

## Was du prüfen sollst

1. **F2 Defensive QScreen-Check ja/nein?** Hartkodiertes
   `window.move(2944, 0)` kann zu unsichtbarem Fenster führen wenn
   Display 3 abgesteckt. V2 schlägt `QGuiApplication.screens()`
   iteration vor. KISS-Frage: ist das Overengineering oder gerechtfertigt?

2. **Helper-Name:** `move_to_remote_display` oder `move_to_preferred_display`?

3. **Settings-Toggle vs. Hartkodiert:** Mike will fix bis 10.06.2026,
   danach reverten. Settings-Toggle (defaultable) oder Magic-Konstante
   mit Revert-Kommentar?

4. **Bypass-Button:** OK dass „ohne Radio weiter" jetzt funktional
   identisch zu „Beenden" ist (zwei Buttons, gleicher Effekt)?
   Oder Empfehlung den Button zu entfernen?

5. **KISS-Check** insgesamt.

6. **Push-Empfehlung** am Ende.

## Code-Kontext

- `main.py` Z.529-530: `window = MainWindow(settings); window.show()`
- `tools/remote/start_simpleft8_nokill.py` Z.215-216: gleicher Pattern
- `ui/connect_status_dialog.py:211` `_on_continue_without_radio`
- `ui/connect_status_dialog.py:215` `_on_quit`
- `ui/main_window.py` — hier kommt der Helper rein

## Antwort-Format

```
## Findings
### F-R1-1 [Bug/Risiko/Hinweis]
...
```

Plus Push-Empfehlung.
