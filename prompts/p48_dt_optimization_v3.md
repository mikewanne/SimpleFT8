# P48 — DT-System aufräumen + tunen (V3)

> **R1-Findings eingearbeitet:** 1 Bug + 2 Risiken + 1 Overengineering +
> 1 Verbesserung angenommen, 1 Hinweis mit Begründung beibehalten,
> 1 Halluzination widerlegt.

---

## Ziel

Vier zusammenhängende Verbesserungen am DT-Korrektur-System:

- **A** — Hardware-spezifische Werte (FlexRadio-TX-Buffer 1.3 s,
  FlexRadio-RX-Hardware-Latenz 0.26 s) in Settings auslagern.
- **B** — Cross-Modus-Fallback: `FT4_<band>` / `FT2_<band>` startet mit
  `FT8_<band>`-Wert (FT8 hat die meisten Stationen → solider Median).
- **C** — Hardware-Default als Kaltstart: statt `0.0` → `0.26 s` aus
  Settings.
- **D** — Schnell-Konvergenz: wenn 1. Mess-Slot ≥10 Stationen mit
  Streuung < 0.1 s → 1 statt 2 Slots warten.

## Hintergrund (empirisch verifiziert)

10.212 DT-Median-Einträge: FlexRadio-RX-Pipeline-Latenz konvergiert über
alle Bänder reproduzierbar auf **+0.26 s ± 0.04 s**.

Aktuell hartverdrahtet: `core/encoder.py:25` `TARGET_TX_OFFSET = -0.8`
und `core/ntp_time.py` Kaltstart-Fallback `0.0`.

## Wichtige Klarstellung — Semantik von `_is_initial`

**R1-Bug-Finding 1 (kritisch, anerkannt):** `_is_initial` wird aktuell
über `saved_val == 0.0` bestimmt (`ntp_time.py:135` + `:151`). Mit
Hardware-Default 0.26 wäre `saved_val != 0.0` → `_is_initial = False` →
**Schnell-Konvergenz (AK6) würde NIE feuern** UND die Erstkorrektur-Logik
in `update_from_decoded:208` ebenfalls nicht.

**Behebung:** `_is_initial` bedeutet jetzt explizit
**„noch keine eigene gemessene Korrektur für diese Mode-Band-Kombi
auf Disk"** — Hardware-Default und Cross-Modus-Fallback zählen NICHT
als eigene Messung.

```python
_is_initial = _saved.get(_mode_key()) is None
```

So bleibt `_is_initial = True` auch wenn `saved_val = 0.26` (vom
Hardware-Default kommt), und Fast-Path + Erstkorrektur-Damping greifen
wie geplant.

## Akzeptanzkriterien

**AK1 — Settings-Block `radio_timing`.**

In `config/settings.py` `DEFAULTS`:

```python
"radio_timing": {
    "tx_buffer_s": 1.3,                    # FlexRadio VITA-49 TX-Buffer
    "rx_hardware_offset_default_s": 0.26,  # FlexRadio RX-Latenz empirisch
},
```

Plus Properties mit defensiver `.get()`-Kette (Backward-Kompat):

```python
@property
def tx_buffer_s(self) -> float:
    return self._data.get("radio_timing", {}).get("tx_buffer_s", 1.3)

@property
def rx_hardware_offset_default_s(self) -> float:
    return self._data.get("radio_timing", {}).get("rx_hardware_offset_default_s", 0.26)
```

**AK2 — `core/ntp_time.py` Hardware-Default-Mechanismus.**

```python
# P48-C: Hardware-Default fuer Kaltstart (von main_window via
# set_hardware_default gesetzt). Default 0.0 fuer Test-Umgebung und
# als Fallback falls Setter nie aufgerufen wird — identisch zu altem
# Verhalten.
_hardware_default_offset: float = 0.0


def set_hardware_default(value_s: float):
    global _hardware_default_offset
    _hardware_default_offset = float(value_s)
```

**AK3 — `_load_for_current_key` mit Cross-Modus + Hardware-Default
(KISS-if-elif).**

R1-Finding 3+4 angenommen: kein Dict, FT8 vor FT4 (FT8-Median solider).

```python
def _load_for_current_key() -> float:
    key = _mode_key()
    val = _saved.get(key, None)
    if val is not None:
        return val
    # Legacy-Migration: alter Schluessel ohne Band
    old_val = _saved.get(_mode, None)
    if old_val is not None:
        print(f"[DT-Korr] Migration: '{_mode}' → '{key}' = {old_val:+.3f}s")
        return old_val
    # P48-B: Cross-Modus-Fallback — Prioritaet FT8 > FT4 (mehr Daten
    # → solider Median). FT8 selber hat keinen Fallback (Master).
    if _mode == "FT2":
        siblings = ["FT8", "FT4"]
    elif _mode == "FT4":
        siblings = ["FT8"]
    else:
        siblings = []
    for sibling_mode in siblings:
        sibling_key = f"{sibling_mode}_{_band}"
        sibling_val = _saved.get(sibling_key, None)
        if sibling_val is not None:
            print(f"[DT-Korr] Cross-Modus-Fallback: '{sibling_key}' "
                  f"({sibling_val:+.3f}s) → '{key}'")
            return sibling_val
    # P48-C: Hardware-Default als Notfall-Kaltstart
    return _hardware_default_offset
```

**AK4 — `_is_initial` neu definieren (Bug-Fix für R1-Finding 1).**

In `set_mode` und `set_band`:

```python
# Vorher: _is_initial = (saved_val == 0.0)
# Neu:    eigene gemessene Korrektur existiert?
_is_initial = _saved.get(_mode_key()) is None
```

Erläuterung im Code als Kommentar:

```python
# P48: _is_initial = "noch keine eigene Messung". Cross-Modus-Fallback
# und Hardware-Default-Werte werden geladen aber ZAEHLEN NICHT als
# eigene Messung (sonst kein Erstkorrektur-Damping und kein
# Schnell-Konvergenz-Pfad).
```

Damit gilt für Schnell-Konvergenz (AK6): `_is_initial = True` auch bei
geladenem Hardware-Default oder Cross-Modus-Wert → Fast-Path kann
greifen.

**AK5 — `main_window.__init__` ruft `set_hardware_default`.**

`ui/main_window.py` in `_init_core_components` vor Encoder-Init:

```python
# P48: Hardware-Default fuer DT-Kaltstart aus Settings setzen
from core import ntp_time as _ntp
_ntp.set_hardware_default(settings.rx_hardware_offset_default_s)
```

**AK6 — Encoder nutzt `tx_buffer_s` aus Settings.**

`core/encoder.py`:

- Modul-Konstante `TARGET_TX_OFFSET = -0.8` (Z.25) **entfernt**.
- `Encoder.__init__`:
  ```python
  def __init__(self, audio_freq_hz: int = 1000,
               tx_buffer_s: float = 1.3):
      super().__init__()
      self.audio_freq_hz = audio_freq_hz
      # P48: TX-Vorlauf = 0.5s WSJT-X-Protokoll - tx_buffer_s Hardware.
      # FlexRadio Default 1.3 → target_tx_offset_s = -0.8 (alter Wert).
      self.target_tx_offset_s = 0.5 - tx_buffer_s
      ...
  ```
- 4 Verwendungen von `TARGET_TX_OFFSET` (Z.312, 345, 352, 358)
  → `self.target_tx_offset_s`.

`ui/main_window.py:144`:
```python
self.encoder = Encoder(1500, tx_buffer_s=settings.tx_buffer_s)
```

**AK7 — Schnell-Konvergenz in `update_from_decoded`.**

```python
if _phase == "measure":
    _measure_buffer.append(median_dt)
    _cycle_count += 1

    # P48-D: Schnell-Konvergenz wenn 1. Slot bereits viele Stationen
    # mit kleiner Streuung hat. Greift NUR bei Kaltstart einer neuen
    # Mode-Band-Kombi (_is_initial = True per AK4-Definition).
    can_fast = (
        _is_initial
        and _cycle_count == 1
        and len(valid) >= _FAST_CONVERGENCE_MIN_STATIONS
        and statistics.stdev(valid) < _FAST_CONVERGENCE_MAX_STDEV
    )
    needed = 1 if can_fast else (
        INITIAL_MEASURE_CYCLES if _is_initial else STEADY_MEASURE_CYCLES
    )

    if _cycle_count >= needed:
        # ... rest unveraendert
```

Modul-Konstanten (im Konfig-Block am Anfang):

```python
_FAST_CONVERGENCE_MIN_STATIONS = 10  # FT8 abends oft 30+, FT4/FT2 selten
_FAST_CONVERGENCE_MAX_STDEV = 0.1    # Stationen alle nahe an gleichem DT
```

R1-Hinweis 6 abgelehnt (Konstanten besser auffindbar als Magic Numbers
für späteres Tuning) — explizite Begründung im Bilanz-Abschnitt.

**AK8 — OMNI-Pretrigger als Followup-Punkt P49.**

`core/omni_cq.py` `_OMNI_PRETRIGGER_OFFSET_S = 1.3` bleibt hartcodiert
in dieser Iteration. In TODO als P49 dokumentiert:

```
| **P49** | OMNI-Pretrigger aus Settings (P48-Followup) | 30min |
```

Bei IC-7300-Fork müsste auch das parametrisiert werden — eigener
Workflow.

**AK9 — Tests `tests/test_p48_dt_optimization.py` (15 Tests).**

`fresh_ntp`-Fixture wie V2 — `conftest.py` schützt `_DT_FILE` automatisch.

- **T1** `test_settings_has_radio_timing_defaults`
- **T2** `test_settings_backward_compat_no_radio_timing_block`
- **T3** `test_load_for_current_key_returns_hardware_default`:
  `_hardware_default_offset = 0.26`, leeres `_saved` → returnt 0.26.
- **T4** `test_cross_mode_ft2_prefers_ft8_over_ft4` (NEU per R1-Finding 4):
  `_saved = {"FT8_30m": 0.27, "FT4_30m": 0.25}`, Modus FT2 → returnt
  0.27 (FT8 hat Priorität).
- **T5** `test_cross_mode_ft2_falls_back_to_ft4_when_no_ft8`
  (NEU per R1-Finding 5): `_saved = {"FT4_30m": 0.25}`, FT8 leer,
  Modus FT2 → returnt 0.25.
- **T6** `test_cross_mode_ft4_uses_ft8`: `_saved = {"FT8_30m": 0.27}`,
  Modus FT4 → 0.27.
- **T7** `test_cross_mode_no_fallback_for_ft8`: `_saved = {"FT4_30m":
  0.27}`, Modus FT8, `_hardware_default_offset = 0.26` → 0.26.
- **T8** `test_cross_mode_prefers_own_value`: `_saved = {"FT2_30m":
  0.29, "FT8_30m": 0.27}`, Modus FT2 → 0.29.
- **T9** `test_encoder_tx_offset_default_flex`:
  `Encoder(1500)` → `target_tx_offset_s == -0.8`.
- **T10** `test_encoder_tx_offset_custom_buffer`:
  `Encoder(1500, tx_buffer_s=1.0)` → `target_tx_offset_s == -0.5`.
- **T11** `test_is_initial_true_with_hardware_default` (NEU per
  R1-Finding 1 — verifiziert dass Bug behoben ist): `_saved = {}`,
  `_hardware_default_offset = 0.26`, `set_mode("FT8", "20m")` →
  `_is_initial == True`, `_correction == 0.26`.
- **T12** `test_is_initial_false_when_own_measurement_exists`:
  `_saved = {"FT8_20m": 0.27}`, `set_mode("FT8", "20m")` →
  `_is_initial == False`.
- **T13** `test_fast_convergence_with_hardware_default` (NEU per
  R1-Finding 2): mit `_hardware_default_offset = 0.26` greift
  `set_mode("FT8", "20m")` (kein eigener Wert, hardware-Default
  geladen, `_is_initial = True`), dann `update_from_decoded([0.0]*12)`
  → `_phase == "operate"` nach 1 Slot (Fast-Path greift).
- **T14** `test_fast_convergence_high_stdev_blocked`: 12 Stationen
  mit Stddev > 0.1 → 1. Slot kein Update, `_phase` bleibt "measure".
- **T15** `test_fast_convergence_few_stations_blocked`: 5 Stationen
  kleine Stddev → wartet auf 2 Slots.

Erwartung: **1175 → 1190** (+15).

**AK10 — Test für `set_hardware_default`-Aufruf in Init (R1-Risiko 10
adressiert):**

Optional, KEIN separater Test — Anti-Pattern wäre Mock-Test der
Importgraph testet. Stattdessen: in V3-Doku explizit dokumentieren
dass der Aufruf in `main_window._init_core_components` vor Encoder-Init
stehen MUSS (siehe AK5 + Risiko-Sektion). Fallback bei
nicht-aufgerufenem Setter ist `0.0` = altes Verhalten (kein
Regression-Risiko).

**AK11 — Gesamtsuite grün.**

Run mit `QT_QPA_PLATFORM=offscreen ./venv/bin/python3 -m pytest tests/ -q`.

## Betroffene Module/Dateien

| Datei | Funktion / Block | Was |
|---|---|---|
| `config/settings.py` | `DEFAULTS` | `radio_timing`-Block |
| `config/settings.py` | Settings-Klasse | 2 Properties |
| `core/ntp_time.py` | Modul-Top | `_hardware_default_offset`, `_FAST_CONVERGENCE_*` |
| `core/ntp_time.py` | Modul-Funktion | `set_hardware_default()` |
| `core/ntp_time.py` | `_load_for_current_key` | if-elif Cross-Modus + Hardware-Default |
| `core/ntp_time.py` | `set_mode` + `set_band` | `_is_initial = _saved.get(_mode_key()) is None` |
| `core/ntp_time.py` | `update_from_decoded` | Schnell-Konvergenz Block |
| `core/encoder.py` | `TARGET_TX_OFFSET` Konst (Z.25) | Entfernen |
| `core/encoder.py` | `Encoder.__init__` | `tx_buffer_s`-Parameter |
| `core/encoder.py` | 4 TARGET_TX_OFFSET-Verwendungen | → `self.target_tx_offset_s` |
| `ui/main_window.py:144` | `_init_core_components` | `set_hardware_default` + `Encoder(tx_buffer_s=...)` |
| `tests/test_p48_dt_optimization.py` | NEU | T1–T15 |

## Randbedingungen

- **KISS:** Module-Var + Setter (nicht Singleton), if-elif statt Dict
  für Cross-Modus, Konstanten bleiben Modul-Level für Tuning-Klarheit.
- **Hardware-Pflicht ANT1=TX unberührt** (nur Buffer-Latenz parametrisiert).
- **Single-Operator-Tool, Mike-only.**
- **Backward-Kompat:** alte Configs identisch, `Encoder(1500)` mit
  Default `tx_buffer_s=1.3` → `target_tx_offset_s = -0.8` (mathematisch
  identisch zum alten Modul-Konstante).
- **`_is_initial`-Semantik geändert** (Bug-Fix R1-Finding 1): jetzt
  „keine eigene Messung", nicht „saved_val=0.0". Erstkorrektur-Pfad
  und Schnell-Konvergenz funktionieren auch mit Hardware-Default 0.26.
- **Cross-Modus-Reihenfolge FT8 > FT4** (R1-Finding 4): FT8 hat in
  Mike's Daten 10k+ Einträge, FT4 nur Hunderte → FT8-Median solider.

## Nicht im Scope

- `_WAKE_OFFSETS` / `_DT_OFFSETS` in Settings.
- OMNI-`_OMNI_PRETRIGGER_OFFSET_S` parametrisieren (→ P49 Followup).
- Self-Adapting Hardware-Default (Mike abgelehnt: too much).
- IC-7300-Fork-Werte.
- DT-Audit-Tool.
- Statistics-Cleanup.

## Geplante Commit-Reihenfolge (atomar)

1. **C1** `config/settings.py` — `radio_timing` + Properties.
2. **C2** `core/ntp_time.py` — `_hardware_default_offset` + Setter +
   `_is_initial`-Bug-Fix + if-elif Cross-Modus-Fallback in
   `_load_for_current_key`.
3. **C3** `core/ntp_time.py` — Schnell-Konvergenz in `update_from_decoded`.
4. **C4** `core/encoder.py` — `tx_buffer_s`-Parameter.
5. **C5** `ui/main_window.py` — `set_hardware_default` + `Encoder(...)`.
6. **C6** `tests/test_p48_dt_optimization.py` NEU (T1–T15).
7. **C7** APP_VERSION 0.97.12 → 0.97.13 + HISTORY + HANDOFF + CLAUDE +
   TODO P48 erledigt + P49 OMNI-Pretrigger als Followup eingetragen +
   Plan-Files.

Backup vor C1:
`Appsicherungen/2026-05-13_v0.97.12_vor_p48_dt_optimization/`.

## R1-Findings-Bilanz (V2 → V3)

| Finding | Schwere | Aktion |
|---|---|---|
| Schnell-Konvergenz feuert nie wegen `_is_initial`-Logik | 🔴 Bug | **Angenommen** — `_is_initial = _saved.get(_mode_key()) is None`. Auch Erstkorrektur-Damping-Pfad profitiert davon. |
| FT2 sollte FT8 vor FT4 priorisieren (FT8-Median solider) | 🟠 Risiko | **Angenommen** — Reihenfolge `["FT8", "FT4"]`. |
| `_SIBLING_PRIORITY`-Dict overengineered | 🟡 Verbesserung | **Angenommen** — if-elif (KISS). |
| Test-Determinismus unter Real-Defaults fehlt | 🟠 Risiko | **Angenommen** — T11+T13 mit `_hardware_default_offset = 0.26`. |
| FT2-Fallback auf FT4 wenn FT8 leer fehlt | 🟢 Verbesserung | **Angenommen** — T5 ergänzt. |
| `_FAST_CONVERGENCE_*` Konstanten Overkill | 🔘 Hinweis | **Beibehalten** — Tuning-Klarheit, nicht Magic Numbers. |
| `_FAST_CONVERGENCE_*` redundant zu `len(valid)` | 🔘 Hinweis | **Beibehalten** — Konstante schafft semantische Trennung. |
| Falscher Kommentar `# P48-C` bei Cross-Modus | 🔘 Hinweis | **Halluzination** — V2 hatte `# P48-B:` korrekt, `# P48-C:` erst beim Hardware-Default. Kein Fix nötig. |
| `set_hardware_default` nie aufgerufen → Init-Reihenfolge | 🟠 Risiko | **Pragmatisch angenommen** — V3 dokumentiert die Pflicht-Reihenfolge in AK5 + Risiko. Fallback `0.0` ist identisch zum alten Verhalten, kein Crash. Mock-Test für Aufruf-Reihenfolge wäre Overkill. |

## Risiko

**MITTEL-LOW.** Bug 1 ist fundamentaler als V2 antizipiert hatte, aber
Fix ist 1 Zeile. Backward-Kompat mathematisch garantiert wenn Settings
auf Defaults. Cross-Modus + Hardware-Default greifen nur bei Kaltstart.
Schnell-Konvergenz greift nur in engem Fenster (≥10 Stationen, Stddev
< 0.1 s, Kaltstart).

**Field-Test (optional, empfohlen):**

1. `dt_corrections.json` leer → App-Start auf 20m FT8 abends → bei
   ≥10 Stationen sollte Korrektur nach **1 Slot** (15 s) greifen,
   `_correction` springt auf ~0.26 s (=Hardware-Default) + Adjust.
2. Bandwechsel auf 30m → Cross-Modus-Fallback aus FT8_30m bei FT2/FT4.
3. TX-Test → DT am Empfänger weiterhin ≈ 0 (TX-Pfad unverändert wenn
   Settings auf Defaults).
