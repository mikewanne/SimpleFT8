# Feature H — Tertile-Analyse Statistik (kein Datencropping) — V1

**Status:** V1 (Erstentwurf, vor Self-Review).
**Datum:** 2026-05-01.
**Vorgaenger:** v0.83 (commit `28fae84`) — Fix F Auto-Close-Dialog.

---

## 0. Kontext

Aktuell zeigen die Statistik-Diagramme (PDF + PNG) ein "shaded band"
basierend auf MIN und MAX der TÄGLICHEN Mittelwerte pro Stunde
(`scripts/generate_plots.py:_aggregate`, Z.848-866):

```python
daily_means = [sum(v) / len(v) for v in data.get("daily", {}).values() if v]
result[hour] = {
    "mean":       pooled_mean,        # Pooled Mean ueber alle Zyklen
    "min":        min(daily_means) if len(daily_means) > 1 else pooled_mean,
    "max":        max(daily_means) if len(daily_means) > 1 else pooled_mean,
    ...
}
```

**Problem:** bei 1 Tag Daten ist `min == max == pooled_mean` →
Band ist null breit. Bei 2 Tagen ist es ein dünnes Band das nur
zwei Tagespunkte verbindet. → effektiv **Datencropping** —
hunderte Cycle-Werte pro Stunde werden auf 1-2 Tagesmittelwerte
reduziert, dann Min/Max davon genommen.

**Mike's Wunsch (TODO seit Mai 2026):** Tertile-Analyse — alle
Cycle-Werte direkt in 3 Drittel (Tertile) teilen, ohne den Umweg
ueber Tagesmittelwerte. Robuster gegen kleine Datensaetze, kein
Cropping.

---

## 1. Statistische Idee

Tertile = 33.3 % / 66.6 % Perzentile.

Pro UTC-Stunde ALLE Cycle-Werte (=Stationen pro Slot) sortieren →
unteres / mittleres / oberes Drittel:

- **t33** = Wert am 33%-Perzentil
- **t67** = Wert am 67%-Perzentil
- Mittleres Drittel = Slots zwischen t33 und t67 (mittlere
  Häufigkeit der Stationen)

Diagramm-Effekt: shaded band geht von **t33** bis **t67** statt
von min(daily_means) bis max(daily_means). Bei 1 Tag mit 100
Zyklen ist das Band aussagekraeftig (echte Streuung der Slots),
nicht null.

**Pooled Mean (Linie) bleibt unveraendert** — `sum/count` ueber
alle Zyklen.

---

## 2. Aenderungen

### 2.1 `scripts/generate_plots.py:_aggregate` (Z.848-866)

```python
def _aggregate(hour_stats: dict[int, dict]) -> dict[int, dict]:
    """Pooled Mean (alle Zyklen) + Tertile (33%/67%) der Cycle-Werte.

    Ersetzt min/max der Tagesmittel durch Tertile der Einzel-Cycle-
    Werte (= "kein Datencropping"-Variante). Bei 1 Tag Daten zeigt
    das Band echte Slot-zu-Slot-Streuung statt Null-Breite.
    """
    import statistics as _stat
    result = {}
    for hour, data in sorted(hour_stats.items()):
        cycles = data.get("cycles", [])
        if not cycles:
            continue
        pooled_mean = sum(cycles) / len(cycles)
        # Tertile: 33%/67%-Perzentile der einzelnen Cycle-Werte
        if len(cycles) >= 3:
            sorted_c = sorted(cycles)
            t33 = _stat.quantiles(sorted_c, n=3, method="inclusive")[0]
            t67 = _stat.quantiles(sorted_c, n=3, method="inclusive")[1]
        else:
            t33 = t67 = pooled_mean
        daily_means = [sum(v) / len(v) for v in data.get("daily", {}).values() if v]
        minutes = data.get("minutes", set())
        result[hour] = {
            "mean":       pooled_mean,
            "min":        t33,                  # Tertile-Untergrenze
            "max":        t67,                  # Tertile-Obergrenze
            "n_cycles":   len(cycles),
            "n_days":     len(daily_means),
            "coverage":   len(minutes),
        }
    return result
```

**Wichtige Wahl:** ich behalte die Keys `min`/`max` (statt sie
auf `t33`/`t67` umzubenennen) — alle Plot-Funktionen lesen `min`
und `max` weiter, kein Refactor. Semantik aendert sich, Schluessel
nicht.

### 2.2 PDF-Text-Anpassungen (Z.437, 440, 449, 667 etc.)

Heute:
> "{band} {protocol} — line = mean, shaded band = day-to-day variation"

Neu:
> "{band} {protocol} — Linie = Pooled Mean, schraffiertes Band = mittleres Drittel der Slots (33%–67%-Tertile)"

EN:
> "{band} {protocol} — line = pooled mean, shaded band = middle third of slots (33%–67% tertiles)"

Anpassungen in `_TEXTS_DE` und `_TEXTS_EN` Dictionaries (suchen
nach "shaded band", "day-to-day variation", "Tag-zu-Tag-Variation",
"day-to-day").

### 2.3 Bestaetigung im PDF-Methodik-Block

Aktuell beschreibt der PDF-Methodik-Text "Pooled Mean ueber alle
Zyklen". Hinzufuegen: kurze Erklaerung was Tertile sind — 1-2
Saetze.

---

## 3. Akzeptanzkriterien

### A — Funktional

A1. Pooled Mean (Linie) bleibt mathematisch unveraendert.
A2. Min-Wert pro Stunde = 33%-Tertile der Cycle-Werte (statt
    min(Tagesmittel)).
A3. Max-Wert pro Stunde = 67%-Tertile der Cycle-Werte (statt
    max(Tagesmittel)).
A4. Bei 1 Tag mit ≥3 Zyklen: Tertile sind echte Werte, nicht
    Pooled Mean.
A5. Bei < 3 Zyklen pro Stunde: t33 = t67 = pooled_mean (Fallback).
A6. PDF-Texte (DE + EN) reflektieren neue Semantik.

### B — Side-Effect-frei

B1. Plot-Layout (Achsen, Farben, Linien-Stil, Diagramm-Groesse)
    unveraendert. Nur die VALUES im shaded band aendern sich.
B2. PNG-Outputs werden neu generiert (visuell breitere/schmalere
    Baender).
B3. Test-Suite gruen (es gibt aktuell keine generate_plots-Tests,
    Test pure-Logik wird hinzugefuegt).

### C — Robustheit

C1. **Edge-Case 1 Cycle:** `_stat.quantiles` mit `n=3` wirft bei
    1 Datenpunkt `StatisticsError`. Fallback `if len(cycles) >= 3`
    deckt das ab.
C2. **Edge-Case 2 Cycles:** auch < 3, Fallback greift.
C3. **Edge-Case 0 Cycles:** schon heute durch
    `if not cycles: continue`.
C4. **Sehr viele Cycles (~30k):** `_stat.quantiles` ist O(n log n)
    durch sortieren — bei 30k Werten in <100ms. Akzeptabel.

### D — Tests

D1. Neuer Test `test_aggregate_tertiles_with_single_day` —
    1 Tag, 12 Zyklen mit Werten [1..12], erwartet:
    pooled_mean=6.5, t33≈4.something, t67≈9.something (statt 6.5).
D2. Neuer Test `test_aggregate_tertiles_fallback_under_3_cycles` —
    1 Tag, 2 Zyklen, erwartet t33 = t67 = pooled_mean.
D3. Test-Datei: NEU `tests/test_aggregate_tertiles.py` — pure
    Funktions-Tests, kein Plot-Rendering.

---

## 4. Code-Diff-Skizze

`scripts/generate_plots.py:_aggregate` ersetzen wie in 2.1.

PDF-Text-Konstanten anpassen — ich gebe keine kompletten Diffs
hier weil das viele kleine String-Aenderungen sind. R1-Review
soll pruefen ob alle Stellen erwischt sind.

`tests/test_aggregate_tertiles.py` (NEU):

```python
"""Tests fuer scripts.generate_plots._aggregate Tertile-Analyse (Feature H v0.84)."""
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))


def test_aggregate_tertiles_with_single_day():
    """1 Tag, 12 Cycles → Tertile auf Cycle-Ebene, nicht null-breit."""
    from scripts.generate_plots import _aggregate
    hour_stats = {
        12: {
            "cycles": list(range(1, 13)),  # [1, 2, ..., 12]
            "daily": {"2026-05-01": list(range(1, 13))},
            "minutes": set(range(60)),
        }
    }
    result = _aggregate(hour_stats)
    assert 12 in result
    h12 = result[12]
    assert h12["mean"] == 6.5  # (1+12)/2
    # Tertile (33% / 67% von [1..12], inclusive): ca. 4.something / 9.something
    assert 3.5 < h12["min"] < 5.5, f"t33 erwartet ~4.x, war {h12['min']}"
    assert 8.5 < h12["max"] < 10.5, f"t67 erwartet ~9.x, war {h12['max']}"
    assert h12["n_cycles"] == 12


def test_aggregate_tertiles_fallback_under_3_cycles():
    """< 3 Cycles → t33 = t67 = pooled_mean (Fallback)."""
    from scripts.generate_plots import _aggregate
    hour_stats = {
        12: {
            "cycles": [10, 20],
            "daily": {"2026-05-01": [10, 20]},
            "minutes": {0, 30},
        }
    }
    result = _aggregate(hour_stats)
    h12 = result[12]
    assert h12["mean"] == 15.0
    assert h12["min"] == 15.0  # Fallback
    assert h12["max"] == 15.0  # Fallback
```

---

## 5. Frage an R1 (Reviewer)

Du bist Senior-Reviewer. KEIN Code schreiben.

**P1 (statistics.quantiles vs. numpy.percentile):**
`statistics.quantiles(n=3)` gibt 2 Cuts (33% + 67%) zurueck. Mit
`method="inclusive"` ist das vergleichbar mit
`numpy.percentile(arr, [33, 67])`. R1, ist das numerisch identisch
oder gibt es Edge-Cases bei Tie-Werten?

**P2 (Min/Max-Keys behalten oder umbenennen?):** V1-Plan behaelt
Schluessel `min`/`max` mit neuer Semantik. Sauberer waere
`t33`/`t67` mit Anpassung aller Konsumenten. KISS sagt: behalten.
R1, wuerdest du anders entscheiden?

**P3 (PDF-Text-Anpassungen vollstaendig?):** Suche-Strings:
"shaded band", "day-to-day variation", "Tag-zu-Tag-Variation",
"day-to-day". Sind das alle relevanten Stellen oder fehlt was?

**P4 (Datenbasis-Auswertung 40m FT8 reaktiv?):** Heute steht in
HISTORY/CLAUDE.md "+88% / +124% Diversity-Gewinn". Mit Tertile
statt Min/Max der Tagesmittel KÖNNTEN sich die Zahlen leicht
verschieben (Pooled-Mean-Linie ist gleich, aber Band-Breite). Ist
das ein Problem fuer Mike's Statistik-Push-Strategie?

**P5 (Test-Strategie):** Ist `tests/test_aggregate_tertiles.py`
als pure-Logic-Test ausreichend oder sollte ein Smoke-Test fuer
den ganzen `_aggregate`-Pfad mit echten Statistik-Files dazu?

**P6 (eigeninitiativ):** Wenn dir noch was auffaellt — z.B. ob
die Tertile-Wahl statt Quartile (25/75) oder Std-Dev sinnvoll ist
fuer die Zielgruppe Hobby-Funker — nenn es.

---

## 6. Out-of-Scope

- Numpy als neue Dependency (statt `statistics`-Modul) — KISS,
  statistics-Modul hat alles was wir brauchen.
- Konfigurierbare Quantile (Slider 25/33/50%) — ueberkomplex.
- Versionsbump v0.83 → v0.84.

---

## 7. Aufwandsschaetzung

| Schritt | h |
|---|---|
| Code-Aenderung _aggregate (~15 Zeilen) | 0.3 |
| PDF-Text-Anpassungen DE+EN (~10 Strings) | 0.5 |
| Test-Datei (2 Tests) | 0.5 |
| Statistik-Regenerierung + visueller Check | 0.5 |
| HISTORY.md + Commits | 0.3 |
| Final-R1-Codereview | 0.5 |
| **Gesamt** | **~2.5 h** |

---

## 8. Migration / Backwards-compat

- API von `_aggregate` unveraendert (Schluessel min/max bleiben).
- Statistik-Files (`statistics/<Modus>/<Band>/<Proto>/YYYY-MM-DD_HH.md`)
  unveraendert.
- PNG/PDF-Outputs aendern sich visuell — Mike sollte einen Vergleich
  machen vor Push (Statistik-Push-Regel: 5 Tage flaechendeckend).
