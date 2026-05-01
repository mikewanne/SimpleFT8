# Feature H — Tertile-Analyse Statistik (kein Datencropping) — V2

**Status:** V2 (nach Self-Review von V1, vor R1-Review).
**Datum:** 2026-05-01.
**Vorgaenger:** v0.83 (commit `28fae84`) — Fix F.

---

## 0. Kontext

Aktuell: `scripts/generate_plots.py:_aggregate` (Z.848-866) berechnet
pro UTC-Stunde:
- `mean` = Pooled Mean ueber alle Cycle-Werte
- `min` = MIN der TÄGLICHEN Mittelwerte
- `max` = MAX der TÄGLICHEN Mittelwerte

Min/Max werden als "shaded band" in Diagrammen gerendert mit Text
"day-to-day variation".

**Problem:** bei 1 Tag → `min == max == pooled_mean` → Band null
breit. Hunderte Cycle-Werte werden auf 1-2 Tagesmittel reduziert.
Das ist Datencropping.

**Mike's Wunsch (TODO seit Mai 2026):** Tertile-Analyse — alle
Cycle-Werte direkt in 3 Drittel teilen, ohne Umweg ueber
Tagesmittel.

---

## 1. Statistische Idee (verifiziert)

`statistics.quantiles(cycles, n=3, method="inclusive")` liefert
2 Cuts: 33%-Tertile und 67%-Tertile.

**Verifiziert** (Self-Review V1→V2):
```
data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
quantiles(n=3, inclusive) = [4.667, 8.333]
quantiles(n=3, exclusive) = [4.333, 8.667]
mean = 6.5
```

Mit `inclusive`: t33 ≈ 4.67, t67 ≈ 8.33. Wahl `inclusive` weil:
Statistik-Standard fuer "Daten in 3 Bereiche teilen" wo erste/
letzte Datenpunkte zu den Endgrenzen zaehlen.

---

## 2. Aenderungen

### 2.1 `scripts/generate_plots.py:_aggregate` (Z.848-866)

```python
def _aggregate(hour_stats: dict[int, dict]) -> dict[int, dict]:
    """Pooled Mean (alle Zyklen) + Tertile (33%/67%) der Cycle-Werte.

    v0.84 Feature H: ersetzt min/max der Tagesmittel durch Tertile
    der Einzel-Cycle-Werte. Bei 1 Tag mit ≥3 Zyklen zeigt das Band
    echte Slot-zu-Slot-Streuung statt Null-Breite.

    Schluessel-Semantik:
    - mean   = Pooled Mean (unveraendert)
    - min    = 33%-Tertile (NEU: war min der Tagesmittel)
    - max    = 67%-Tertile (NEU: war max der Tagesmittel)
    - Schluessel min/max behalten weil alle Plot-Konsumenten sie
      lesen — Refactor zu t33/t67 ist KISS-violiert (siehe V2 P2).
    """
    import statistics as _stat
    result = {}
    for hour, data in sorted(hour_stats.items()):
        cycles = data.get("cycles", [])
        if not cycles:
            continue
        pooled_mean = sum(cycles) / len(cycles)
        # Tertile: 33%/67%-Perzentile aller Cycle-Werte (kein Cropping)
        if len(cycles) >= 3:
            t33, t67 = _stat.quantiles(cycles, n=3, method="inclusive")
        else:
            t33 = t67 = pooled_mean
        daily_means = [sum(v) / len(v) for v in data.get("daily", {}).values() if v]
        minutes = data.get("minutes", set())
        result[hour] = {
            "mean":       pooled_mean,
            "min":        t33,
            "max":        t67,
            "n_cycles":   len(cycles),
            "n_days":     len(daily_means),
            "coverage":   len(minutes),
        }
    return result
```

### 2.2 PDF-Text-Anpassungen

**Suche-Strings die anzupassen sind** (DE + EN):

| Zeile | Heute | Neu |
|---|---|---|
| ~437 | "shaded band = day-to-day variation" | "shaded band = middle third of slots (33%–67% tertiles)" |
| ~440 | "shaded band shows day-to-day variation — as more days are added, the band will narrow." | "shaded band shows the middle third of slot values per hour (33%–67% tertiles). Even with one day of data, the band reflects real slot-to-slot variation." |
| ~449 | "White error bars show day-to-day variation." | "White error bars show 33%–67% tertile range." |
| ~667 | "The shaded band is wider than on 40m..." | gleicher Text — Aussage bleibt, nur Quelle ist jetzt Tertile statt Tagesmittel |

DE-Aequivalente in `_TEXTS_DE`-Dict suchen und parallel anpassen.

### 2.3 Methodik-Block im PDF (Page 2)

Den existierenden "Pooled Mean"-Erklaerungstext um 1-2 Saetze
erweitern:

> "Das schraffierte Band zeigt das **mittlere Drittel** aller Slot-
> Werte pro Stunde (33%- bis 67%-Tertile). Auch bei nur einem Tag
> Daten ist das Band aussagekraeftig — es zeigt die echte Slot-zu-
> Slot-Streuung statt Tag-zu-Tag-Variation."

EN:
> "The shaded band shows the **middle third** of all slot values per
> hour (33%–67% tertiles). Even with one day of data, the band is
> meaningful — it reflects actual slot-to-slot variation rather
> than day-to-day differences."

---

## 3. Akzeptanzkriterien

### A — Funktional

A1. Pooled Mean (Linie) bleibt mathematisch unveraendert.
A2. `min`-Wert pro Stunde = 33%-Tertile der Cycle-Werte.
A3. `max`-Wert pro Stunde = 67%-Tertile der Cycle-Werte.
A4. Bei 1 Tag mit ≥3 Zyklen: Tertile sind echte Werte, nicht
    Pooled Mean.
A5. Bei < 3 Zyklen pro Stunde: t33 = t67 = pooled_mean (Fallback).
A6. PDF-Texte (DE + EN) reflektieren neue Semantik (mittleres
    Drittel statt Tag-zu-Tag).

### B — Side-Effect-frei

B1. Plot-Layout (Achsen, Farben, Linien-Stil) unveraendert. Nur
    die VALUES im shaded band aendern sich.
B2. PNG-Outputs werden visuell anders (breitere/schmalere
    Baender). Kein Bruch.
B3. Bestehende 510 Tests gruen.

### C — Robustheit

C1. **Edge-Case 1 Cycle:** `_stat.quantiles(n=3)` wirft bei < 2
    Datenpunkten `StatisticsError`. Fallback `len(cycles) >= 3`
    schon defensiver.
C2. **Edge-Case 2 Cycles:** Fallback greift.
C3. **Edge-Case 0 Cycles:** durch `if not cycles: continue` schon
    abgedeckt (Z.853).
C4. **Sehr viele Cycles (~30k):** quantiles ist O(n log n). <100ms.

### D — Tests

D1. NEU `tests/test_aggregate_tertiles.py`:
    - `test_aggregate_tertiles_basic` — 12 Cycles [1..12]:
      pooled_mean=6.5, t33=4.667, t67=8.333.
    - `test_aggregate_tertiles_fallback_under_3` — 2 Cycles:
      t33=t67=pooled_mean.
    - `test_aggregate_tertiles_zero_cycles_skipped` — 0 Cycles:
      Stunde fehlt im Output.
D2. Pure Logic-Tests, kein Plot-Rendering, kein File-IO.

---

## 4. Test-Datei (komplett)

`tests/test_aggregate_tertiles.py`:

```python
"""Tests fuer scripts.generate_plots._aggregate Tertile-Analyse (Feature H v0.84)."""
import sys
from pathlib import Path

PROJ = Path(__file__).parent.parent
sys.path.insert(0, str(PROJ))


def test_aggregate_tertiles_basic():
    """12 Cycles [1..12] → t33=4.667, t67=8.333, pooled_mean=6.5."""
    from scripts.generate_plots import _aggregate
    hour_stats = {
        12: {
            "cycles": list(range(1, 13)),
            "daily": {"2026-05-01": list(range(1, 13))},
            "minutes": set(range(60)),
        }
    }
    result = _aggregate(hour_stats)
    h12 = result[12]
    assert h12["mean"] == 6.5
    # Tertile inclusive aus statistics.quantiles für [1..12]
    assert abs(h12["min"] - 4.6666666) < 0.01, f"t33 erwartet 4.667, war {h12['min']}"
    assert abs(h12["max"] - 8.3333333) < 0.01, f"t67 erwartet 8.333, war {h12['max']}"
    assert h12["n_cycles"] == 12
    assert h12["n_days"] == 1


def test_aggregate_tertiles_fallback_under_3():
    """< 3 Cycles → t33 = t67 = pooled_mean (Fallback gegen StatisticsError)."""
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
    assert h12["min"] == 15.0
    assert h12["max"] == 15.0


def test_aggregate_tertiles_zero_cycles_skipped():
    """0 Cycles → Stunde wird im Output uebersprungen (heute schon so)."""
    from scripts.generate_plots import _aggregate
    hour_stats = {
        12: {"cycles": [], "daily": {}, "minutes": set()},
        13: {"cycles": [5, 5, 5], "daily": {"2026-05-01": [5, 5, 5]}, "minutes": {0}},
    }
    result = _aggregate(hour_stats)
    assert 12 not in result, "leere Stunde muss uebersprungen werden"
    assert 13 in result
    h13 = result[13]
    assert h13["mean"] == 5.0
    assert h13["min"] == 5.0  # alle Werte gleich → t33=t67=5
    assert h13["max"] == 5.0
```

---

## 5. Frage an R1 (Reviewer)

**Du bist Senior-Reviewer, KEIN Code schreiben.**

V2-Spec angehaengt + Code-Files (`scripts/generate_plots.py`).
Antwort fuer P1-P6 mit JA/NEIN/TRADEOFF + Datei:Zeile.

**P1 (`statistics.quantiles` Inclusive vs. Exclusive):**
Mike's Hobby-Kontext, Cycle-Werte sind ganzzahlige Stations-Counts.
`inclusive` und `exclusive` weichen um ~1% ab. Spielt das eine
Rolle oder bin ich paranoid?

**P2 (min/max-Keys behalten oder umbenennen?):** V2-Plan behaelt
Schluessel `min`/`max` mit neuer Semantik. Sauberer waere
`t33`/`t67` mit Anpassung aller Konsumenten (`_hours_x` Z.875-878,
Plot-Funktionen). KISS sagt: behalten. R1, wuerdest du anders
entscheiden? Wo greifen Konsumenten auf `min`/`max` zu?

**P3 (PDF-Text-Anpassungen vollstaendig?):** Ich habe diese
Patterns identifiziert: "shaded band", "day-to-day variation",
"day-to-day", "Tag-zu-Tag", "Tagesvariation". R1, ist das alles
oder fehlt was?

**P4 (Datenbasis-Auswertung 40m FT8 reaktiv?):** Heute steht in
HISTORY/CLAUDE.md "40m FT8: +88% / +124% Diversity-Gewinn".
Pooled-Mean-Linie unveraendert → diese Zahlen bleiben. Aber
Band-Beschreibung aendert sich. Mike's Statistik-Push-Strategie
(5 Tage flaechendeckend) — Aenderung der Band-Semantik vor Push
problematisch?

**P5 (Test-Strategie pure-Logic ausreichend?):** Reicht
`tests/test_aggregate_tertiles.py` mit 3 Tests, oder Smoke-Test
fuer `_aggregate`-Pfad mit echten Statistik-Files dazu?

**P6 (eigeninitiativ):** Wenn dir noch was auffaellt — z.B. ob
Tertile vs. Quartile (25/75) sinnvoller fuer Hobby-Funker, oder
ob ein Boxplot-aehnlicher Ansatz (Median + IQR) praeziser ist —
nenn es.

---

## 6. Out-of-Scope

- Numpy-Dependency.
- Konfigurierbare Quantile-Grenzen.
- Boxplot-Diagramm-Typ statt shaded band.
- Versionsbump v0.83 → v0.84 (in V3 dokumentiert).

---

## 7. Aufwandsschaetzung

~2.5 h (Code 0.3h + PDF-Texte 0.5h + Tests 0.5h + Statistik-
Regenerierung 0.5h + Commits 0.3h + Final-R1 0.5h).

---

## 8. V1 → V2 Self-Review-Diff

1. **Test-Werte korrigiert** — V1 hatte t67-Range 8.5-10.5 (wurde
   nicht treffen, statistik liefert 8.33). V2: exakte Werte mit
   `abs(... ) < 0.01` Tolerance.
2. **Inclusive-Method begruendet** im Plan (war in V1 nur erwaehnt).
3. **Min/Max-Keys-Entscheidung** mit Begruendung dokumentiert
   (KISS — Konsumenten bleiben unveraendert).
4. **0-Cycles-Edge-Case** als dritten Test hinzugefuegt.
5. **PDF-Methodik-Block** explizit erwaehnt (war in V1 nur
   "1-2 Saetze hinzufuegen").
