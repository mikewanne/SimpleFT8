# P101 — Final-R1 Push-Check

Bundle aus 2 Bugs nach Mike-Field-Test 21.05. (v0.97.72 P100 Live-Test):

**Bug A (TUNE-Override startet nicht):**
- `ui/mw_tx.py:_on_tune_override`: Guard von `btn_tune.isChecked()` auf
  `_tune_active` umgestellt (P101). Bei aktivem TUNE → `_tune_stop(None)`
  synchron + sofort `_tune_start(duration_s)` (Variante B „Dauer-Switch
  in einem Rutsch"). 4 Diagnose-Prints für Signal-Verifikation
  (R1-Empfehlung Phase 1).
- `ui/control_panel.py:_on_tune_button_context_menu`: Inline-Lambda durch
  `_emit_override`-Helper ersetzt damit Print möglich.

**Bug B (QMenu Padding-Asymmetrie):**
- `ui/qso_panel.py:_build_columns_menu`: padding `4px 32px 4px 28px` →
  `4px 20px 4px 20px` (symmetrisch). Neue Indicator-Regel
  `margin-left: 0px; subcontrol-position: left center` (R1: macOS-Theme
  kann sonst Indikator rechts rendern).
- `ui/rx_panel.py`: 2× identischer Fix für Spalten-Menü + Länder-Filter.

**Tests:** 1683 → 1696 (+9 P100 ergänzt/angepasst, +4 P101, +2 P95-Updates).
Voller Test-Lauf grün.

---

## Bitte prüfen

1. Hardware-Sicherheit: `_tune_stop(None)` mitten in laufendem TUNE während
   Closed-Loop Phase B — gibt's da einen Race? Re-Entry-Sperre
   `_tune_stop_active` in `_tune_stop` Z.200 sollte das abfangen, aber
   bitte verifizieren ob das bei direktem Stop+Restart sauber durchläuft.

2. Diagnose-Prints — bleiben für Mike's Field-Test, R1-Empfehlung. Sollen
   sie nach Bestätigung entfernt werden oder dauerhaft als Log bleiben?

3. Variante B (Switch statt Stop) — ist die Spec-Auslegung „in einem Rutsch"
   = „Dauer umschalten" wirklich korrekt? Falls Mike doch lieber Stop will,
   ist nur ein `return` nach `_tune_stop` nötig.

4. Padding-Werte `20/20` mit `subcontrol-position: left center` — gibt's
   eine Plattform wo der Indicator dann gar nicht mehr sichtbar ist
   (Clipping)? Symmetrische Werte sollten universal sein.

5. Was übersehen wir? Es geht um Push-Freigabe.
