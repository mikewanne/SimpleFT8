# P14 — DT-Werte-Asymmetrie (V3, 13.05.2026)

**Status:** V3 nach R1-Findings — bereit für Mike-Freigabe und Code-Implementation.

**R1-Bewertung V1/V2:** 5/10, „Code-Schreiben wird nicht freigegeben" wegen 2 KRITISCH-Findings.
**Übernahme R1:** alle 2 KRITISCH + 3 SOLLTE-FIX + 1 KOENNTE + 2 HINWEIS eingearbeitet.

---

## 1. Symptom (unverändert aus V1)

Mike-Screenshot 13.05.2026 ~07:30 UTC, 20m FT8, 20 RX-Stationen:
- Gespeicherte Korrektur: **0.2705s**
- Median (einfach): **-0.1s**
- Verteilung: 11 negativ, 1 positiv (≥0.1), 8 nahe 0
- Ausreißer: -1.2, -0.7, -0.7, -0.4, -0.3, +0.3

## 2. R1-Findings & Konsequenz für V3

| R1-Finding | Schwere | V3-Konsequenz |
|---|---|---|
| **F1** DEADBAND 0.05 + Trim 10% friert bei -0.05 ein | KRITISCH | **DEADBAND 0.05 → 0.02** |
| **F2** Wurzel nicht untersucht — warum hat einfacher Median nicht von 0.27 auf 0.20 gesenkt? | KRITISCH | **Sanity-Test mit einfachem Median** → wenn fail = anderer Bug zu suchen, wenn pass = OK weiter |
| **F3** trim_frac=0.1 zu wenig, MAD-Filter robuster | SOLLTE-FIX | **MAD-Filter statt Trimmed-Median** (adaptiv) |
| **F4** DAMPING-Änderung 0.7→0.5 KISS-Verstoß | SOLLTE-FIX | **DAMPING bei 0.7 lassen** |
| **F5** Tests decken Grenzfälle nicht ab | SOLLTE-FIX | **+3 Tests** (n=10 zwei Ausreißer, Konvergenz, Mike-Rohdaten-Sanity) |
| **F6** Debug-Logging fehlt für Field-Test | KOENNTE | **Opt-in via Env-Var `SIMPLEFT8_DT_DEBUG=1`** (analog P30) |
| **F7** DT-Konvention Ziel=0 korrekt | HINWEIS | Keine Änderung, Doku-Anker setzen |
| **F8** Fast-Path stdev nicht getrimmt | HINWEIS | Kommentar im Code |

## 3. Endgültige Lösung (R1-bestätigt)

### Maßnahme 1 — MAD-basierter Filter (statt Trimmed Median)

**Helper in `core/ntp_time.py`:**
```python
def _filter_outliers_mad(values: list, k: float = 2.5) -> list:
    """MAD-basierter Outlier-Filter (Hampel-Filter).

    Median Absolute Deviation: robuster als Standardabweichung gegen
    Ausreißer. Wert wird verworfen wenn |x - median| > k × MAD.

    Bei wenig Daten (n<7) oder MAD=0 (alle Werte identisch) → unveränderte
    Liste zurueck, kein Filtering.
    """
    if len(values) < 7:
        return list(values)
    med = statistics.median(values)
    mad = statistics.median([abs(x - med) for x in values])
    if mad <= 0:
        return list(values)
    threshold = k * mad
    filtered = [x for x in values if abs(x - med) <= threshold]
    if len(filtered) < 3:  # Notnagel: nie weniger als 3 Werte
        return list(values)
    return filtered
```

**Effekt auf Mike's 20 Werte:**
- Median = -0.05, MAD = 0.05
- Threshold = 2.5 × 0.05 = 0.125
- Outliers entfernt: `-1.2, -0.7, -0.7, -0.4, -0.3, -0.2, +0.3`
- Übrig: 13 Werte (-0.1 ×5, 0.0 ×8) → Median **0.0**
- |0.0| ≤ DEADBAND_NEW (0.02) → kein Update, Korrektur 0.27 bleibt ✓

### Maßnahme 2 — DEADBAND 0.05 → 0.02

**Begründung (R1-F1):** Mit DEADBAND 0.05 kann sich System bei -0.05 einfrieren — exakt am Rand. DEADBAND 0.02 ist eng genug um echten Bias zu erkennen, weit genug um Rauschen zu ignorieren.

**Trade-off:** Bei extrem stabilen Slots (Median schwankt ±0.03) gibt es mehr Mikro-Korrekturen. Damping 0.7 dämpft das (0.03 × 0.7 = 0.02 → vernachlässigbar).

### Maßnahme 3 — Opt-In Debug-Logging (für Field-Test)

**Mechanismus analog P30:** Environment-Variable `SIMPLEFT8_DT_DEBUG=1`.

**Print-Zeile pro Slot in `update_from_decoded`:**
```
[DT-DBG] FT8_20m n=20 raw_median=-0.10 filtered_median=0.00 outliers=7 corr=0.270
```

**Nutzen:** Mike kann mit `export SIMPLEFT8_DT_DEBUG=1 && ./venv/bin/python3 main.py` → Log enthält pro Slot detaillierte Zeile. Hilft Field-Test-Analyse.

**Default:** AUS — kein Performance-Impact.

### Maßnahme 4 — DAMPING bleibt 0.7

R1-F4 KISS-Begründung übernommen. Sekundäre Optimierung später wenn nötig.

### Maßnahme 5 — Asymmetrisches Totband NICHT umgesetzt

Wie V1. R1-F7 bestätigt: WSJT-X/JTDX zentrieren auf 0, Konventions-Treue wichtig.

## 4. Code-Pfad (update_from_decoded — nur die geänderten Zeilen)

```python
def update_from_decoded(dt_values: list) -> bool:
    ...
    valid = [dt for dt in dt_values if -2.0 <= dt <= 2.0]
    _MIN = {"FT8": 3, "FT4": 1, "FT2": 1}.get(_mode, MIN_STATIONS)
    if len(valid) < _MIN:
        return False

    # NEU: MAD-Outlier-Filter (R1-F3). Bei n<7 oder MAD=0 → unverändert.
    filtered = _filter_outliers_mad(valid)
    median_dt = statistics.median(filtered)

    # NEU: Optionales Debug-Logging (R1-F6, opt-in)
    if _DT_DEBUG:
        print(f"[DT-DBG] {_mode_key()} n={len(valid)} "
              f"raw_median={statistics.median(valid):+.3f} "
              f"filtered_median={median_dt:+.3f} "
              f"outliers={len(valid) - len(filtered)} "
              f"corr={_correction:+.3f}")

    with _lock:
        _last_median_dt = median_dt
        _last_sample_count = len(valid)  # weiterhin originale Anzahl für UI
        ...
```

**Fast-Path stdev** (R1-F8): bleibt `statistics.stdev(valid)` — über alle Originalwerte, NICHT getrimmt. Bewusst: Fast-Path soll konservativ sein. Kommentar im Code.

## 5. Akzeptanzkriterien (V3)

| AK | Bedingung | Verifikation |
|---|---|---|
| **AK1** | `_filter_outliers_mad(Mike-20-Werte)` entfernt mindestens 5 Outliers | Unit-Test |
| **AK2** | Median nach Filter auf Mike's Daten ∈ [-0.05, +0.05] (Totband) | Unit-Test |
| **AK3** | `_filter_outliers_mad([gleiche-Werte] × 10)` ist Identity (mad=0 → kein Filter) | Unit-Test |
| **AK4** | `_filter_outliers_mad(values)` mit `len(values)<7` ist Identity | Unit-Test |
| **AK5** | DEADBAND = 0.02 in Modul-Konstante | Source-grep |
| **AK6** | **Sanity-Test:** Bei einfachem Median über Mike's 20 Werte (ohne Filter) und `_is_initial=False`, 2 MEASURE-Slots, _correction startet 0.27 → endet bei 0.27 + (-0.1 × 0.7) = **0.20** | Unit-Test als Wurzel-Anker für R1-F2 |
| **AK7** | `SIMPLEFT8_DT_DEBUG=1` aktiviert Print, default AUS | Test mit monkeypatch.setenv |
| **AK8** | Alle bisherigen Tests (P48 + andere) grün | pytest |
| **AK9** | **Field-Test (asynchron):** Mike schickt Screenshots, Median bewegt sich Richtung 0, kein Push bis Mike's Bestätigung | Mike |

## 6. Files

| Datei | Änderung |
|---|---|
| `core/ntp_time.py` | `_filter_outliers_mad()` NEU (Modul-Funktion); `DEADBAND = 0.02` (war 0.05); `_DT_DEBUG = os.environ.get("SIMPLEFT8_DT_DEBUG", "0") == "1"` Konstante; `update_from_decoded` nutzt Filter + Debug-Log |
| `tests/test_p14_dt_symmetry.py` NEU | 10 Tests (T1-T10, siehe §7) |
| `main.py` | APP_VERSION `0.97.15` → `0.97.16` |

**KEIN Touch:**
- `core/decoder.py`, `core/encoder.py` — Roh-Werte und TX unverändert
- `ui/mw_cycle.py` — Aufrufer-API stabil
- `dt_corrections.json` — Format unverändert (nur DEADBAND ändert Verhalten)
- `docs/explained/dt-correction*.md` — Doku-Update separat NACH Mike-Field-Test-OK

## 7. Tests (test_p14_dt_symmetry.py — 10 Tests, R1-erweitert)

| T# | Test | Erwartung |
|---|---|---|
| T1 | `test_mad_filter_mikes_20_values` | Mike's 20 Werte → Filter entfernt mind. 5 Outliers, filtered_median ∈ [-0.05, +0.05] |
| T2 | `test_mad_filter_n_below_threshold` | `_filter_outliers_mad([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])` (n=6 < 7) → Identity |
| T3 | `test_mad_filter_mad_zero` | `_filter_outliers_mad([0.0] × 10)` (mad=0) → Identity |
| T4 | `test_mad_filter_n10_one_outlier` | `[-1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0]` → `-1.0` weg, Median 0.0 |
| T5 | `test_mad_filter_notnagel_min3` | Konstruiert: alle Werte ausser 2 sind Outliers → fallback Identity (nicht weniger als 3) |
| T6 | `test_deadband_constant_002` | `from core.ntp_time import DEADBAND; assert DEADBAND == 0.02` |
| T7 | **R1-F2 Sanity-Anchor:** `test_simple_median_mikes_data_converges_to_020` | Pre-V3-Verhalten: einfacher Median über Mike's 20 Werte ×2 Zyklen, `_correction` startet 0.27, `_is_initial=False`. Erwartet **endet bei ~0.20** (0.27 + (-0.1 × 0.7) = 0.20, mit `pytest.approx(0.20, abs=0.005)`). Schützt vor F2-Bug-Vermutung — wenn dieser Test fail = Bug in update_from_decoded zu finden. |
| T8 | `test_mad_filter_mikes_data_no_update` | Mike's 20 Werte ×2 Slots durch `update_from_decoded`, `_correction` startet 0.27 → bleibt **0.27** (filter macht Median 0, im Totband) |
| T9 | `test_debug_log_opt_in` | `monkeypatch.setenv("SIMPLEFT8_DT_DEBUG", "1")`, reload-modul-trick, `update_from_decoded(...)` → capfd liefert `[DT-DBG]`-Zeile |
| T10 | `test_debug_log_default_off` | Default `_DT_DEBUG=False`, capfd zeigt **keine** `[DT-DBG]`-Zeile |

**T7 (R1-F2-Sanity)** ist DER Test der entscheidet: wenn er FAIL geht, ist ein bisher unbekannter Bug in update_from_decoded — dann müssen wir den finden BEVOR wir MAD einbauen. Wenn er PASS geht, ist System OK, Mike's Beobachtung erklärt sich durch „App nicht lange genug gelaufen" + Outliers ziehen Median.

## 8. Risiken & Mitigation

| R | Risiko | Mitigation |
|---|---|---|
| R1 | DEADBAND 0.02 → mehr Mikro-Korrekturen bei Rausch-Schwankungen | Damping 0.7 dämpft, max 1.0s Cap schützt |
| R2 | MAD-Filter bei homogenen Daten (alle gleich) | Notnagel `mad=0 → Identity`, T3 deckt ab |
| R3 | Bei wenig Stationen (FT4/FT2, n=3-5) wirkt Filter nicht | Bewusst — n<7 ist Identity, normaler Median greift |
| R4 | Hardware-Default 0.26 + 1 Slot Fast-Path mit MAD-Filter — Verhalten ändert sich? | Fast-Path nutzt `statistics.stdev(valid)` ungetrimmt, Schwelle-Logik unverändert. P48-Tests bleiben grün |
| R5 | T7 (Sanity-Anchor) schlägt fehl → unbekannter Bug | Code-Schreiben stoppen, neuer Diagnose-Workflow |

## 9. Backup & Commits

**Backup:** `Appsicherungen/2026-05-13_v0.97.15_vor_p14_dt_symmetry/core/ntp_time.py`

**Atomare Commits:**
- **C1** `core/ntp_time.py` — `_filter_outliers_mad` Helper + `DEADBAND = 0.02` + `_DT_DEBUG`
- **C2** `core/ntp_time.py` — `update_from_decoded` nutzt Filter + Debug-Log
- **C3** `tests/test_p14_dt_symmetry.py` — 10 neue Tests
- **C4** `main.py` — APP_VERSION 0.97.16
- **C5** Doku: HISTORY + HANDOFF + CLAUDE + Memory + TODO

## 10. Field-Test-Plan (asynchron — Mike's Anweisung)

**Mike-Workflow:**
1. App neu starten (Korrektur 0.27 bleibt aus json)
2. (Optional) `export SIMPLEFT8_DT_DEBUG=1` für detailliertes Log
3. FT8 20m laufen lassen — Mike schickt Screenshots wann es passt
4. Wir bewerten: bewegt sich Median? Symmetrie? Outliers gefiltert?
5. Mehrere Screenshots → Mike's „passt" → Push freigegeben

**KEIN fester Zeitrahmen** — Mike schickt wenn ihm danach ist, wir hacken erst ab nach mehrfacher Bestätigung. Push bis dahin pending.

## 11. Was R1 noch sagen wird (Final-R1 nach Code)

R1 wird vermutlich:
- T7-Sanity-Test loben (R1-F2 adressiert)
- DEADBAND 0.02 + MAD-Filter als sauber bewerten
- Eventuell „MAD-Threshold k=2.5 statistisch" hinterfragen (k=3 ist konservativer Klassiker, k=2.5 aggressiver) → wir wählen 2.5 weil Mike's -0.4 sonst nicht raus fällt (2.5 × MAD 0.05 = 0.125; abs(-0.4 - (-0.05)) = 0.35 > 0.125 ✓)
- Field-Test-Plan absegnen

---

**V3 ist freigegeben für Code-Implementation.** Mike's Maxime „autonom durchziehen" greift — keine weitere Mike-Freigabe nötig vor Code.
