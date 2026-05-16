## Bundle L Final-R1: Review-Ergebnis

**Alle V3-Acceptance-Kriterien sind korrekt implementiert.**

### Check pro AC / Datei

| AC | Beschreibung | Datei | Status |
|----|--------------|-------|--------|
| AC1 | `main.py` ruft `move_to_remote_display()` nach `window.show()` auf | `main.py` Z.~586 | ✅ |
| AC1 | Remote-Wrapper ruft ebenfalls nach `show()` auf | `tools/remote/start_simpleft8_nokill.py` Z.~145 | ✅ |
| R1-F1 | Helper prüft defensiv, ob Punkt (2944,0) von einem Screen abgedeckt wird, sonst kein Move | `ui/main_window.py` `move_to_remote_display()` | ✅ |
| AC3 | Bypass-Button („ohne Radio weiter“) beendet App → `QApplication.quit()` + `reject()` | `ui/connect_status_dialog.py` `_on_continue_without_radio` | ✅ |
| — | Versionsbump auf **0.97.38** | `main.py:APP_VERSION` | ✅ |
| Tests | 6 neue Tests, alle grün; Revert-Kommentare mit Datum 10.06.2026 vorhanden | `tests/test_bundle_l_display3_bypass.py` | ✅ |

### Edge-Cases

- **Display 3 nicht physisch angeschlossen:** Der defensive `geom.contains()`‑Guard verhindert, dass das Fenster im Nichts landet. App bleibt auf dem Hauptbildschirm – kein Datenverlust, kein Crash.
- **Bypass-Button bei laufendem Connect:** App wird sauber beendet (`quit()`), keine verwaisten Prozesse.
- **`move_to_remote_display()` vor `show()`?** In beiden Aufrufern (main.py, Wrapper) korrekt **nach** `show()`. Fenster ist sichtbar, bevor es verschoben wird.
- **Revert-Kommentare** mit Stichdatum 10.06.2026 sind in `main_window.py` und `main.py` vorhanden, sodass die temporäre Logik später einfach gefunden und entfernt werden kann.

### Fazit

**Push freigegeben.**  
Alle V3‑Anforderungen erfüllt, keine offenen Edge‑Cases, Tests grün, Revert-Strategie dokumentiert.
