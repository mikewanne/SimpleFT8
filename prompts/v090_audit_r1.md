[deepseek] ~34471 Tokens, 4 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=38850 out=6502 total=45352
## ui/dx_tune_dialog.py

- (kein offensichtlicher Fehler gefunden)

## core/diversity.py

- 🔴 BUG: `choose()` in der Mess-Phase liefert ein unfaires Pattern:  
  `("A2","A1","A1","A2","A1","A1")` ergibt 4× A1 + 2× A2 (step 0–5). Die Doku fordert jedoch 3× A1 + 3× A2.  
  Das führt zu systematisch verzerrten Medianwerten und falscher Ratio-Entscheidung.

## ui/mw_cycle.py

- (kein offensichtlicher Fehler gefunden)

## ui/mw_radio.py

- 🟡 VERDACHT: Bandwechsel während eines laufenden Zyklus (Phase 3)  
  `_on_band_changed()` ruft `self._diversity_ctrl.on_band_change()` (reset auf measure + step=0).  
  Der aktuell noch laufende Zyklus (unter altem Band gestartet) wird *nach* dem Reset  
  in `_on_cycle_decoded` verarbeitet, ruft `record_measurement` auf und verfälscht so  
  die neu gestartete Messung (inkonsistenter Zustand zwischen Antenne und step-Zähler).  
  Es fehlt ein Mechanismus, der die Verarbeitung des anstehenden Zyklus nach einem  
  Bandwechsel verwirft.

## Cross-Cutting

- (keine weiteren Auffälligkeiten)
