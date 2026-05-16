## Findings

### F-R1-1 [Hinweis] Defensive QScreen-Check empfohlen
Das hartkodierte `move(2944, 0)` birgt das Risiko eines unsichtbaren Fensters, wenn Display 3 physisch nicht angeschlossen ist (F2).  
Die vorgeschlagene `QGuiApplication.screens()`‑Prüfung ist minimaler Zusatzaufwand (~5 Zeilen), verbessert die Robustheit und bleibt KISS‑konform.  
**Empfehlung:** Defensive‑Check in die Helper‑Methode einbauen.

### F-R1-2 [Hinweis] Helper‑Name
`move_to_remote_display` beschreibt den Zweck treffend (Mike‑Remote) und ist für die temporäre Nutzung bis 10.06.2026 klar.  
`move_to_preferred_display` wäre zu generisch – verführt zu Annahmen über Konfigurierbarkeit, die nicht gegeben ist.  
**Empfehlung:** `move_to_remote_display` beibehalten.

### F-R1-3 [Hinweis] Kein Settings‑Toggle – Hardcode mit Revert‑Kommentar
Die Anforderung gilt nur bis 10.06.2026 und ist eine feste Position. Ein Settings‑Toggle würde unnötig Komplexität (UI, Persistenz) einführen und liegt außerhalb des Scopes.  
**Empfehlung:** Hartkodierte Position mit klarem Kommentar, dass der Block nach dem 10.06.2026 entfernt werden muss. Das ist KISS pur.

### F-R1-4 [Hinweis] Bypass‑Button – Redundanz akzeptabel
Zwei Buttons mit gleicher Wirkung („ohne Radio weiter“ / „Beenden“) sind redundant, aber Mike hat den Text explizit genannt und keine Entfernung gewünscht. Die Redundanz ist unkritisch für die Bedienung.  
**Empfehlung:** Button so lassen. Falls Mike später stört, eigens anpassen.

### F-R1-5 [KISS‑Check] Bundle bleibt schlank
Die beiden Änderungen (Display‑Move + Quit‑Bypass) sind atomar und unabhängig. Der Helper‑Mechanismus synchronisiert die zwei Caller‑Pfade (`main.py` + Wrapper) elegant und ohne Code‑Duplikation. Keine unerwarteten Seiteneffekte. **KISS erfüllt.**

## Push‑Empfehlung
**Bundle L kann gepushed werden.**  
Umsetzung gemäß V2‑Plan:  
- `MainWindow.move_to_remote_display()` mit defensivem Screen‑Check,  
- Aufruf in `main.py` und `start_simpleft8_nokill.py` nach `window.show()`,  
- `_on_continue_without_radio` ruft `QApplication.quit()` + `reject()`,  
- Versions‑Bump auf 0.97.38 in Commit‑3.  

Alle bestehenden Tests bleiben unverändert (AC4); der Defensive‑Check verhindert Offscreen‑Fenster bei abgezogenem Display.
