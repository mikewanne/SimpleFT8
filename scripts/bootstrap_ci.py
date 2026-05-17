"""Block-Bootstrap-Konfidenz-Intervalle fuer Diversity-Mode-Vergleiche.

Verwendet in `scripts/generate_plots.py` (PDF-Tabelle Seite 3) und
`scripts/print_ci_for_readme.py` (README-Tabellen-Update).

Methodik (P69, V3 nach R1-V4-pro):
- Block-Bootstrap nach (date, hour)-Blöcken über cycle-level Daten.
- 5000 Iterationen, Percentile-CI, Seed=42 für Reproduzierbarkeit.
- Unabhängiges Resampling pro Modus (kein paired-bootstrap).
- Punktschätzer: Pooled Mean über alle Cycles (matcht
  `_combo_summary_fair` in generate_plots.py).
- Threshold:
    n_min >= 25 -> "ok"
    15 <= n_min < 25 -> "limited"
    n_min < 15 -> "insufficient" + (nan, nan, nan, "insufficient")

Caveats:
- Tag-zu-Tag-Drift bleibt unmodelliert (CIs sind untere Schranke der wahren
  Unsicherheit).
- Paired Tests nicht anwendbar (Modi sequenziell gemessen).
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Callable


DEFAULT_N_ITER = 5000
DEFAULT_CONFIDENCE = 0.95
DEFAULT_SEED = 42

THRESHOLD_OK = 25
THRESHOLD_LIMITED = 15

MAX_DIV0_RETRIES = 10


def _pooled_mean(blocks: list[list[float]]) -> float:
    """Pooled Mean = sum(all_cycles) / count(all_cycles) ueber alle Bloecke."""
    total = 0.0
    count = 0
    for block in blocks:
        total += sum(block)
        count += len(block)
    if count == 0:
        return 0.0
    return total / count


def _resample_blocks(blocks: list[list[float]], rng: random.Random) -> list[list[float]]:
    """Resample mit Zuruecklegen: n Bloecke aus n Originalbloecken."""
    n = len(blocks)
    return [blocks[rng.randrange(n)] for _ in range(n)]


def _quality_flag(n_min: int) -> str:
    if n_min >= THRESHOLD_OK:
        return "ok"
    if n_min >= THRESHOLD_LIMITED:
        return "limited"
    return "insufficient"


def compute_bootstrap_ci_diff_pct(
    blocks_normal: list[list[float]],
    blocks_compare: list[list[float]],
    n_iter: int = DEFAULT_N_ITER,
    confidence: float = DEFAULT_CONFIDENCE,
    seed: int | None = DEFAULT_SEED,
) -> tuple[float, float, float, str]:
    """Block-Bootstrap-CI fuer (compare_mean - normal_mean) / normal_mean * 100 %.

    Args:
        blocks_normal: Liste von Cycle-Listen je (date, hour)-Block fuer Normal-Modus.
        blocks_compare: Analog fuer Diversity Standard oder DX.
        n_iter: Bootstrap-Iterationen (Default 5000).
        confidence: CI-Niveau (Default 0.95 -> 95 %-CI).
        seed: PRNG-Seed (Default 42); None fuer nichtdeterministisch.

    Returns:
        (point_estimate_pct, ci_low_pct, ci_high_pct, quality_flag)
            quality_flag in {"ok", "limited", "insufficient"}.
            Wenn "insufficient" oder Normal-Mean == 0 fuer Originaldaten:
                (nan, nan, nan, flag).

    Raises:
        ValueError: Wenn nach MAX_DIV0_RETRIES kein gueltiger Resample
            mit normal_mean != 0 gefunden wurde (statistisch sinnlos).
    """
    # Filter: leere Bloecke ignorieren
    blocks_normal = [b for b in blocks_normal if b]
    blocks_compare = [b for b in blocks_compare if b]

    n_min = min(len(blocks_normal), len(blocks_compare))
    flag = _quality_flag(n_min)

    if flag == "insufficient":
        return (math.nan, math.nan, math.nan, flag)

    # Punktschaetzer aus Originaldaten
    pt_normal = _pooled_mean(blocks_normal)
    pt_compare = _pooled_mean(blocks_compare)
    if pt_normal == 0:
        # Originaldaten degeneriert
        return (math.nan, math.nan, math.nan, flag)
    pt_pct = (pt_compare - pt_normal) / pt_normal * 100.0

    # Bootstrap-Schleife
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(n_iter):
        # F-DIV0: bei normal_mean == 0 verwerfen, max MAX_DIV0_RETRIES Versuche
        for _retry in range(MAX_DIV0_RETRIES):
            rs_normal = _resample_blocks(blocks_normal, rng)
            rs_compare = _resample_blocks(blocks_compare, rng)
            m_n = _pooled_mean(rs_normal)
            m_c = _pooled_mean(rs_compare)
            if m_n != 0:
                deltas.append((m_c - m_n) / m_n * 100.0)
                break
        else:
            raise ValueError(
                f"compute_bootstrap_ci_diff_pct: nach {MAX_DIV0_RETRIES} "
                f"Versuchen kein Resample mit normal_mean != 0 gefunden. "
                f"Daten zu wenig variabel oder zu viele Null-Werte."
            )

    # Percentile-CI
    deltas.sort()
    alpha = 1.0 - confidence
    lo_idx = int(round(alpha / 2.0 * (n_iter - 1)))
    hi_idx = int(round((1.0 - alpha / 2.0) * (n_iter - 1)))
    ci_lo = deltas[lo_idx]
    ci_hi = deltas[hi_idx]

    return (pt_pct, ci_lo, ci_hi, flag)


def blocks_from_hourly_stats(hour_stats: dict[int, dict]) -> list[list[float]]:
    """Extrahiert (date, hour)-Bloecke aus load_hourly_stats-Output.

    Args:
        hour_stats: dict[hour -> {"cycles": [...], "daily": {date: [...]},
                                  "minutes": set}]

    Returns:
        Liste von Cycle-Listen je (date, hour)-Block.
    """
    blocks: list[list[float]] = []
    for hour, data in hour_stats.items():
        daily = data.get("daily", {})
        for date, cycles in daily.items():
            if cycles:
                blocks.append([float(c) for c in cycles])
    return blocks


def compute_mode_comparison_ci(
    stats_dir: Path,
    band: str,
    protocol: str = "FT8",
    n_iter: int = DEFAULT_N_ITER,
    load_hourly_stats_fn: Callable | None = None,
) -> dict[str, tuple[float, float, float, str]]:
    """Bootstrap-CI fuer Diversity Standard und DX gegen Normal.

    Args:
        stats_dir: Pfad zum statistics/-Tree.
        band: Band-String, z. B. "40m".
        protocol: Default "FT8".
        n_iter: Bootstrap-Iterationen.
        load_hourly_stats_fn: Optionaler Injection-Point fuer Tests
            (vermeidet Import-Zirkel).

    Returns:
        dict {"Diversity_Normal": (pt, lo, hi, flag),
              "Diversity_Dx":     (pt, lo, hi, flag)}.
        Bei fehlendem Normal-Modus oder fehlenden Compare-Modi: leeres dict
        oder partielles dict.
    """
    if load_hourly_stats_fn is None:
        # Lazy import um Zirkular-Import zu vermeiden
        from generate_plots import load_hourly_stats as _load
        load_hourly_stats_fn = _load

    normal_stats = load_hourly_stats_fn(stats_dir, "Normal", band, protocol)
    if not normal_stats:
        return {}

    blocks_normal = blocks_from_hourly_stats(normal_stats)
    if not blocks_normal:
        return {}

    result: dict[str, tuple[float, float, float, str]] = {}
    for compare_mode in ("Diversity_Normal", "Diversity_Dx"):
        compare_stats = load_hourly_stats_fn(stats_dir, compare_mode, band, protocol)
        if not compare_stats:
            continue
        blocks_compare = blocks_from_hourly_stats(compare_stats)
        if not blocks_compare:
            continue
        result[compare_mode] = compute_bootstrap_ci_diff_pct(
            blocks_normal, blocks_compare, n_iter=n_iter
        )
    return result


def format_ci_short(pt: float, lo: float, hi: float, flag: str) -> str:
    """Formatiert (pt, lo, hi, flag) fuer Tabellen-Anzeige.

    Beispiele:
        format_ci_short(126.3, 112.1, 141.5, "ok")        -> "+112-141%"
        format_ci_short(126.3, 112.1, 141.5, "limited")   -> "+112-141% (limited)"
        format_ci_short(nan, nan, nan, "insufficient")    -> "n/a"
    """
    if flag == "insufficient" or math.isnan(lo) or math.isnan(hi):
        return "n/a"
    sign_lo = "+" if lo >= 0 else ""
    sign_hi = "+" if hi >= 0 else ""
    base = f"{sign_lo}{lo:.0f}\u2013{sign_hi}{hi:.0f}%"
    if flag == "limited":
        return f"{base} (limited)"
    return base


def format_ci_full(pt: float, lo: float, hi: float, flag: str) -> str:
    """Formatiert mit Punktschaetzer fuer README/Print.

    Beispiel: "+126% (95%-CI: +112% to +141%)"
    """
    if flag == "insufficient" or math.isnan(pt):
        return "n/a (insufficient data)"
    sign_pt = "+" if pt >= 0 else ""
    sign_lo = "+" if lo >= 0 else ""
    sign_hi = "+" if hi >= 0 else ""
    base = (
        f"{sign_pt}{pt:.0f}% (95%-CI: {sign_lo}{lo:.0f}% to {sign_hi}{hi:.0f}%)"
    )
    if flag == "limited":
        return f"{base} (limited data)"
    return base
