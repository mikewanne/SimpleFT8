# Lock-Coverage-Audit (V1)

## Kontext

SimpleFT8 v0.91 (04.05.2026), nach Block 1+2 Pipeline-Optimierung.
R1 hat in v0.90 einen Bandwechsel-Race-Verdacht in `mw_radio.py`
geaeussert: laufender Slot kann nach `on_band_change()` reset noch
Decode-Daten liefern → `record_measurement` mit altem Antennen-State
auf neuem Band → Mess-Daten-Leck.

Mike's Argument (KISS): „Waehrend Gain-/Diversity-Messung laeuft, soll
ALLES geblockt sein ausser Cancel-Button. Bandwechsel, Modus-Wechsel,
CQ-Klick — alles." Wenn der Lock dicht ist → R1's Token-Pattern unnoetig.

**Auftrag an R1:** Audit der Lock-Coverage. Wir wollen Probleme beseitigen
BEVOR sie relevant werden. Zusaetzlich: ersichtliche Fehler in den
betroffenen Code-Abschnitten.

## Was bereits existiert

`ui/mw_radio.py:1080` `_set_gain_measure_lock(locked: bool)` — disabled:
- FT8/FT4/FT2-Buttons (Mode)
- Band-Buttons (alle)
- CQ-Button + advance + cancel
- Normal/Diversity-Wechsel
- TUNE-Button + Einmessen-Button

Setzt Statusbar: „GAIN-MESSUNG AKTIV — Bedienung gesperrt" / „DIVERSITY
SETUP AKTIV — Bedienung gesperrt".

## Bekannte Set/Reset-Punkte

```
SET (Lock=True):
  ui/mw_radio.py:813   — _enable_diversity (Diversity einschalten, neue Messung)
  ui/mw_radio.py:1012  — Gain-Messung-Button gedrueckt (Normal-Modus)
  ui/mw_radio.py:1074  — DX-Tune-Pipeline (vor Dialog.show)

RESET (Lock=False):
  ui/mw_radio.py:1149  — _on_dx_tune_accepted (DX-Tune erfolgreich)
  ui/mw_radio.py:1241  — _on_dx_tune_rejected (DX-Tune Cancel)
  ui/mw_cycle.py:195   — wenn Phase=operate erreicht (Diversity-Einmessen fertig)
```

## Befunde aus Schnell-Verifikation

### Befund 1 — `_on_band_changed` hat keinen Lock-Check (mw_radio.py:265)
```python
@Slot(str)
def _on_band_changed(self, band: str):
    self._tune_token = None
    self.settings.set("band", band)
    ...
    self._diversity_ctrl.on_band_change()  # ← reset() der Mess-Daten
    ...
```
Wenn das `band_changed`-Signal aus einer **anderen Quelle** als User-Klick
kommt (Bandpilot Auto-Wechsel, Settings-Dialog, programmatic), feuert es
auch wenn Lock aktiv ist. Buttons-Disable verhindert NUR User-Klicks.

### Befund 2 — `_on_mode_changed` hat keinen Lock-Check (mw_radio.py:199)
Gleiches Problem. Wenn jemand programmatisch `mode_changed.emit()` ausloest
(z.B. Auto-Hunt, Settings-Dialog), feuert _on_mode_changed unbeachtet vom Lock.

### Befund 3 — Race-Window in `_enable_diversity` (mw_radio.py:811-813)
```python
self._diversity_ctrl.reset()        # ← Z. 811: Mess-Daten leer
self._set_cq_locked(True)
self._set_gain_measure_lock(True)   # ← Z. 813: Lock erst danach
```
Reihenfolge: erst `reset()`, dann Lock. Wenn ein laufender Decoder-Slot
zwischen Z.811 und Z.813 mit Decode-Daten ankommt, fuehrt das in das
frische, leere `_measurements`-Bucket → Datenleck.

### Befund 4 — Lock-Reset moeglicherweise zu frueh (mw_cycle.py:195)
```python
if self._diversity_ctrl.phase == "operate":
    if not getattr(self, '_diversity_in_operate', False):
        self._diversity_in_operate = True
        ...
        self._set_gain_measure_lock(False)  # Lock weg
```
Lock geht weg, sobald Phase=operate gesetzt ist (im `_evaluate`). ABER:
ist der laufende Slot zu diesem Zeitpunkt schon abgeschlossen? Oder kann
ein Slot noch Decode-Daten liefern, wenn er kurz vor `_evaluate` gestartet wurde?

### Befund 5 — Adaptiv-Stop Phase 3 (v0.91 #8) verkuerzt Mess-Phase
Mit Block 2 (#8) kann `_evaluate` nach 4 statt 6 Zyklen kommen. Phase=operate
wird frueher gesetzt → Lock geht frueher weg. Aber:
- Slot 5 + 6 (die nicht mehr gemessen werden) koennten noch laufen
- Wenn deren Decode-Daten ueber `record_measurement` kommen → wird ignoriert
  (`if self._phase != "measure": return` Z.385 `record_measurement`)
- Aber: gehen die Daten dann **woanders** hin? (z.B. station_accumulator,
  RX-Liste, Statistik-Logging)

## Was R1 pruefen soll

### A) Lock-Coverage (Hauptauftrag)

1. **Sind alle band_changed/mode_changed-Pfade durch den Lock geschuetzt?**
   - Bandpilot Auto-Wechsel — wird Lock geprueft?
   - Settings-Dialog Aenderungen — wird Lock geprueft?
   - Auto-Hunt — kann Auto-Hunt waehrend Pipeline einen Mode-Change triggern?
   - Programmatic Calls (Tests, Init, andere Module) — bypassen Lock?

2. **Wenn Lock-Loch existiert: Vorschlag fuer KISS-Fix?**
   - Variante a: Frueh-Return in `_on_band_changed`/`_on_mode_changed`
     wenn Lock aktiv ist (`if self._gain_measure_locked: return`)
   - Variante b: Bandpilot/Auto-Hunt etc. respektieren Lock direkt
   - Variante c: Token-Pattern (R1's Original-Vorschlag) — nur falls a/b nicht reichen

3. **Race-Window in `_enable_diversity` Z.811-813 — relevant oder Theorie?**
   Reihenfolge umkehren (erst Lock, dann reset)? Oder reset()-Aufruf irrelevant
   weil Slots zu dem Zeitpunkt noch nicht laufen?

### B) Lock-Reset-Timing (mw_cycle.py:195)

1. Ist Phase=operate ein sicherer Punkt um Lock freizugeben? Oder kann
   ein laufender Slot noch Daten liefern die in einem "Operate"-Pfad
   missinterpretiert werden?

2. Mit v0.91 Adaptiv-Stop (#8): Slot 5+6 sind nicht-gemessene "Geister-Slots".
   Kommen deren Decode-Daten ueber `record_measurement` rein und werden
   per `if self._phase != "measure": return` ignoriert? Oder gibt's andere
   Eintrittspfade (station_accumulator, station_stats, RX-Panel)?

### C) Andere ersichtliche Fehler im betroffenen Code

Mike's Auftrag: „und überprüfen den code auch gleich auf sonstige
ersichtliche fehler in den betroffenen abschnitt".

Bitte pruefen:
- `_on_band_changed` (mw_radio.py:265-360) — Threading, Reihenfolge,
  evtl. fehlende Aufrufe (z.B. _stats_warmup_cycles korrekt?)
- `_on_mode_changed` (mw_radio.py:199-260) — gleiches
- `_set_gain_measure_lock` (mw_radio.py:1080-1106) — fehlt ein Button?
- `_enable_diversity` (mw_radio.py:~770-900) — Race-Schutz vollstaendig?
- mw_cycle.py:180-240 — Phase-Transition-Logik

### D) KISS-Bewertung

Mike will minimal-invasiv. Vorschlag fuer:
- Komplexitaet O(Zeilen) eines Fix
- Risiko (kann der Fix selber neue Bugs schaffen?)
- Test-Coverage-Bedarf (was muss zwingend getestet werden?)

## Format der Antwort

Strukturiert nach A/B/C/D oben. Pro Befund:
1. Klar/unklar/nicht relevant
2. Schweregrad (KRITISCH / mittel / kosmetisch)
3. Konkreter Fix-Vorschlag in Pseudo-Code (kein vollstaendiger Code,
   nur Idee)
4. Test-Empfehlung

Bei „nicht relevant" bitte explizit begruenden warum NICHT — Mike's
Anweisung: „Probleme beseitigen bevor sie relevant werden". Lieber
ein Befund zu viel als ein verstecktes Loch.

## Was NICHT geprueft werden soll

- Block 1+2 Optimierungen selbst (sind durch v0.89/v0.91 bereits R1-reviewed)
- Test-Coverage von Block 1+2 (sind 675 Tests gruen)
- UI-Design-Entscheidungen
- Performance-Optimierungen
