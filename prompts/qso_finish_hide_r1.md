# DeepSeek-Review R1 — QSO-Finish-Button verstecken + TODO-Pflege

## Kontext

**SimpleFT8** ist ein FT8/FT4 Hobby-Tool für FlexRadio. Wir hatten gerade
einen erfolgreichen Hide-Workflow für den FT2-Button (Decodium-
kompatibel, aber Standards-Fragmentierung → parken statt löschen).

Jetzt das gleiche Muster für `btn_advance` („QSO Finish"):
- Mike hat den Button **nie gebraucht**. Tooltip: „Sendet manuell den
  nächsten QSO-Schritt (R+Report / RR73 / 73 — je nach Phase). Nutze
  bei stuck-Gegenstation." Die regulären FT8-Timeouts (MAX_STATION_CALLS,
  3-min Gesamt-Timeout) fangen stuck-Partner ohnehin ab.
- Workaround-Funktion, kein Sicherheits-Netz (≠ HALT, das bleibt).
- Mike will hide statt delete, damit reaktivierbar (gleiches Argument
  wie bei FT2).

## V1

**AC1 — Visibility-Hide** (`ui/control_panel.py:1199`):
```python
self.btn_advance.setVisible(False)  # + Reaktivierungs-Kommentar
```

**AC2 — Layout** — `adv_row` ist `QHBoxLayout`; Qt kollabiert hidden
Widgets in HBox automatisch → HALT nimmt die volle Zeile, kein Shift
nötig (anders als bei FT2, wo Spalte 3 in Zeile 1 noch 15m enthielt).

**AC3 — Andere Verweise** laufen weiter auf hidden Button ohne
sichtbare Wirkung:
- `mw_radio.py:1224, 1790`: `btn_advance.setEnabled(not locked)`
- `control_panel.py:2165`: `setText(labels.get(state, "QSO Finish"))`
- Signal `advance_clicked = Signal()` line 1306, Handler `_on_advance`
  in `mw_qso.py:373` — bleiben.

**AC4 — Neuer Test**: `btn_advance.isVisible() is False` nach Init.

**AC5 — Doku**: APP_VERSION 0.97.91→0.97.92, CLAUDE.md/HISTORY.md/
HANDOFF.md.

**AC6/AC7 — TODO-Pflege**: vermutlich stale „OFFEN"-Einträge zu ✅
konvertieren (P52, P60, P56, Bundle H sind ✅ in Memory, aber in
TODO.md noch als OFFEN markiert).

## V2 Findings (Self-Review)

- F1: Tests die btn_advance anfassen ungeprüft (→ V3 grep).
- F2: Dynamic-Label-Code läuft weiter auf hidden Button — Crash-frei,
  aber prüfen ob Logik am alten Label-Wert hängt.
- F3: setEnabled-Calls verifizieren — analog FT2 wasserdicht.
- F4: TODO-Pflege braucht systematischen Cross-Check (kein „glauben",
  jeder Eintrag verifiziert).
- F5: _on_advance-Handler bleibt, Signal bleibt — programmatisch
  triggerbar (Tests/Hooks), unabhängig von UI-Sichtbarkeit.
- F6: Konsistenz CLAUDE.md falls adv_row-Layout dort beschrieben.

## Was ich von dir will

**Konzept-Sanity-Check** für eine sehr kleine Änderung — kein Refactor:

1. **Annahmen korrekt?** Insbesondere: kollabiert QHBoxLayout hidden
   Widgets wirklich automatisch (kein leerer Slot)? Wenn ja → die
   AC2-Behauptung „kein Shift nötig" hält.
2. **Versteckte Abhängigkeiten?** Gibt es im angehängten `control_panel.py`
   oder `mw_qso.py` einen Pfad, der `btn_advance.isVisible()` als
   Bedingung nutzt? (Bei FT2 war's nicht der Fall — analog erwartet.)
3. **`_on_advance`-Handler** in `mw_qso.py:373`: löst er irgendeine
   Logik aus, die jetzt unerwartet brachliegt oder Inkonsistenzen
   erzeugt?
4. **Tests**: was wäre ein vollständiger Test-Plan für diesen Hide?
5. **Sonstige Risiken** die wir übersehen haben?

Antworte auf Deutsch, knapp, konkret, mit Datei:Zeile. Es geht um
eine 1-Zeilen-Änderung — sei kritisch ob das wirklich so sauber ist
wie wir glauben, oder ob es einen Stolperdraht gibt.
