# Feature H — Tertile-Analyse Statistik — V3

**Status:** V3 (nach R1-Review von V2, Mike-Freigabe vorab erteilt).
**Datum:** 2026-05-01.
**Vorgaenger:** v0.83 (commit `28fae84`) — Fix F.

---

## R1-Bilanz V2 → V3

| Frage | R1-Antwort |
|---|---|
| P1 inclusive vs. exclusive | NEIN — paranoid, ~1% Abweichung egal |
| P2 min/max-Keys behalten | TRADEOFF — kein Konsument heute, KISS OK |
| P3 PDF-Texte vollstaendig | JA — alle Patterns gefunden |
| P4 Push-Strategie | TRADEOFF — Methodenwechsel im Push-Text erwaehnen |
| P5 Test-Strategie | JA — pure-Logic-Tests reichen |
| **P6 KRITISCH** | **shaded band wird gar nicht gezeichnet — Feature waere unsichtbar!** + `daily_means`-Berechnung obsolet |

**R1's BLOCKER:** `_hours_x` liefert `mins`/`maxs` aber kein
`fill_between` ist im Plot-Code → Feature waere reines Berechnen
ohne sichtbaren Effekt.

→ V3 erweitert: `create_stations_diagram` bekommt `fill_between`
fuer shaded band. `daily_means`-Zeile entfernt, `n_days` direkt
aus `data["daily"]`-Dict-Laenge.

---

## 1. Aenderungen (final)

### 1.1 `scripts/generate_plots.py:_aggregate` (Z.848-866)

```python
def _aggregate(hour_stats: dict[int, dict]) -> dict[int, dict]:
    """Pooled Mean (alle Zyklen) + Tertile (33%/67%) der Cycle-Werte.

    v0.84 Feature H: ersetzt min/max der Tagesmittel durch Tertile
    der Einzel-Cycle-Werte. Bei 1 Tag mit ≥3 Zyklen zeigt das Band
    echte Slot-zu-Slot-Streuung statt Null-Breite.
    """
    import statistics as _stat
    result = {}
    for hour, data in sorted(hour_stats.items()):
        cycles = data.get("cycles", [])
        if not cycles:
            continue
        pooled_mean = sum(cycles) / len(cycles)
        if len(cycles) >= 3:
            t33, t67 = _stat.quantiles(cycles, n=3, method="inclusive")
        else:
            t33 = t67 = pooled_mean
        # daily_means-Berechnung entfernt (R1-P6: obsolet seit
        # min/max aus Tertilen kommen). n_days direkt aus Dict-Laenge.
        n_days = sum(1 for v in data.get("daily", {}).values() if v)
        minutes = data.get("minutes", set())
        result[hour] = {
            "mean":       pooled_mean,
            "min":        t33,
            "max":        t67,
            "n_cycles":   len(cycles),
            "n_days":     n_days,
            "coverage":   len(minutes),
        }
    return result
```

### 1.2 `scripts/generate_plots.py:create_stations_diagram` (Z.978-1052)

NEU: `fill_between` direkt nach der Mean-Linie:

```python
        color = COLORS[rx_mode]
        ax.plot(xs, means, color=color, label=label, linewidth=2.5, zorder=3)
        # +++ NEU v0.84 Feature H: shaded band = 33%-67%-Tertile
        ax.fill_between(xs, mins, maxs, color=color, alpha=0.15, zorder=2)
        has_data = True
```

`fill_between` mit `alpha=0.15` ist dezent und vermischt sich nicht
mit anderen Modi. `zorder=2` legt das Band hinter die Linien
(`zorder=3`) damit Linien weiterhin sichtbar bleiben.

### 1.3 PDF-Text-Anpassungen (V2-Sektion 2.2 unveraendert)

R1-P3 bestaetigt: alle Patterns sind in `TEXTS_DE`/`TEXTS_EN`
abgedeckt (Z.~437, 440, 449, 667).

### 1.4 Tests bleiben wie V2 (`tests/test_aggregate_tertiles.py`)

3 Pure-Logic-Tests fuer `_aggregate`. R1-P5: ausreichend.

---

## 2. Akzeptanzkriterien (final)

A1-A6 wie V2.

**NEU A7:** `create_stations_diagram` rendert das shaded band
zwischen `mins` und `maxs` mit alpha=0.15. Visuell sichtbar bei
allen 3 Modi (Normal, Diversity Std, Diversity DX) in
unterschiedlichen Farben.

**NEU A8:** PDF-Bericht regeneriert ohne Fehler.

---

## 3. Atomare Commits (geplant)

1. `feat(plots): _aggregate Tertile (33%/67%) statt Min/Max der Tagesmittel`
   — generate_plots.py + tests/test_aggregate_tertiles.py
2. `feat(plots): shaded band in create_stations_diagram aktivieren`
   — generate_plots.py
3. `chore(plots): PDF-Texte DE+EN auf Tertile-Semantik anpassen`
   — generate_plots.py (TEXTS-Dicts)
4. `chore(release): v0.84 — Tertile-Analyse Statistik (Feature H)`
   — main.py + HISTORY.md + HANDOFF.md + CLAUDE.md + prompts

---

## 4. Lessons-V3

R1's P6 zeigt: bei Statistik-/Plot-Code ist End-to-End-Verifikation
wichtig. Pure Berechnung-Tests sagen NICHT, ob die Werte tatsaechlich
GEZEICHNET werden. R1 hat den toten Code-Pfad gefunden, den ich
nicht gesehen haette ohne Final-Codereview.

Mike's PFLICHT-Workflow erneut bestaetigt: auch bei "nur Statistik"
findet R1 architektonische Luecken.
