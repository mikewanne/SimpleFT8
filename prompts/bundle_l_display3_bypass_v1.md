# Bundle L V1 — Display-3-Auto-Move + Bypass-Button = Beenden

**Datum:** 2026-05-15 abends
**Version:** v0.97.37 → v0.97.38 (geplant, klein)

## Mike-Wunsch O-Ton

> „kannst du bitte einstellen das a. die app immer auf bildschirm 3 zu
> sehen ist und b. beendet die app sich wenn ich auf ohne radio weiter
> gehe und es ist kein radio an"

## Interpretation

### A — Display 3 automatisch

App soll **immer** auf Display 3 erscheinen (Position 2944,0 laut
Memory-Update). Heute passiert das nur via osascript-Trigger im
Ferienhaus-Setup. Mike will das jetzt im normalen App-Start automatisch.

Begründung: Mike arbeitet bis 10.06.2026 remote vom Ferienhaus —
Display 3 ist der Bildschirm den er via Screen-Sharing sieht. Aktuell
muss Mike jedesmal manuell osascript ausführen → nervig.

### B — „ohne Radio weiter"-Button beendet App

Heute: `_on_continue_without_radio` macht `self.reject()` → Dialog
schließt, App läuft im Demo-Modus weiter (read-only, kein Funk).

Mike-Spec: Demo-Modus macht praktisch keinen Sinn (Mike will funken,
nicht read-only browsen). Wenn kein Radio da ist und Mike klickt
„ohne Radio weiter", soll App sich beenden.

KISS-Lösung: `_on_continue_without_radio` macht jetzt analog zu
`_on_quit`: `QApplication.quit() + reject()`.

Konsequenz: die zwei Buttons („ohne Radio weiter" + „Beenden")
machen funktional dasselbe. Das ist redundant, aber Mike hat den
„ohne Radio weiter"-Text/Button-Hinweis nicht erwähnt, also bleibt
er. Falls Mike das später bereinigen will → eigener Workflow.

## AC

| # | Was |
|---|---|
| AC1 | `main.py` ruft nach `window.show()` `window.move(2944, 0)` (Display 3) |
| AC2 | Kommentar im Code dass das Mike's Remote-Wunsch ist (10.06.2026 reverten) |
| AC3 | `ui/connect_status_dialog.py:_on_continue_without_radio` ruft `QApplication.quit() + reject()` (analog `_on_quit`) |
| AC4 | Bestehende Tests bleiben grün |

## Code-Plan (3 Commits)

| # | Datei | Was |
|---|---|---|
| C1 | `main.py` | `window.move(2944, 0)` nach `window.show()` + Kommentar |
| C2 | `ui/connect_status_dialog.py` | `_on_continue_without_radio` → quit |
| C3 | `main.py` APP_VERSION 0.97.37 → 0.97.38 + Tests + Doku |

## Tests

- T1 Source-Check: `main.py` enthält `window.move(2944, 0)` nach `window.show()`
- T2 Source-Check: `_on_continue_without_radio` ruft `QApplication.quit()`
- T3 Bestehende ConnectStatusDialog-Tests bleiben grün

## Aus Scope

- Display-Position als Setting konfigurierbar machen (Mike will fix)
- „ohne Radio weiter"-Button umbenennen oder entfernen (Mike sagt nichts)
- Multi-Display-Auto-Detection via QScreen API (hartkodierte Position
  reicht für Mike's Setup, KISS)

## Risiken

1. **Andere Mac-Setups:** Position 2944,0 ist Mike-spezifisch. Falls
   anderer User die App startet, landet das Fenster ggf. unsichtbar.
   Mike-Antwort: das ist sein privates Tool, andere Setups irrelevant.
2. **Display 3 weg:** Wenn Mike das Display absteckt, ist 2944,0
   unsichtbar. Qt macht dann auto-fallback auf Main-Display? Oder
   bleibt Fenster offscreen? V2 prüfen.
3. **Wrapper-Script `start_simpleft8_nokill.py`:** ruft auch
   `window.show()` (Z.219). Wenn der Display-Move in `main.py:main()`
   passiert, wirkt er NUR im normalen App-Start, NICHT im Wrapper.
   Lösung: Display-Move in `main_window.__init__` ODER an beiden Stellen.
   V2 entscheidet.
