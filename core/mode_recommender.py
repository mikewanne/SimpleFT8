"""Bandpilot — RX-Modus-Empfehlung pro Band aus Statistik-Daten.

Hobby-Funker-Tool: User wechselt Band → Bandpilot empfiehlt automatisch
den RX-Modus (Normal / Diversity Standard / Diversity DX) der in der
bisherigen Messung den hoechsten Pooled-Mean an Stationen pro 15s-Zyklus
geliefert hat.

Aggregations-Methodik (Mike-Entscheidung 2026-05-01, Kandidat A):
    Vergleichswert Diversity = (Diversity_Normal + Diversity_Dx) / 2
    Empfehlung = Normal vs Diversity-Aggregat

Begruendung Kandidat A: Alle drei Stats-Pfade
(Normal / Diversity_Normal / Diversity_Dx) loggen dieselbe Metrik —
Anzahl dekodierter Stationen pro Slot. Das halbiert die Mindest-Messzeit:
ein Tag Diversity_Normal + ein Tag Diversity_Dx zaehlt fuer das Diversity-
Aggregat als zwei Datentage statt nur als Halb-Daten.

Wenn Diversity gewinnt: der user-konfigurierbare ``diversity_pref``
("auto"/"standard"/"dx") entscheidet welcher konkrete Modus aktiviert wird.
"auto" = der Modus mit dem hoeheren individuellen Mean wird gewaehlt.

Threshold ``MIN_DAYS = 2`` pro Modus — gleiche Schwelle wie GitHub-Push-
Minimum (CLAUDE.md "Statistik-Veroeffentlichung"). Unter MIN_DAYS oder
MIN_CYCLES gibt ``recommend()`` ``None`` zurueck — User behaelt seinen
manuell gesetzten Modus.

Cache: ``~/.simpleft8/bandpilot_summary.json`` mit TTL 24h pro Band.
Aggregation kostet bei 10+ Tagen ~50ms — Lazy-Load reicht.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

# Mindest-Messtage pro Modus (Normal / Diversity_Normal / Diversity_Dx)
# — unter dieser Schwelle gibt recommend() None zurueck (kein Auto-Switch).
MIN_DAYS = 2

# Mindest-Zyklenzahl pro Modus — Schutz gegen Tage mit nur 1-2 Slots
# (z.B. Mode-Wechsel-Artefakte in den ersten Sekunden einer Stunde).
MIN_CYCLES = 50

# Cache-TTL: nach 24h wird neu aggregiert (deckt einen ganzen Messtag ab).
CACHE_TTL_S = 24 * 3600

# Welche Modi gepruert werden — Reihenfolge entspricht Verzeichnisnamen.
_RX_MODES = ("Normal", "Diversity_Normal", "Diversity_Dx")

# Stats-File-Format-Match (z.B. "2026-04-21_07.md").
# Verhindert Treffer auf "2026-04-21_07 2.md" (macOS-Spotlight-Duplikate).
_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_\d{2}\.md$")

# Stats-Tabellenzeile: "| HH:MM:SS | <count> | ..."
# Erste Spalte muss eine Uhrzeit sein, zweite Spalte ist Stationsanzahl.
_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def _parse_stats_file(path: Path) -> tuple[int, int]:
    """Eine Stats-MD-Datei lesen → (sum_count, num_cycles).

    Format der relevanten Zeilen (Normal):  ``| HH:MM:SS | <int> | <snr> |``
    Format Diversity (5 Spalten):           ``| HH:MM:SS | <int> | <snr> | <wins> | <delta> |``

    Defekte Zeilen (z.B. Header, Trenner, leere Werte) werden uebersprungen.
    Bei IO-Fehler: (0, 0) — wir wollen Bandpilot nicht crashen lassen.
    """
    sum_count = 0
    cycles = 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("| "):
                    continue
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if len(parts) < 2:
                    continue
                if not _TIME_RE.match(parts[0]):
                    continue
                try:
                    count = int(parts[1])
                except ValueError:
                    continue
                sum_count += count
                cycles += 1
    except OSError:
        return 0, 0
    return sum_count, cycles


def _aggregate_mode(mode_dir: Path) -> dict:
    """Alle MD-Dateien eines Modus-Verzeichnisses aggregieren.

    Returns: ``{"days": int, "cycles": int, "mean": float | None}``
    ``mean`` ist Pooled Mean = sum(counts) / cycles. ``None`` wenn 0 Cycles.
    """
    if not mode_dir.is_dir():
        return {"days": 0, "cycles": 0, "mean": None}

    days: set[str] = set()
    sum_count = 0
    cycles = 0

    for entry in mode_dir.iterdir():
        m = _FILE_RE.match(entry.name)
        if not m:
            continue
        day = m.group(1)
        s, c = _parse_stats_file(entry)
        if c == 0:
            continue
        sum_count += s
        cycles += c
        days.add(day)

    mean = sum_count / cycles if cycles > 0 else None
    return {"days": len(days), "cycles": cycles, "mean": mean}


def aggregate_stats(stats_dir: Path, band: str, protocol: str = "FT8") -> dict:
    """Stats fuer ein Band aggregieren ueber alle drei Modi.

    Args:
        stats_dir: ``<repo>/statistics`` — App-Root-relativ (portable).
        band: ``"40m"``, ``"20m"`` etc.
        protocol: aktuell nur ``"FT8"`` (Stats-Logger filtert FT4/FT2).

    Returns: dict mit drei Keys (Normal, Diversity_Normal, Diversity_Dx),
             jeder mit ``{"days", "cycles", "mean"}``.
    """
    summary = {}
    for mode in _RX_MODES:
        mode_dir = stats_dir / mode / band / protocol
        summary[mode] = _aggregate_mode(mode_dir)
    return summary


def recommend(summary: dict, diversity_pref: str = "auto") -> str | None:
    """Empfehlung aus aggregiertem Summary herleiten.

    Args:
        summary: Output von ``aggregate_stats()``.
        diversity_pref: ``"auto"`` (besserer der beiden Diversity-Modi),
                        ``"standard"`` (immer Diversity_Normal),
                        ``"dx"`` (immer Diversity_Dx).

    Returns:
        ``"normal"`` | ``"diversity_normal"`` | ``"diversity_dx"`` | ``None``.
        ``None`` wenn auch nur ein Modus unter MIN_DAYS oder MIN_CYCLES liegt
        (User behaelt manuellen Modus).
    """
    n = summary.get("Normal", {})
    s = summary.get("Diversity_Normal", {})
    d = summary.get("Diversity_Dx", {})

    for entry in (n, s, d):
        if entry.get("days", 0) < MIN_DAYS:
            return None
        if entry.get("cycles", 0) < MIN_CYCLES:
            return None
        if entry.get("mean") is None:
            return None

    n_mean = n["mean"]
    s_mean = s["mean"]
    d_mean = d["mean"]

    # Kandidat A: gewichtet 50/50, weil beide Diversity-Modi dieselbe
    # Metrik (Stationen/Slot) loggen. Halbiert die Mindest-Messzeit.
    div_aggregate = (s_mean + d_mean) / 2.0

    if n_mean >= div_aggregate:
        return "normal"

    if diversity_pref == "standard":
        return "diversity_normal"
    if diversity_pref == "dx":
        return "diversity_dx"
    # "auto" oder unbekannt: bessererer der beiden
    return "diversity_normal" if s_mean >= d_mean else "diversity_dx"


class BandpilotSummaryCache:
    """Persistenter Cache pro Band fuer aggregierte Stats.

    Aggregation kostet bei 10+ Tagen ~50ms. Cache invalidert nach 24h
    automatisch — naechster Aufruf re-aggregiert. Manueller Reset ueber
    ``invalidate(band)`` falls noetig.

    Datei: ``~/.simpleft8/bandpilot_summary.json``, Format:
    ``{ "<band>": {"ts": <unix>, "summary": {...}} }``
    """

    def __init__(self, cache_path: Path | None = None):
        if cache_path is None:
            cache_path = Path.home() / ".simpleft8" / "bandpilot_summary.json"
        self._path = Path(cache_path)
        self._data: dict = self._load()

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def get(self, band: str) -> dict | None:
        """Cached Summary fuer band, wenn nicht abgelaufen. Sonst None."""
        entry = self._data.get(band)
        if not entry:
            return None
        ts = entry.get("ts", 0)
        if (time.time() - ts) > CACHE_TTL_S:
            return None
        summary = entry.get("summary")
        return summary if isinstance(summary, dict) else None

    def set(self, band: str, summary: dict) -> None:
        """Summary fuer band cachen + atomar persistieren."""
        self._data[band] = {"ts": time.time(), "summary": summary}
        self._save()

    def invalidate(self, band: str) -> None:
        """Cache-Eintrag fuer band loeschen + persistieren."""
        if band in self._data:
            del self._data[band]
            self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self._path)


class Bandpilot:
    """High-Level-API fuer das UI: ``recommend_for_band(band)`` reicht.

    Kapselt Aggregator + Cache. Lazy-Aggregation: Cache wird erst beim
    ersten Aufruf pro Band gefuellt.
    """

    def __init__(
        self,
        stats_dir: Path | None = None,
        cache: BandpilotSummaryCache | None = None,
        diversity_pref: str = "auto",
    ):
        if stats_dir is None:
            stats_dir = Path(__file__).parent.parent / "statistics"
        self._stats_dir = Path(stats_dir)
        self._cache = cache if cache is not None else BandpilotSummaryCache()
        self.diversity_pref = diversity_pref

    def recommend_for_band(self, band: str) -> str | None:
        """Empfehlung fuer band, mit Cache-Fast-Path. None = nicht genug Daten."""
        summary = self._cache.get(band)
        if summary is None:
            summary = aggregate_stats(self._stats_dir, band)
            self._cache.set(band, summary)
        return recommend(summary, diversity_pref=self.diversity_pref)

    def invalidate(self, band: str) -> None:
        """Cache fuer band invalidieren — naechster Aufruf re-aggregiert."""
        self._cache.invalidate(band)
