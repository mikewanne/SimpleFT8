# P153 R1 — SWR-Freeze: Median über stabiles Fenster statt Snapshot

## Kontext

SimpleFT8 (FT8 FlexRadio Hobby-Tool, DA1MHH). Hardware-Sicherheit:
Bandsperre bei zu hohem SWR, Freigabe nur durch manuellen TUNE mit
SWR ≤ Limit.

**Field-Bug 28.05.:** Tuner matchte sichtbar auf SWR 2,5 (Anzeige zeigte
es), aber das System fror >4,0 ein → Band blieb fälschlich gesperrt.
2. TUNE: zufällig 2,3 → frei. Mike-Diagnose: der Freeze nimmt einen
EINZIGEN Momentan-Snapshot (`radio.last_swr`) — wenn der einen Mess-/
Regel-Ausreißer erwischt, falscher Wert.

**Auslöser:** P142 (gestern) zog den Freeze von „nach Phase B" (5s
Stabilisierung) auf „nach Phase A" (direkt nach Match, SWR noch am
Schwanken) → Snapshot fragiler.

## Geplanter Fix (Mike-Spec final)

Statt EINEN Snapshot → über Fenster **[Dauer-3s, Dauer-1s]** (= Sek. 7-9
bei 10s Tune) den **Median** der gesammelten SWR-Werte nehmen.

### Änderung 1: `_tune_start` — Sammlung initialisieren
```python
import time
self._tune_swr_samples: list[tuple[float, float]] = []  # (elapsed_s, swr)
self._tune_duration_s = duration_s
self._tune_start_time = time.time()
```

### Änderung 2: `_on_meter_update` SWR-Branch — sammeln während TUNE
```python
elif name == "SWR":
    if self.encoder.is_transmitting or self._tune_active:
        self.control_panel.update_swr(value)
    if self._tune_active and hasattr(self, '_tune_start_time'):
        elapsed = time.time() - self._tune_start_time
        self._tune_swr_samples.append((elapsed, value))
```

### Änderung 3: Helper `_compute_match_swr`
```python
import statistics

def _compute_match_swr(self) -> float:
    dur = getattr(self, '_tune_duration_s', 0)
    samples = getattr(self, '_tune_swr_samples', [])
    win_start = max(0.0, dur - 3.0)
    win_end = dur - 1.0
    window = [swr for el, swr in samples if win_start <= el <= win_end]
    if window:
        return statistics.median(window)
    return self.radio.last_swr   # Fallback: alter Snapshot
```

### Änderung 4: `_tune_stop` Z. 268
```python
- swr_after_match = self.radio.last_swr
+ swr_after_match = self._compute_match_swr()
```

### Änderung 5: Diagnose-Logging (debug_log P21-Framework)
```python
from core.debug_log import debug_log
debug_log("TUNE", f"SWR-Fenster [{win_start:.0f}-{win_end:.0f}s] "
                  f"n={len(window)} median={swr_after_match:.2f} "
                  f"last_snapshot={self.radio.last_swr:.2f}")
```

## Relevanter Bestandscode (Auszüge)

`_tune_stop` Z. 267-283:
```python
if token is not None and self.radio.ip:
    swr_after_match = self.radio.last_swr      # ← wird ersetzt
    self._tune_last_valid_swr = swr_after_match
    swr_limit = self.settings.get("swr_limit", 3.0)
    if swr_after_match <= swr_limit:
        self._tune_converged_rf = self._tune_converge_to_target(target_w=10)
    else:
        self._tune_converged_rf = None
else:
    self._tune_converged_rf = None
    self._tune_last_valid_swr = None
```

`_on_meter_update` SWR-Branch Z. 917-931 (P148):
```python
elif name == "SWR":
    if self.encoder.is_transmitting or self._tune_active:
        self.control_panel.update_swr(value)
```

`flexradio.py:1460`: `_last_swr = swr; meter_update.emit("SWR", swr)`
(Anzeige + Snapshot = wertgleich, divergieren nur durch Timing)

`_tune_start` Z. 213-217: Auto-Stop via `QTimer.singleShot(duration_s*1000,
lambda: self._tune_stop(_token))` — Phase A ist passives Warten, sammelt
aktuell NICHTS.

## Architektur-Kontext (wichtig)

- Phase A = `tune_on()` + 10W ANT1 + `duration_s` warten (Default 15s,
  Mike nutzt 10s). Tuner matcht in den ersten Sekunden, dann stabil.
- SWR-Ticks kommen via VITA-49 in `_on_meter_update` (GUI-Thread, Qt
  serialisiert).
- Nach Phase A: SWR-Freeze (DIESER Fix), dann Phase B (Power-Konvergenz,
  nur wenn SWR ≤ Limit), dann tune_off, dann Post-Check (2s).
- P142-Schutz: Cancel während Phase B → `_tune_last_valid_swr = None`
  (Z. 251) bleibt unangetastet.

## Fragen an dich

**F1 (kritisch, Hardware-Sicherheit):** Median über Fenster [Dauer-3s,
Dauer-1s] — ist das die richtige Wahl? Macht es die Bandsperre-Freigabe
robuster (nicht laxer)? Gibt es ein Szenario wo Median fälschlich ein
schlecht-matchendes Band freigibt?

**F2 (Fenster-Grenzen):** [Dauer-3s, Dauer-1s] schließt die letzte Sekunde
aus (Übergang zu tune_off). Sinnvoll? Bei Dauer=10s → [7s, 9s]. Bei
Dauer=15s → [12s, 14s]. Bei sehr kurzer Dauer (z.B. 3s) → win_start=
max(0, 0)=0 → [0s, 2s]. Edge-Case ok?

**F3 (Sample-Rate):** Wie viele SWR-Ticks erwarten wir in 2s? FlexRadio
VITA-49 Meter-Rate ~10 Hz? Wenn nur 1-2 Ticks im Fenster → Median wenig
aussagekräftig. Sollte ich eine Mindest-Sample-Zahl prüfen (z.B. < 3 →
Fallback auf größeres Fenster oder Snapshot)?

**F4 (Threading):** `_on_meter_update` (GUI-Thread) befüllt
`_tune_swr_samples`, `_tune_stop` (auch GUI-Thread, via QTimer) liest sie.
Qt serialisiert → kein Lock nötig? Oder doch defensiv?

**F5 (Memory):** `_tune_swr_samples` wird in `_tune_start` neu angelegt
(alte verworfen). Bei 10s × 10 Hz = 100 Tupel. Vernachlässigbar. Reset ok?

**F6 (Fallback):** Wenn Fenster leer → `radio.last_swr` (alter Snapshot).
Ist das ein sicherer Fallback oder sollte leeres Fenster → Band gesperrt
lassen (konservativer)?

**F7:** Übersehe ich was? Edge-Cases? Soll der Diagnose-Log-Eintrag
anders aussehen?

Hart kritisch, Hardware-Sicherheit hat Vorrang. KISS. „Weiß ich nicht"
statt raten. Mike (Hardware-Experte) hat Median + Fenster 7-9 entschieden
— bitte die UMSETZUNG reviewen, nicht die Entscheidung neu aufrollen,
außer du siehst ein echtes Sicherheits-Problem.
