# P69 — V3 (final, nach R1-V4-pro)

## R1-Findings-Bewertung

| ID | Klassifikation | Bewertung | Aktion |
|---|---|---|---|
| F-DIV0 | 🔴 ROT | Annehmen | Resample verwerfen wenn `normal_mean == 0` |
| F-RATIO1 | 🟠 ORANGE | Annehmen (Variante B) | Percentile-CI behalten, präziser Caveat + Threshold |
| F-THRESHOLD | 🟠 ORANGE | Annehmen | n < 15 → „n/a", 15 ≤ n < 25 → „limited", n ≥ 25 → normal |
| F-ITER | 🟡 GELB | Annehmen | 1000 → 5000 (wenn Performance < 2s bleibt) |
| F-TEST-DATA | 🟡 GELB | Annehmen | Fixture-Daten in `tests/data/p69_fixture/` |
| F-CAVEAT-LANG | 🟡 GELB | Annehmen | DeepSeek-Wortlaut übernehmen |
| H-RATIO-JENSEN | ⚪ Hinweis | Ablehnen | Würde Verwirrung stiften |
| H-BLOCKGRÖSSE | ⚪ Hinweis | Akzeptanz | Kein Action-Item |

## Begründung für „Variante B" bei F-RATIO1 (BCa nicht implementieren)

DeepSeek schlägt BCa (bias-corrected and accelerated) als alternative
Methode vor. Argumente dagegen:

1. **Datenmenge:** Bei n ≥ 25 Blöcken und 5000 Iterationen ist Percentile-
   Bias < 1 % im Vergleich zur Block-Auswahl-Varianz — praktisch
   irrelevant.
2. **Threshold-Schutz:** F-THRESHOLD-Schwelle „n < 15 → n/a" schließt
   genau die Fälle aus in denen Bias relevant wäre.
3. **KISS:** BCa braucht Jackknife für acceleration parameter →
   Implementierung 2× komplexer, Tests aufwändiger.
4. **Mike's Zielgruppe:** Hobby-Funker, keine Statistiker. Ein
   Percentile-CI mit klarem Caveat ist verständlicher als BCa.
5. **TODO P69b einrichten** als Folge-Idee: „BCa-CI für Edge-Case n < 25"
   — wenn Mike will, kann ich das später nachziehen.

## V3 finale Spec

### V3.1 — `compute_bootstrap_ci_diff_pct` Funktionssignatur

```python
def compute_bootstrap_ci_diff_pct(
    blocks_normal: list[list[int]],
    blocks_compare: list[list[int]],
    n_iter: int = 5000,
    confidence: float = 0.95,
    seed: int | None = 42,
) -> tuple[float, float, float, str]:
    """Block-Bootstrap-CI fuer (compare - normal) / normal * 100 %.

    Args:
        blocks_normal: Liste von Cycle-Listen je (date, hour)-Block fuer Normal.
        blocks_compare: Analog fuer Diversity Standard oder DX.
        n_iter: Bootstrap-Iterationen (Default 5000, R1-F-ITER).
        confidence: CI-Niveau (Default 0.95 -> 95 %-CI).
        seed: PRNG-Seed fuer Reproduzierbarkeit (Default 42).

    Returns:
        (point_estimate_pct, ci_low_pct, ci_high_pct, quality_flag)
        quality_flag in {"ok", "limited", "insufficient"}:
            - n_min := min(len(blocks_normal), len(blocks_compare))
            - n_min >= 25         -> "ok"
            - 15 <= n_min < 25    -> "limited"
            - n_min < 15          -> "insufficient" + (nan, nan, nan, "insufficient")

    Methodik:
        1. Filter: leere Bloecke (n_cycles == 0) werden ignoriert.
        2. Punktschaetzer: Pooled Mean ueber alle Cycles aller Original-
           Bloecke (matcht _combo_summary_fair-Logik).
        3. Pro Iteration:
           - Resample-with-replacement: ziehe N_n Bloecke aus blocks_normal
             und N_c Bloecke aus blocks_compare (jeweils mit Zuruecklegen).
           - Pooled Mean = sum(all_cycles) / count(all_cycles) ueber alle
             Cycles aller gezogenen Bloecke.
           - delta_pct = (compare_mean - normal_mean) / normal_mean * 100
           - **F-DIV0:** Wenn normal_mean == 0 -> Resample verwerfen, neu
             ziehen. Wenn nach 10 Versuchen kein gueltiges Resample -> Abbruch
             mit ValueError (statistisch dann eh unsinnig).
        4. CI = [alpha/2, 1-alpha/2] Perzentile der Bootstrap-Verteilung.

    Unabhaengigkeit:
        Beide Modi werden unabhaengig resampelt (kein paired-bootstrap),
        weil Messungen sequenziell pro Modus laufen, nicht parallel.
    """
```

### V3.2 — `compute_mode_comparison_ci` Wrapper

```python
def compute_mode_comparison_ci(
    stats_dir: Path,
    band: str,
    protocol: str = "FT8",
    n_iter: int = 5000,
) -> dict[str, tuple[float, float, float, str]]:
    """Bootstrap-CI fuer Diversity Standard und DX gegen Normal.

    Returns dict {"Diversity_Normal": (pt, lo, hi, flag),
                  "Diversity_Dx": (pt, lo, hi, flag)}.

    Liest Daten via load_hourly_stats, extrahiert (date, hour)-Bloecke
    aus dem daily-Sub-dict, ruft compute_bootstrap_ci_diff_pct.
    """
```

### V3.3 — README-Caveat (F-CAVEAT-LANG)

Ersetzt den aktuellen Caveat-Block (Z. 204-219 im README):

> **Methodology** (Block-Bootstrap with 95 % confidence intervals)
> - Percentile-Block-Bootstrap (5000 iterations, independent resampling
>   per mode) over (date, hour) blocks. This controls intra-hour
>   autocorrelation between adjacent cycles.
> - **Day-to-day drift and dependencies between hours of the same day
>   remain unmodeled** — the 95 % intervals are therefore a **lower
>   bound on true uncertainty**, especially for modes with fewer than
>   25 (date, hour) blocks (CI flag: "limited" in PDF report).
> - **Paired tests are not applicable** because modes are measured
>   sequentially across the day, not in parallel.
> - Cycles per block vary (50-240 typical) — Pooled Mean weights by
>   measurement duration, consistent with `_combo_summary_fair` in
>   `scripts/generate_plots.py`.
> - Raw data in `statistics/` allows alternative analyses (hierarchical
>   bootstrap, BCa, solar-flux stratification).

### V3.4 — Test-Plan (F-TEST-DATA)

Fixture-Daten in `tests/data/p69_fixture/` mit 20 konstruierten Blöcken:
- Normal: 20 Blöcke à konstant 5 Cycles, Werte gleichverteilt um 10
- Compare: 20 Blöcke à konstant 5 Cycles, Werte gleichverteilt um 20

Erwartung: Punktschätzer ≈ +100 %, CI eng (z. B. [+95 %, +105 %]).

Tests:
- **T1**: identische Blöcke (normal == compare) → CI eng um 0 %
- **T2**: konstante Werte (normal = [[10]*5]*N, compare = [[20]*5]*N) →
  Punkt = +100 %, CI = [+100 %, +100 %] (deterministisch)
- **T3**: Seed-Reproduzierbarkeit (gleicher Seed → identische CI)
- **T4**: Unterschiedlicher Seed → leicht andere CI
- **T5**: Fixture-Daten → CI ist plausibel (Bandbreite, Punktschätzer
  enthalten)
- **T6**: Leere Blöcke werden ignoriert
- **T7**: n_min < 15 → quality_flag == "insufficient", (nan, nan, nan)
- **T8**: 15 <= n_min < 25 → quality_flag == "limited"
- **T9**: n_min >= 25 → quality_flag == "ok"
- **T10**: F-DIV0 — Normal-Blöcke mit Werten = 0 → no crash,
  ValueError wenn alle Resamples invalid
- **T11**: Performance — Fixture-Daten 1× CI < 2.0 s
- **T12**: `compute_mode_comparison_ci` mit Fixture-statistics-Tree:
  läuft durch, gibt dict mit korrekten Keys

### V3.5 — PDF-Integration

`_r_ergebnisse_page` (Z. 1460) wird erweitert:
- Spalte „95 %-CI" zwischen „vs Normal" und „+ Rescue"-Spalte
- Format: `+112-141%` für Diversity Standard, `n/a` bei „insufficient",
  `+112-141% (limited)` bei „limited"
- Tabelle bleibt 7 Spalten breit, „vs Normal" wird zu „vs Normal (95 % CI)"
  mit zwei Zeilen pro Cell („+126%" über „+112-141%")

### V3.6 — `print_ci_for_readme.py` (F7 aus V2)

Separates Helper-Skript in `scripts/`:

```python
"""Druckt fertige Markdown-Tabellen-Zeilen mit CI fuer README-Update.

Aufruf: ./venv/bin/python3 scripts/print_ci_for_readme.py
"""
```

Ausgabe pro Band: 1 Block mit DE+EN-Tabellen-Zeilen.

### V3.7 — APP_VERSION

0.97.45 → 0.97.46 (Patch-Bump, neue Stats-Feature).

### V3.8 — Files

- **Neu:** `scripts/bootstrap_ci.py` (~120 LOC) — die zwei Funktionen
  isoliert, importierbar von `generate_plots.py` und Tests
- **Neu:** `scripts/print_ci_for_readme.py` (~50 LOC)
- **Neu:** `tests/test_p69_bootstrap_ci.py` (~250 LOC, 12 Tests)
- **Neu:** `tests/data/p69_fixture/` (3 Dateien für Mock-stats-Tree)
- **Modify:** `scripts/generate_plots.py` (+~50 LOC: PDF-Tabelle erweitert)
- **Modify:** `README.md` (CI-Spalte in 6 Tabellen, Caveat-Block)
- **Modify:** `main.py` APP_VERSION 0.97.45 → 0.97.46

### V3.9 — Atomare Commits

1. **C1:** `scripts/bootstrap_ci.py` NEU mit Doc-Strings (kein Test
   noch, nur Algorithmus)
2. **C2:** `tests/test_p69_bootstrap_ci.py` NEU + `tests/data/p69_fixture/`
3. **C3:** `scripts/generate_plots.py` PDF-Integration
4. **C4:** `scripts/print_ci_for_readme.py` NEU
5. **C5:** README.md CI-Spalte + Caveat
6. **C6:** main.py APP_VERSION-Bump + HISTORY/HANDOFF/CLAUDE/TODO-Update

### V3.10 — Field-Test (post-implementation)

Field-Test entfällt — radio-frei. Stattdessen:
- F1: PDF wird neu generiert, alle 3 Bänder-Seiten sehen plausibel aus
- F2: print_ci_for_readme.py-Output ist menschenlesbar
- F3: README rendert in GitHub-Markdown-Preview korrekt
