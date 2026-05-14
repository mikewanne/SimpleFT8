# Bundle H — V2 (Self-Review)

**Basis:** `bundle_h_v1.md`

## Findings (Self-Review)

### L1 — `BandpilotManualDialog` funktioniert mit 2 Modi (KEIN Subclass)

Code-grep `ui/bandpilot_dialogs.py:202`:
```python
for mode_code, mean in rec["ranking"]:
    btn = QPushButton(USER_LABEL.get(mode_code, mode_code))
```
Iteriert über Ranking-Länge → 2 Modi = 2 Buttons + Abbruch. DeepSeek
verifiziert. KEIN Subclass nötig.

ABER: Z.195 Hint `f"●  = aktueller Modus (Normal)"` ist irreführend bei
H-Pfad, weil current="normal" NICHT in allowed_modes-Ranking auftaucht
(also kein ●-Marker sichtbar).

**Fix:** Bei H-Pfad `current=None` an Manual-Dialog übergeben →
Hint-Logik anpassen (current=None → Hint ausblenden).
Konstruktor: `def __init__(self, parent, band, utc_hour, rec, current)`.
Wenn current=None → `hint.hide()` oder `current="<keine>"` (siehe Code
für Default-Verhalten).

### L2 — `current_mode`-Tolerance bei allowed_modes

V1-Q1: Bei H-Pfad ist User aktuell Normal, allowed_modes=Div-only →
current_mode="normal" nicht in ranking → recommend_for_hour returnt None.

**Fix-Entscheidung:** in `recommend_for_hour` Spezial-Pfad:
- Wenn `allowed_modes` gesetzt UND `current_mode not in allowed_modes`:
  - Tolerance-Check SKIP (User will eh wechseln)
  - `decision = "switch"`
  - `decision_mode = top1` (Top der allowed_modes)
  - ranking = nur allowed_modes (desc sortiert)

Alternative neue API ist overengineered (1 if-Branch reicht).

### L3 — Refactor inline-Dialog → `_show_diversity_choice_dialog`

mw_radio.py:578-633 (55 Zeilen) extrahieren in eigene Method. Vorteil:
- Wiederverwendbar (off + Mangel-Daten-Pfad)
- Testbar
- KISS — nur Intro-Text als Parameter

### L4 — Toast bei Manual-Path?

V1-Q4: bei manual zusätzlich Toast? Nein — Manual-Dialog IST der
User-Touchpoint. Toast wäre Doppelung. Konsens mit DeepSeek.

### L5 — `_decision_to_scoring` Modul-Function

V1-Q5: Klein, einmalig genutzt → könnte inline sein. Aber Modul-Function
in `core/mode_recommender.py` wäre logischer (ist Bandpilot-Domain).

**Entscheidung:** in `core/mode_recommender.py` als Modul-Function
`code_mode_to_scoring(decision_mode: str) -> str`.

### L6 — `recommend_for_hour` API-Erweiterung Tests

`allowed_modes` braucht Tests:
- T1a: `allowed_modes=None` (Default) → wie heute, 3 Modi
- T1b: `allowed_modes=(Div, DX)` → 2 Modi Ranking
- T1c: `allowed_modes=(Div, DX)` + `current=normal` → Top-1 Div-only
  return mit decision="switch"
- T1d: `allowed_modes=(Div, DX)` + zu wenig Daten in DX → return None

### L7 — Mw_radio Imports erweitern

`from datetime import datetime, timezone` ist in `_maybe_apply_bandpilot`
schon importiert (lokal). Bei H-Pfad in `_on_rx_mode_changed` ebenfalls
lokal importieren (KISS, kein Top-Level-Import).

### L8 — Edge-Case: Bandpilot nicht initialisiert

`self._bandpilot` wird in `main_window.py:351` initialisiert
(`HourlyBandpilot()`). Wenn Bundle H beim `_on_rx_mode_changed` läuft
und `_bandpilot` fehlt: `bp_mode != "off"` triggers `recommend()` →
AttributeError. **Fix:** defensiver `getattr(self, "_bandpilot", None)`-
Check + Fallback auf off-Pfad.

### L9 — `set_rx_mode("normal")` bei Abbruch

V1 setzt `control_panel.set_rx_mode("normal")` bei Dialog-Abbruch.
Aber Mike's `_current_rx_mode_string()` muss konsistent zurück sein.
Pattern wie im inline-Dialog Z.628-630.

### L10 — Field-Test F8 Race-Schutz

V1 erwähnt Pipeline-Lock. Bei H-Pfad ist `_gain_measure_locked`-Check
ganz am Anfang von `_on_rx_mode_changed` (Z.528). Greift bei H auch.
Verifiziert.

## Antworten auf V1-Q's

- Q1: Spezial-Pfad in `recommend_for_hour` für `allowed_modes` +
  `current not in allowed_modes` → Tolerance-Skip + decision="switch"
- Q2: `BandpilotManualDialog` ranking-len-agnostisch, Hint anpassen bei
  current=None
- Q3: `decision`-Feld bleibt — Konsistenz mit Bandwechsel-Pfad
- Q4: Kein Toast bei Manual
- Q5: `code_mode_to_scoring` in `core/mode_recommender.py` (Domain)

## R1-Fragen (V3)

- R1-Q1: `allowed_modes`-Spezial-Pfad in `recommend_for_hour` — sauber
  oder doch neue API?
- R1-Q2: Inline-Dialog-Extraktion mit dynamischem Intro — gibt's
  PySide6-Pitfalls (Memory-Leak bei mehrfach exec()?)
- R1-Q3: Test-Strategie — mit ECHTEM `HourlyBandpilot` (braucht
  statistics/-Daten) ODER Mock?
- R1-Q4: Bundle G Memory-Lesson zu „T8 mit echtem Objekt" — sollte
  Bundle H einen analogen Anker bekommen?
- R1-Q5: Sonstiges?
