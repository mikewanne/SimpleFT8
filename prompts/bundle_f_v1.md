# Bundle F — V1 (Plan-Entwurf)

**Datum:** 2026-05-14 morgens nach Bundle E
**Trigger:** Mike-Field-Test v0.97.22:
1. OMNI CQ wird nicht mehr gestartet (sendet nichts)
2. Zwei Slot-Balken sichtbar (`cycle_bar` in QSO-Kachel + `_slot_progress_bar`
   in Statusbar). Mike: großen weg, kleinen behalten.
3. Magenta-Farbe für Odd ist „rosa, nix funker-like". Mike: Orange.

**Ziel:** OMNI-Bug fixen (Wurzel im P34-Stufe2-Partial-Fix) + 2 UI-Aufräum-
Arbeiten als gemeinsames Bundle.

---

## Problem 1 — OMNI sendet nicht (KRITISCH)

### Wurzel

`core/omni_cq.py:231-233`:
```python
# V2-L12: kein Senden waehrend Diversity-Mess-Phase
if self._diversity.phase != "operate":
    return
```

P34-Stufe2 (v0.97.19, gestern nachmittag) hat `_phase`-State-Machine aus
`core/diversity.py` komplett entfernt — Mike-Spec „Statik-Pipeline raus".
`DiversityController` hat KEIN `phase`-Attribut mehr.

Zur Laufzeit:
```python
>>> d = DiversityController(timer)
>>> hasattr(d, 'phase')
False
>>> d.phase
AttributeError: 'DiversityController' object has no attribute 'phase'
```

Qt-Slot `on_cycle_start` ist `@Slot(int, bool)`. Qt fängt Exceptions im
Slot **silently** ab (loggt höchstens). OMNI-Pfad bricht bei jedem
Slot-Tick beim Phase-Check ab → kein `encoder.transmit`-Call → kein
TX → `_has_sent_cq=False` bleibt.

**Beweis im Mike-Log (2026-05-14 06:42–06:46, 4 Min Diversity 30m):**
```
06:42:27 [DIV-EN] _enable_diversity scoring=normal
06:42:27 [DYNAMIC] activate -> Buffer leer, Ratio 50:50
06:42:31 [PSK] SKIP — _has_sent_cq=False (noch keine CQ gesendet)
... 4 Min lang KEIN [OMNI-CQ] Log-Eintrag ...
```

### Warum Tests grün waren

Memory-Lesson `feedback_test_critical_path_not_mock.md` (09.05.2026):
„Tests dürfen den kritischen Pfad nicht wegmocken."

Tests die OMNI testen setzen `_diversity_ctrl.phase = "operate"` als
Mock-Attribut auf einem Fake-Diversity (siehe `test_omni_cq_signal.py:40`,
`test_p23_omni_counter.py:47`, `test_p45_omni_stats_guard.py:64`,
`test_p34_elif_chain_intact.py:34`). Mock-Objekte schlucken
`obj.phase = "operate"` einfach (MagicMock oder einfaches Fake-Objekt).
→ Tests grün, Realität kaputt. Klassischer Mock-Antipattern.

### Fix

Phase-Check ersatzlos streichen. Begründung:
- Die ganze Mess-Phase-Logik existiert nicht mehr (P34-Stufe2).
- Während Gain-Messung (DXTuneDialog) ist die UI modal-blockiert → OMNI
  kommt sowieso nicht durch (`btn_omni_cq` nicht klickbar weil über UI
  gesperrt).
- KISS: wenn Mess-Phase je zurückkommt, kommt sie als eigener Check zurück.

```python
# core/omni_cq.py:228-234 VORHER:
if not self._active or self._paused:
    return

# V2-L12: kein Senden waehrend Diversity-Mess-Phase
if self._diversity.phase != "operate":
    return

# V2-L9 Fresh-Compute is_even — robust gegen Signal-Latenz
slot_dur = self._timer.cycle_duration
fresh_is_even = (int(time.time() / slot_dur) % 2 == 0)

# NACHHER:
if not self._active or self._paused:
    return

# V2-L9 Fresh-Compute is_even — robust gegen Signal-Latenz
slot_dur = self._timer.cycle_duration
fresh_is_even = (int(time.time() / slot_dur) % 2 == 0)
```

### Test-Anpassungen

1. `tests/test_omni_cq_signal.py`:
   - `_make_omni(..., diversity_phase=...)`-Parameter raus
   - `diversity.phase = diversity_phase`-Setter raus
   - T5 (AC5) „on_cycle_start no-op wenn diversity.phase != 'operate'"
     komplett LÖSCHEN (testet obsolete Logik)
2. `tests/test_p23_omni_counter.py`: gleicher Parameter raus
3. `tests/test_p45_omni_stats_guard.py:64`: Zeile raus
4. `tests/test_p34_elif_chain_intact.py:34`: Zeile raus
5. NEU **T-Bug-Schutz** in `test_bundle_f.py`:
   - `DiversityController` hat KEIN `phase`-Attribut (Source-grep)
   - `on_cycle_start` ruft `encoder.transmit` bei aktivem OMNI + matched
     parity OHNE auf `diversity.phase` zuzugreifen (echter
     `DiversityController` statt MagicMock)

---

## Problem 2 — Doppelter Slot-Balken

### Wurzel

Zwei unabhängige Anzeigen:
- **Alt (großer „8s"-Balken):** `cycle_bar` (QLabel mit Unicode-Block-
  Zeichen + Sekunden-Text) im STATUS-Block der QSO-Card. Existiert seit
  langem, Definition `ui/control_panel.py:1150-1156`, Update-Methode
  `update_cycle_bar()` Z.1947-1957, Caller `mw_cycle.py:519`.
- **Neu (kleiner Balken in Statusbar):** `_slot_progress_bar` (QProgressBar
  80×14 px). Bundle D (v0.97.21) hinzugefügt. Sollte den alten ablösen,
  aber alter wurde nicht entfernt.

Mike-Wunsch: alten weg, neuen behalten.

### Fix

Alle `cycle_bar`-Referenzen löschen:
1. `ui/control_panel.py:1150-1156` — `QLabel` Definition + `addWidget` raus
2. `ui/control_panel.py:1336` — `self.cycle_bar = qso_card.cycle_bar`
   Alias raus
3. `ui/control_panel.py:1947-1957` — `update_cycle_bar()`-Methode raus
4. `ui/mw_cycle.py:519` — `self.control_panel.update_cycle_bar(...)`-
   Aufruf raus

### Test-Anpassungen

- Tests die `cycle_bar`-Existenz prüfen → grep `tests/` nach `cycle_bar`,
  alle löschen oder anpassen
- NEU **T-Layout-Verifikation:** ControlPanel hat KEIN `cycle_bar`-
  Attribut mehr nach Bundle F.

---

## Problem 3 — Rosa-Farbe ist „nix funker-like"

### Wurzel

`ui/main_window.py:500` (Initial-Style) und `:1269` (Update-Logik):
```python
chunk = "#00CCFF" if is_even else "#FF66CC"  # cyan / magenta
```

`#FF66CC` ist Magenta/Rosa.

### Fix

`#FF66CC` → `#FFAA00` (Orange).

- Z.500 Initial-Style — Cyan bleibt, kein Effekt hier (Start ist Even)
- Z.1269 — Magenta-Konstante → Orange
- Tooltip Z.495 anpassen: „Cyan = Even, Magenta = Odd" → „Cyan = Even,
  Orange = Odd"
- Kommentar Z.486: „Cyan (Even) / Magenta (Odd)" → „Cyan (Even) / Orange (Odd)"
- Docstring Z.1253: gleicher Replacement
- Konstantenname-Kommentar Z.1269 „cyan / magenta" → „cyan / orange"

### Test-Anpassungen

Wenn Tests die Farbe asserten (z.B. Bundle-D T3):
- Magenta-String → Orange-String tauschen

---

## Backup-Plan

`Appsicherungen/2026-05-14_v0.97.22_vor_bundle_f/` mit:
- `core/omni_cq.py`
- `ui/control_panel.py`
- `ui/main_window.py`
- `ui/mw_cycle.py`
- alle Test-Dateien die geändert werden

## Atomare Commits (geplant)

| C | Datei(en) | Inhalt |
|---|---|---|
| C1 | `core/omni_cq.py` | Phase-Check raus |
| C2 | tests/test_omni_cq_signal.py, test_p23_omni_counter.py, test_p45_*.py, test_p34_elif_chain_intact.py | Mock-Phase-Setter raus, T5 löschen |
| C3 | `ui/control_panel.py` + `ui/mw_cycle.py` | cycle_bar weg |
| C4 | `ui/main_window.py` | Magenta → Orange |
| C5 | tests/test_bundle_f.py NEU | OMNI no-phase, cycle_bar gone, color orange |
| C6 | tests/test_bundle_d.py | Color-Assertion update (falls vorhanden) |
| C7 | APP_VERSION 0.97.22 → 0.97.23 + HISTORY/HANDOFF/CLAUDE-Header |

## Test-Bilanz

- 1179 (Bundle E)
- −1 (T5 in test_omni_cq_signal.py „phase != operate" gelöscht)
- +X (Bundle F neue Tests T1-Txx in test_bundle_f.py)

Erwartung: ~1185–1190 grün.

## Field-Test F1-F5

| # | Test | Erwartung |
|---|---|---|
| **F1** | Diversity Std/DX, OMNI klicken | OMNI sendet sofort (CQ-Zeile in QSO-Panel) |
| **F2** | OMNI laufen lassen 30 Min | Counter-Display ↻N läuft, Paritäts-Flip funktioniert |
| **F3** | QSO-Kachel STATUS-Block | Kein „8s"-Balken mehr |
| **F4** | Statusbar unten rechts | Kleiner Balken, wechselt **Cyan→Orange** beim Slot-Wechsel |
| **F5** | OMNI während Gain-Mess klicken (sollte UI-blockiert sein) | Klick ohne Effekt (DXTuneDialog modal) |

## Offene Fragen für V2-Self-Review

- Q1: Soll Phase-Check ersatzlos raus oder durch `_gain_measure_locked`-
  Check ersetzt werden? (DXTuneDialog ist modal — aber DXTuneDialog ist
  NICHT der einzige Mess-Pfad. Was passiert wenn OMNI während eines
  zukünftigen Auto-Tune läuft?)
- Q2: `cycle_bar` Tests — gibt es überhaupt welche? Wenn nein, einfach
  löschen.
- Q3: `_slot_progress_bar` Tests in Bundle D — Color-Assertion vorhanden?
- Q4: Sollten wir Orange für Odd auch im OMNI-Counter/Indicator
  einheitlich verwenden, oder ist das eigene Sub-Farbgruppe?
- Q5: `cycle_bar` ist QLabel mit Background — entfernt zu werden ist
  trivial, aber gibt es Tests die das Vorhandensein prüfen?
- Q6: APP_VERSION bump auf 0.97.23 oder 0.98.0? (3 Fixes inkl.
  kritischem OMNI-Bug → eher 0.97.23 patch).
- Q7: Backup-Verzeichnis-Name korrekt? `2026-05-14_v0.97.22_vor_bundle_f/`?
