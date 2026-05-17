# P69 — Konfidenz-Intervalle für Diversity-Statistiken (V1)

**Stand:** 17.05.2026, autonomer Workflow während Mike unterwegs.
**Ziel:** README-Headline-Aussagen wie „+126%" mit Bootstrap-95%-CI härten.
**Aus TODO P69 (DeepSeek-Vorschlag aus GitHub-Review):** entkräftet
„Hobby-Bullshit-Bingo"-Vorwurf, macht Aussagen wissenschaftlich solide.

## 1. Problem-Definition

**Aktuell:** README zeigt Tabellen wie

| Mode | Stations/15s (Pooled Mean) | vs Normal | Days | Cycles |
|---|---|---|---|---|
| Normal | 18.7 | — | 8 | 7,743 |
| Diversity Standard | 42.2 | **+126%** | 9 | 10,172 |

Der Wert „+126%" ist ein **Punktschätzer ohne Unsicherheits-Aussage**.
Mike's eigener Caveat im README sagt das auch explizit:

> Pooled-mean across all cycles **without** confidence intervals, p-values
> or stratification for solar flux / weather / hour-of-day. 27,200 cycles
> sounds large but the data is **time-autocorrelated** within sessions —
> the effective sample size is much smaller.
>
> Raw data is in `statistics/` (one Markdown file per hour per mode) for
> anyone who wants to run a proper t-test, bootstrap CI, or solar-index
> normalization. I haven't done that work myself.

Das ist ehrlich aber suboptimal — wenn wir die CI nachrüsten, ist die
Aussage hart und der Caveat kann gekürzt werden.

## 2. Methodik-Wahl: Block-Bootstrap nach Stunden

**Standard-Bootstrap (Zyklen-Level)** würde die zeitliche Autokorrelation
ignorieren — innerhalb einer Stunde sind Cycle-Werte stark korreliert
(gleiches Band, gleiche Ausbreitung, oft gleiche Stationen). Resamplet
man Einzel-Zyklen unabhängig, wird die effektive Stichprobengröße
überschätzt und die CIs werden zu eng (zu optimistisch).

**Block-Bootstrap nach (Datum, Stunde)** ist der saubere Mittelweg:
- Jeder Block = alle Cycle-Werte einer konkreten (Datum, Stunde) — sagen
  wir 240 Cycles in einer Mess-Stunde.
- Resampling: aus den N verfügbaren (Datum, Stunde)-Blöcken werden mit
  Zurücklegen N Blöcke gezogen. Pooled Mean berechnen. 1000× wiederholen.
- 95%-CI = 2.5%- und 97.5%-Perzentil der Bootstrap-Verteilung.

Das respektiert die Innerhour-Autokorrelation. Über-Tag-Drift (Solar-Flux
Sprünge) bleibt **unkorrigiert** — das müssen wir im README-Caveat
weiterhin nennen, aber Innerhour ist das größte Problem und das ist gefixt.

**Alternativen verworfen:**
- Naive Bootstrap (Zyklen-Level): unterschätzt CI dramatisch → unehrlich
- Stationary Bootstrap: zu komplex für unsere Datenstruktur (Blöcke sind
  natürlich durch File-Aufteilung definiert)
- t-Test / Welch: setzt Normalverteilung voraus, die wir nicht haben
- Permutation Test: gibt p-Wert, kein CI

## 3. Code-Plan

### 3a. Neue Datenstruktur in `load_hourly_stats`

Aktuell liefert `load_hourly_stats` ein dict `result[hour] = {"cycles":
[...], "daily": {date: [...]}, "minutes": set}`. Die `daily`-Sub-Struktur
liefert genau was wir brauchen: pro (date, hour) eine Liste von Cycle-
Werten = ein Block.

→ Keine Daten-Struktur-Änderung nötig. `daily` wird nur bisher nur für
`n_days` benutzt, wir nutzen es zusätzlich für Bootstrap.

### 3b. Neue Helper-Funktion `compute_bootstrap_ci_diff_pct`

```python
def compute_bootstrap_ci_diff_pct(
    blocks_normal: list[list[int]],
    blocks_compare: list[list[int]],
    n_iter: int = 1000,
    confidence: float = 0.95,
    seed: int | None = 42,
) -> tuple[float, float, float]:
    """Block-Bootstrap-CI für (compare - normal) / normal * 100 %.

    Args:
        blocks_normal: Liste von Cycle-Listen je (date, hour)-Block fuer
                       Normal-Modus.
        blocks_compare: Analog fuer Diversity Standard oder DX.
        n_iter: Bootstrap-Iterationen (Default 1000).
        confidence: CI-Niveau (Default 0.95 → 95 %-CI).
        seed: PRNG-Seed fuer Reproduzierbarkeit.

    Returns:
        (point_estimate_pct, ci_low_pct, ci_high_pct)

    Methodik:
        Pro Iteration:
          1. Resample-with-replacement: ziehe |blocks_normal| Bloecke aus
             blocks_normal und |blocks_compare| Bloecke aus blocks_compare.
          2. Pooled-Mean fuer beide Stichproben berechnen.
          3. Delta-Prozent = (compare_mean - normal_mean) / normal_mean * 100.
        Punktschaetzer = Delta-Prozent ueber die Original-Bloecke (nicht
          ueber Mittelwert der Bootstrap-Verteilung — die ist nur fuer CI).
        CI = [alpha/2, 1-alpha/2] Perzentile der Bootstrap-Verteilung.
    """
```

Pure Funktion, kein I/O, ideal für Tests.

### 3c. Integration in PDF-Bericht

In `generate_plots.py` gibt es Seiten die die 3-Modus-Vergleichs-Tabelle
zeigen (S. 3 laut README-Referenzen). Dort fügen wir eine zusätzliche
Spalte „95 %-CI" hinzu mit dem Wert „+112 % bis +141 %".

Implementierungs-Plan:
- Neue Funktion `compute_mode_comparison_ci(stats_dir, band, protocol)`
  → returnt dict `{"standard": (pt, lo, hi), "dx": (pt, lo, hi)}`
- Aufruf einmalig pro Band+Protokoll (für PDF-Seite + Stats-Helper)
- Tabelle-Renderer erweitert um CI-Spalte

### 3d. README-Tabellen-Update

Die Tabellen in README.md unter „Diversity rescues an off-band antenna —
40m FT8" und den 20m/30m-Sektionen bekommen eine CI-Spalte. Plus der
Methodik-Caveat wird gekürzt: „No confidence intervals" → „95 %-CI via
Block-Bootstrap über (date, hour)-Blöcke (1000 iter, seed 42). Innerhour-
Autokorrelation kontrolliert; Tag-zu-Tag-Drift (Solar-Flux) bleibt
unkorrigiert."

### 3e. README-CQ-DL-Hinweis-Block

Zusätzliche Zeile im neuen CQ-DL-Klarstellungs-Block: „Plus: die im
Artikel genannten Prozent-Werte sind im README jetzt mit 95 %-CIs
ergänzt (Block-Bootstrap)." — entkräftet auch ex-post den fehlenden
CI-Punkt aus dem Artikel.

## 4. Test-Plan

### Unit-Tests (`tests/test_p69_bootstrap_ci.py` NEU)

- **T1**: `compute_bootstrap_ci_diff_pct` mit identischen Blöcken (normal
  == compare) → Punktschätzer ≈ 0 %, CI eng um 0
- **T2**: Mit konstanten Werten (normal = [10], compare = [20]) → Punkt
  = +100 %, CI = [+100 %, +100 %] (kein Sampling-Rauschen möglich)
- **T3**: Seed-Reproduzierbarkeit: gleicher Seed → identisches CI
- **T4**: Unterschiedlicher Seed → leicht andere CI (sonst Bug)
- **T5**: Mit realistischen Daten (Mock 10 Blöcke à 240 Cycles) → CI
  enthält Punktschätzer
- **T6**: Edge-Case: leere Blöcke werden ignoriert
- **T7**: Edge-Case: 1 Block → CI = (pt, pt, pt) (kein sinnvolles
  Resample möglich, Warnung)
- **T8**: Performance: 1000 iter < 1 s für realistische Datenmenge

### Integration-Tests

- **T9**: `compute_mode_comparison_ci` mit echter `statistics/40m`-Daten
  → CI enthält den dokumentierten Punktschätzer 126 %
- **T10**: PDF-Generierung läuft durch ohne Crash

## 5. Aus Scope (NICHT bauen)

- p-Werte / Hypothesen-Tests (kein Mike-Wunsch, KISS)
- Stratifikation nach Solar / Tageszeit
- Autokorrelations-Schätzung über mehrere Tage
- CI für „mit Rescue"-Werte (Rescue ist hourly-aggregiert, nicht cycle-
  level → Block-Bootstrap-Struktur passt nicht direkt)
- Visualisierung der Bootstrap-Verteilung (Histogram im PDF)
- Update der englischen `auswertung.md`-Vorlage (nur Doku)

## 6. Risiken / offene Fragen

- **R1 Performance:** 1000 iter × (~50 Blöcke × 240 Cycles) = 12 M
  Operationen pro CI. Bei 3 Modi-Paaren × 3 Bänder = 9 CIs gesamt → ~100
  M Operationen. Sollte in Python <10 s laufen, eventuell mit numpy
  vektorisieren. Wenn zu langsam: numpy-Variante.
- **R2 Block-Größen-Variabilität:** Blöcke (date, hour) haben unter-
  schiedliche Längen (z. B. 50 vs 240 Cycles). Beim Resampling mit
  Zurücklegen wird das Pooled Mean dadurch leicht verzerrt. Sauberer:
  Cycles vor Pooling alle gleich gewichten. → KISS: ignorieren, der
  Effekt ist <2 % im Vergleich zur Block-Auswahl-Varianz.
- **R3 N=1 Tag pro Block:** Wenn Mike pro Stunde nur 1 Tag gemessen hat,
  reduziert sich Block-Bootstrap effektiv auf Stunden-Bootstrap. Das ist
  immer noch korrekt, nur konservativ.
- **R4 Wann CI sinnvoll?** Wenn nur 2 Tage gemessen wurden, ist jeder
  CI-Wert irreführend. Threshold: mindestens 5 (date, hour)-Blöcke pro
  Modus, sonst Tabellen-Spalte zeigt „n/a" mit Hinweis.

## 7. Workflow-Plan

- V1: dieses Dokument
- V2: Self-Review (Halluzinations-Check, Edge-Cases, Performance-Math)
- R1: DeepSeek-V4-pro Review via `tools/deepseek_review.py`
- V3: aus R1-Findings, kritische Bewertung
- Code: in atomaren Commits
- Tests: T1-T8 vor Integration
- PDF regenerieren + Stichprobe
- README-Tabellen-Update
- Final-R1 V4-pro
- Commit + HISTORY/HANDOFF/CLAUDE/TODO-Update

## 8. Code-Files

- **Neu:** `tests/test_p69_bootstrap_ci.py` (~150 LOC, 10 Tests)
- **Modify:** `scripts/generate_plots.py` (+~100 LOC: Helper + Tabellen-Integration)
- **Modify:** `README.md` (Tabellen-Spalte + Methodik-Caveat-Update)
- **Bump:** `main.py` APP_VERSION 0.97.45 → 0.97.46
