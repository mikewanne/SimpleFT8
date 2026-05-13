# Bundle B' — Final R1 Codereview Request

Du bist DeepSeek-R1. Dies ist das FINALE Codereview vor Push.
Pruefe den implementierten Code gegen V3-Plan + sucht restliche Bugs,
Doppelschutz-Luecken, Test-Coverage-Gaps.

Pro Finding: Datei:Zeile + konkrete Empfehlung.

Antwort-Schema:
- KRITISCH (KP-N): muss vor Push gefixt werden
- SOLLTE-FIX (S-N): waere besser zu fixen
- KOENNTE (K-N): Hinweis
- ZUSAMMENFASSUNG mit Push-Freigabe-Status

## Implementierte Aenderungen

### P32 — RX-Panel-Spalten-Persist
- `ui/rx_panel.py:50-52` neues Signal `hidden_cols_changed = Signal(list)`
- `ui/rx_panel.py:53-78` Konstruktor: `hidden_cols`-Param + defensive
  Filter (Range, Typ, COL_MSG)
- `ui/rx_panel.py:78-80` Spalten via `setColumnHidden` nach `_setup_ui`
- `ui/rx_panel.py:518-525` `_toggle_column` emittet
  `hidden_cols_changed`
- `ui/main_window.py:528` RxPanel mit
  `hidden_cols=self.settings.get("rx_panel_hidden_cols", [])`
- `ui/main_window.py:656` Signal-Connect
- `ui/mw_qso.py:239-243` neuer Slot `_on_rx_hidden_cols_changed`

### P33 — QSO-Komplett-Reihenfolge
- `core/qso_state.py:101-105` 2 Signale: `qso_confirmed_visual` +
  `qso_confirmed`
- `core/qso_state.py:315-323` `on_cycle_end` WAIT_73-Timeout emittet
  `visual` + `full` direkt hintereinander
- `core/qso_state.py:485-494` `on_message_sent` TX_73_COURTESY emittet
  NUR `full` (kein 2. visual)
- `core/qso_state.py:646-679` `on_message_received` is_73-Branch:
  `visual.emit` SOFORT (vor Courtesy-Send-Trigger). Doppelschutz-else
  emittet `full` (visual schon oben).
- `ui/main_window.py:680-682` Signal-Connect `qso_confirmed_visual`
- `ui/mw_qso.py:496-505` neuer Slot `_on_qso_confirmed_visual` (nur
  `add_qso_complete`)
- `ui/mw_qso.py:507-535` `_on_qso_confirmed` modifiziert
  (`add_qso_complete` RAUS — wurde in visual-Slot gerufen)

### Tests
- `tests/test_p32_rx_panel_persist.py` 6 Tests
- `tests/test_p33_qso_complete_order.py` 6 Tests
- 1204 passed (1192 + 12)

### Konkrete Pruefauftraege

1. **P33 Reihenfolgen-Garantie**: visual + full feuern jetzt in
   verschiedenen Zeitpunkten. Kann Qt `DirectConnection` (default
   bei gleichem Thread) die Reihenfolge invertieren wenn Mike via
   GUI klickt? Antwort sollte „nein" sein (Slot ist im GUI-Thread,
   Signal ebenfalls). Aber pruefen.

2. **P33 Doppel-emit-Schutz**: durchlaufe alle 3 Pfade
   - 73-Empfang in WAIT_73 → visual 1× + full 1× (nach Courtesy)
   - WAIT_73-Timeout → visual 1× + full 1× (direkt)
   - Hypothetischer Doppelschutz → visual 1× + full 1×
   Konnte ich irgendwo doppeltes emit produzieren?

3. **P33 `add_qso_complete`-Aufruf-Pfad**:
   - visual-Slot ruft → 1× pro QSO
   - full-Slot ruft NICHT mehr (RAUS)
   - Frage: hat irgendein anderer Pfad in der Codebase auch noch
     `add_qso_complete` aufgerufen direkt? grep noetig?

4. **P32 Race**: Wenn User schnell mehrere Spalten toggelt, gibt es
   einen Race? `_toggle_column` setzt erst dict, dann Qt-Set, dann
   emit. Single-Threaded GUI = ok. Aber pruefen.

5. **P32 Settings-Save-Failure**: wenn `settings.save()` mal failed
   (Disk voll, Permissions)? Aktuell kein except — wirft Exception.
   In Bundle A war das ein Hinweis. Soll P32 das absichern oder
   passt es so?

6. **P33 - bestehende `test_p1_10_courtesy_73.py` und andere
   QSO-Flow-Tests**: laufen sie weiterhin durch oder erwartet einer
   `qso_confirmed.emit` an einer Stelle wo jetzt `visual` feuert?
   (Voller Test-Lauf hat 1204 passed gemeldet — aber pruefe genau
   ob das wirklich die alten Tests sind.)

7. **APP_VERSION**: 0.97.13 → 0.97.14 ist Bugfix-Bundle. Korrekt.

8. **Memory-Lessons**: `feedback_partial_fix_check_other_paths.md` —
   sind ALLE Pfade gleicher Klasse abgedeckt? grep `qso_confirmed`-
   Aufrufer ergab 4 Stellen: Z.317 (Timeout), Z.488 (Courtesy-Send),
   Z.658 (Doppelschutz), Z.671 (im 73-Empfang else-Branch). Alle
   konsistent behandelt?

9. **Field-Test-Risiko**: was kann beim ersten Field-Test schief
   gehen? Identifiziere 2-3 Punkte fuer Mike.
