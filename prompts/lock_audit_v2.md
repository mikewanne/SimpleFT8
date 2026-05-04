# Lock-Coverage-Audit (V2 — Self-Review)

## Was V2 anders/besser macht als V1

V1 hatte folgende Luecken die V2 schliesst:

1. **Race-Mechanismus war unklar formuliert** → V2 zeigt konkreten Datenfluss
2. **Bandpilot-Trigger nicht verifiziert** → V2 bestaetigt: Bandpilot zeigt nur
   Dialog, KEINE programmatischen `band_changed.emit()`-Aufrufe
3. **`_diversity_lock` (threading) nicht erwaehnt** → V2 macht klar dass es
   den Pipeline-Race nicht abdeckt, nur die record_measurement-Sektion
4. **Phase-Check-Bypass durch reset()** → V2 explizit dokumentiert
5. **Mike's KISS-Variante als 1. Vorschlag** → V2 stellt sie konkreter dar

## Kontext (unveraendert)

SimpleFT8 v0.91, nach Block 1+2. R1 hat in v0.90 Bandwechsel-Race-Verdacht
in `mw_radio.py` geaeussert. Mike's KISS-Argument: „Waehrend Messung lauft,
soll ALLES geblockt sein ausser Cancel."

## Konkreter Race-Pfad (V2 verifiziert)

```
T=0   Slot N startet auf 40 m, ant=A2, Decoder beginnt
T=1   User klickt 20 m  ← FRAGE: blockt der UI-Lock das?
T=2   _on_band_changed("20m") laeuft:
        - settings.set("band", "20m")
        - self._diversity_ctrl.on_band_change()
            → reset()
              → _phase = "measure"     ← wichtig
              → _measure_step = 0
              → _measurements = {A1:[], A2:[]}
T=3   Slot N's Decoder kommt mit Decode-Daten zurueck
T=4   _handle_diversity_measure(messages, ant=A2_alt):
        with self._diversity_lock:
            self._diversity_ctrl.record_measurement("A2", ...)
              → Phase-Check: if _phase != "measure": return
                 ABER: _phase ist "measure" (durch reset gesetzt!)
                 → DATEN GEHEN IN 20-m-BUCKET
              → _measurements["A2"].append(40m_score)
T=5   ... weitere Slots fuellen 20-m-Bucket
T=6   _evaluate auf 20 m mit kontaminierten Daten
```

**Kritischer Punkt:** Der Phase-Check in `record_measurement` (Z.385)
schuetzt NUR vor „Daten kommen nach Phase=operate". Bei Bandwechsel wird
Phase explizit ZURUECK auf „measure" gesetzt, der Phase-Check passiert
also ungehindert.

## Was bisher schuetzt — und was nicht

### Schuetzt:
- **UI-Buttons-Disable** waehrend `_set_gain_measure_lock(True)` aktiv —
  blockt **User-Klicks** auf Band-/Mode-Buttons
- **`_diversity_lock`** (threading.Lock in mw_cycle.py:184) — schuetzt
  die kritische Sektion in record_measurement vor parallelen Decoder-
  Threads
- **Phase-Check Z.385** — blockt Daten nach Pipeline-Ende (Phase=operate)

### Schuetzt NICHT:
- **Programmatische Calls** zu `_set_band`/`_set_mode` (z.B. Init,
  zukuenftige Bandpilot-Auto-Wechsel, Tests)
- **Race-Window** im Pipeline-Start: `reset()` lauft VOR
  `_set_gain_measure_lock(True)` (mw_radio.py:811-813) → laufende
  Slots koennen ins frische Bucket schreiben
- **In-Flight-Slots beim Bandwechsel** — Phase-Check-Bypass durch reset()

## Befunde V2-final

### Befund 1 (KRITISCH): Race beim Bandwechsel ist real, nicht Theorie
Der Phase-Check `if self._phase != "measure": return` in `record_measurement`
wird durch `reset()` aktiv ausgehebelt. Datenfluss oben dokumentiert.

**Frequenz im Mike's Use-Case:** Hobby-Funker, mehrere Bandwechsel pro
Session. Auch wenn Race nur in 1 von 10 Wechseln triggert — passiert
es. Daten-Kontamination ist messbar in Statistik-Folgen.

### Befund 2 (KRITISCH): Race beim Mode-Wechsel — gleiche Mechanik
`_on_mode_changed` ruft `self._diversity_ctrl.set_mode(mode)` auf
(Z.208), aber **kein** `reset()`. ABER: gleichzeitig wird Decoder/Encoder
auf neues Protokoll umgeschaltet. Slots in Flight haben dann andere Cycle-
Dauer → Decode-Daten kommen mit verzoegerter Timing zurueck.

**Pruefen R1:** ist Mode-Wechsel weniger kritisch weil reset nicht
passiert? Oder sind Cycle-Timing-Inkonsistenzen ein eigenes Problem?

### Befund 3 (mittel): `_enable_diversity` Z.811-813 Race-Window
```python
self._diversity_ctrl.reset()        # Z.811 ← Bucket geleert
self._set_cq_locked(True)           # Z.812
self._set_gain_measure_lock(True)   # Z.813 ← Lock spaet
```
Reihenfolge umkehren ist trivial:
```python
self._set_cq_locked(True)
self._set_gain_measure_lock(True)
self._diversity_ctrl.reset()  # Lock vor Reset
```

### Befund 4 (mittel): Lock-Reset-Timing in mw_cycle.py:194-197
Mit v0.91 Adaptiv-Stop (#8): Phase=operate kann nach 4 Zyklen erreicht
werden. Slot 5+6 sind „Geister-Slots" — koennen sie noch Decode-Daten
liefern die einen falschen Pfad nehmen? `record_measurement` blockt sie
durch Phase-Check, aber:

**Pruefen R1:** Andere Eintrittspfade fuer Slot-Daten?
- `station_accumulator` — laeuft auch im Operate-Modus
- `station_stats` — Statistik-Logging
- `RX-Panel` — Anzeige
Diese Pfade sind unabhaengig vom Phase-Check.

### Befund 5 (kosmetisch): Bandpilot ist KEIN Race-Pfad
Verifiziert: `bandpilot_dialogs.py` triggert keinen automatischen Wechsel,
zeigt nur Dialog der User-Bestaetigung verlangt. User-Klick im Dialog
geht ueber Standard-Pfad → durch Lock geschuetzt.

## Mike's KISS-Loesung — V2-konkret

```python
# 1. Flag im _set_gain_measure_lock setzen:
def _set_gain_measure_lock(self, locked: bool):
    self._gain_measure_locked = locked  # NEU
    # ... rest unveraendert

# 2. Frueh-Return in _on_band_changed:
@Slot(str)
def _on_band_changed(self, band: str):
    if getattr(self, '_gain_measure_locked', False):
        print(f"[Bandwechsel ignoriert: Pipeline laeuft, bleibe auf {self.settings.band}]")
        # UI-Sync: Button auf altes Band zuruecksetzen
        self.control_panel._set_band(self.settings.band)
        return
    # ... rest unveraendert

# 3. Gleiches in _on_mode_changed:
@Slot(str)
def _on_mode_changed(self, mode: str):
    if getattr(self, '_gain_measure_locked', False):
        print(f"[Mode-Wechsel ignoriert: Pipeline laeuft]")
        self.control_panel._set_mode(self.settings.mode)
        return
    # ... rest unveraendert
```

**Aufwand:** ~10 Zeilen Code + 4-6 Tests.
**Risiko:** Sehr gering. Frueh-Return aendert nichts wenn Lock aus.
**Gewinn:** Lock-Loch geschlossen, R1's Race-Verdacht erledigt.

**ZUSAETZLICH** Befund 3 fixen (3 Zeilen umstellen) — kostet nichts.

## Was V2 explizit FRAEGT R1

### A) Lock-Coverage

1. **Befund 1 (Bandwechsel-Race) — Schweregrad?**
   KRITISCH wie ich denke, oder ueberschaetze ich? Konkret: wie oft
   triggert der Phase-Check-Bypass im normalen Hobby-Use?

2. **Befund 2 (Mode-Wechsel) — gleiche Schwere?**
   Oder ist Mode-Wechsel ein anderer Bug-Klasse (Cycle-Timing)?

3. **Mike's KISS-Loesung (Frueh-Return) — ausreichend?**
   Oder gibt es Pfade die das Flag umgehen? Was ist mit:
   - Programmatischen Aufrufen aus Tests
   - Settings-Dialog (kann settings.set("band", X) → wirft Signal)?
   - Init-Race-Guard (main_window:705 — separater Bug?)

### B) Befund 4 (Slot-Geister-Daten in Operate-Phase)

1. Sind `station_accumulator`/`station_stats`/`RX-Panel` betroffen?
2. Wenn ja: was sollte gefiltert werden? Antennen-Tag (A1/A2) am Slot
   pruefen?

### C) Andere ersichtliche Fehler

Mike's Auftrag: „auf sonstige ersichtliche Fehler in den betroffenen
Abschnitten". Bitte 1× quergelesen:
- `_on_band_changed` (mw_radio.py:265-360) — Exception-Pfade,
  Threading-Reihenfolge, fehlt was?
- `_on_mode_changed` (mw_radio.py:199-260) — gleiches
- `_set_gain_measure_lock` (mw_radio.py:1080-1106) — fehlt ein Button?
- `_handle_diversity_measure` (mw_cycle.py:171-208) — Race-Schutz vollstaendig?

### D) Test-Strategie

- Unit-Test: race-frei → Mock `_set_band`-Aufruf waehrend Pipeline-Lock
  → erwartet Frueh-Return
- Integration-Test: simulierter Slot-In-Flight + Bandwechsel → erwartet
  keine Daten in neuem Band-Bucket
- Wie testet man Slot-In-Flight ohne echten Decoder-Thread?

## Format der Antwort R1

Strukturiert nach A/B/C/D. Pro Befund:
1. Klar/unklar
2. Schweregrad (KRITISCH / mittel / kosmetisch / nicht relevant)
3. Wenn nicht relevant → BEGRUENDEN warum
4. Konkreter Fix-Vorschlag (Pseudo-Code)

KISS-Bias: Lieber kleinerer Fix als ueberambitionierter Refactor.

## Was V2 explizit NICHT geprueft sehen will

- Block 1+2 Optimierungen (sind durch v0.89/v0.91 R1-reviewed)
- Test-Coverage Block 1+2 (675 gruen)
- UI-Design
- Performance
- Dependency-Refactoring

## Auftrag an R1

Du bist Senior-Reviewer (Code + Funk-Praxis). Pruefe V2 hart, mit Bias
zu „lieber Bug zu viel finden als zu wenig". Mike's Anweisung:
„Probleme beseitigen bevor sie relevant werden."
