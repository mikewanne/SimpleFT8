# P79 — Final-R1 Review nach Code-Phase

## Kontext

Voller V1→V2→R1→V3→Code-Workflow durchgezogen. R1 hat „PUSH FREIGEGEBEN"
gesagt nach 9 Findings (1 ORANGE F6, 3 GELB, 5 WEISS) — alle F6+GELB
übernommen. Code ist jetzt eingespielt + 1496 Tests grün (von 1484 → +12
netto inkl. 14 neue P79-Tests, 3 obsolete Modal-Tests entfernt).

**Du sollst jetzt FINAL-R1:** den tatsaechlich eingebauten Code gegen die
V3-Spec + R1-V1-Findings pruefen. Findest du Regressionen, übersehene
Edge-Cases, KISS-Verletzungen, falsche Implementation der R1-Findings?

**Stand:** v0.97.51, Tests 1496 grün. P79-Field-Test pending.

---

## Was implementiert wurde

### C1 `ui/qso_panel.py`
- Modul-Konstante `_SYMBOL_COLORS` mit Wartungs-Kommentar (R1-F1 GELB ✓)
- `add_info` mit:
  - Empty-Guard `if not text: return` mit 1-Zeilen-Kommentar (R1-F4 GELB ✓)
  - `text.startswith(symbol)`-Loop (V2-F5 ✓)
  - `_append_two_color(f"       {symbol}", color, rest, "#666666")` bei Treffer
  - `_append_colored(f"       {text}", "#666666")` bei kein Treffer

### C3 `ui/mw_tx.py:401-405`
- Text-Erweiterung: „Antenne pruefen ODER SWR-Limit in Einstellungen
  anpassen ODER manueller TUNE zum Freischalten."
- Tuner-fehlt-Branch (Z.407-411) UNVERAENDERT

### C5 `ui/mw_radio.py:_show_calibration_done`
- Modal komplett raus (50 LOC → 8 LOC)
- `qso_panel.add_info(text)` mit ✓-Praefix
- `self.statusBar().showMessage(text, 3000)` mit try/except-Wrapper (R1-F6 ORANGE ✓)
- Docstring frei von „QDialog"/„WindowStaysOnTopHint" Strings (sonst T9 falsch)

### Tests
- `tests/test_p79_ui_bundle.py` NEU: T1-T7 add_info Auto-Detect,
  T8 mw_tx Source-Level, T9-T11 mw_radio Source+Smoke, T12 Edge-Case
  (R1-F7 GELB ✓) + 2 Bonus (APP_VERSION + statusBar-Exception-Swallow)
- `tests/test_calibration_dialog_smoke.py`: 3 alte Modal-Tests durch
  einen P79-Test ersetzt (KEIN QDialog mehr).

### APP_VERSION
- `main.py:16` 0.97.50 → 0.97.51

---

## Final-R1 Pruefliste

1. **R1-Findings korrekt umgesetzt?**
   - F6 ORANGE: Statusbar-Echo 3s — ja, mit try/except (verlustsicher).
   - F1 GELB: Wartungs-Kommentar in `_SYMBOL_COLORS` — ja.
   - F4 GELB: Empty-Guard-Kommentar — ja.
   - F7 GELB: T12 fuer `add_info("⚠")` — ja.

2. **Backwards-Compat:** wurden alle add_info-Aufrufer beruecksichtigt?
   Bitte aktiv suchen ob ein Aufrufer existiert dessen Verhalten regressiv
   wird (z.B. Aufrufer der ein nicht-mappte Symbol sendet → graue
   Default-Branch, kein Bug).

3. **Thread-Safety:** add_info wird aus dem GUI-Thread aufgerufen
   (Decoder/Encoder-Signals → Qt::QueuedConnection). Patch aendert das
   Verhalten zu `_append_two_color` (war schon thread-safe verwendet
   in add_tx/add_rx) — kein neuer Race.

4. **`statusBar()`-Aufruf:** in einem Mixin (RadioMixin). `self` muss
   QMainWindow sein. Funktioniert das immer? Was wenn `_show_calibration_done`
   aus Test gerufen wird (siehe try/except)?

5. **Test-Coverage:** 14 Tests grün. Fehlen Edge-Cases? Hat T9 die
   richtigen Source-Strings als Verbot (QDialog/WindowStaysOnTopHint/
   _close_timer)? Was wenn die Symbol-Zeichen in einer kuenftigen
   Unicode-Norm normalisiert werden?

6. **Hardware-Pflicht:** kein TX-Trigger angefasst, ANT1-Pflicht intakt?

7. **Synergie-Pruefung:** ✓-Symbol in `_show_calibration_done` wird
   automatisch grün gerendert via `add_info` Auto-Detect? Visuell ok?

8. **Backup + Versions-Bump:** `Appsicherungen/2026-05-18_v0.97.50_vor_p79/`
   liegt mit qso_panel/mw_tx/mw_radio/main vor. APP_VERSION auf 0.97.51.

---

## Push-Empfehlung

Bitte am Ende eine klare Zeile:
- „**PUSH FREIGEGEBEN**" — alles sauber, Field-Test ist letzter Schritt.
- „**PUSH BLOCKIERT WEGEN F<x>**" — ein konkreter Punkt muss vorher gefixt.

Die geaenderten Dateien sind anbei: `ui/qso_panel.py`, `ui/mw_tx.py`,
`ui/mw_radio.py`, `tests/test_p79_ui_bundle.py`,
`tests/test_calibration_dialog_smoke.py`, `main.py`.
