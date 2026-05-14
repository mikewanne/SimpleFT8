"""Bandpilot — Stunden-genaue RX-Modus-Empfehlung pro Band aus Statistik.

Hobby-Funker-Tool: User wechselt Band → Bandpilot prueft fuer die aktuelle
UTC-Stunde welcher RX-Modus (Normal / Diversity Standard / Diversity DX)
historisch am meisten Stationen gebracht hat, und entscheidet basierend
auf Settings (off / auto / manual).

Design v0.88 (Mike + R1 Konsens 2026-05-04):

    Drei DIREKTE Stunden-Werte pro UTC-Stunde — KEINE Aggregation.
    Begruendung: Std und DX repraesentieren unterschiedliche
    Grundgesamtheiten (Antennen-Pattern, Win-Rate-Logik). Aggregat
    ``(Std + DX) / 2`` aus v0.87 war statistisch nicht sauber, weil
    nicht IID.

    Empfehlung = Top-1 nach Stations-Mean. Toleranz ``max(5%, 1 Station)``
    gegen den AKTUELLEN Modus (R1-Finding A): wenn der aktuelle Modus
    nahe genug an Top-1 dran ist, kein Wechsel — sonst Wechsel zu Top-1.

    Stille bei zu wenig Daten in irgendeinem der drei Modi pro Stunde.
    Schwellen: ``MIN_DAYS_HOUR = 3`` Messtage, ``MIN_CYCLES_HOUR = 20``
    Slots in DIESER UTC-Stunde, alle drei Modi muessen erfuellen.

Cache: ``~/.simpleft8/bandpilot_hourly.json`` mit TTL 24h pro Band.
Lazy-Aggregation — ``HourlyBandpilot.get_summary(band)`` nutzt Cache.

Replacement von v0.87 ``Bandpilot``-Klasse + ``aggregate_stats`` +
``recommend(diversity_pref)``: alte Aggregat-API ist komplett geloescht.
Migration siehe ``config/settings.py:_migrate_bandpilot_settings_v088``.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

# ── Schwellen pro Stunde (alle drei Modi muessen erfuellen) ──────────────
MIN_DAYS_HOUR = 3
MIN_CYCLES_HOUR = 20

# Cache-TTL: 24h
CACHE_TTL_S = 24 * 3600

# ── Encoding-Konvention v0.88 (V3-AK 22) ──────────────────────────────
# Code-Strings (interne Repraesentation, JSON-Keys)
CODE_MODES: tuple[str, ...] = ("normal", "diversity_normal", "diversity_dx")

# Stats-Verzeichnis-Mapping (Code-String → Verzeichnis-Name)
STATS_DIR: dict[str, str] = {
    "normal":           "Normal",
    "diversity_normal": "Diversity_Normal",
    "diversity_dx":     "Diversity_Dx",
}

# UI-Label (Toast, Dialog, MD-Datei)
USER_LABEL: dict[str, str] = {
    "normal":           "Normal",
    "diversity_normal": "Diversity Standard",
    "diversity_dx":     "Diversity DX",
}

# ── Datei-Format ──────────────────────────────────────────────────────
# Stats-File-Namen z.B. "2026-04-21_07.md" (Datum_Stunde).
# Das _2-Suffix-Pattern (macOS-Spotlight-Duplikat) wird nicht gematcht.
_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{2})\.md$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def _parse_stats_file(path: Path) -> tuple[int, int]:
    """Eine Stats-MD-Datei lesen → (sum_count, num_cycles).

    Format der relevanten Zeilen:
    ``| HH:MM:SS | <int> | <snr> |`` (Normal, 3 Spalten)
    ``| HH:MM:SS | <int> | <snr> | <wins> | <delta> |`` (Diversity, 5 Spalten)

    Defekte Zeilen (Header, Trenner, leere Werte) werden uebersprungen.
    Bei IO-Fehler: ``(0, 0)`` — Bandpilot soll nie crashen.
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


def _aggregate_mode_by_hour(mode_dir: Path) -> dict[int, dict]:
    """Alle MD-Dateien eines Modus-Verzeichnisses pro UTC-Stunde aggregieren.

    Returns: ``{hour: {"days": int, "cycles": int, "mean": float}}``.
    Stunden ohne Daten werden nicht in das Dict aufgenommen.
    """
    if not mode_dir.is_dir():
        return {}

    # state pro Stunde: {hour: {"days": set, "sum_count": int, "cycles": int}}
    hour_state: dict[int, dict] = {}

    for entry in mode_dir.iterdir():
        m = _FILE_RE.match(entry.name)
        if not m:
            continue
        day = m.group(1)
        hour = int(m.group(2))
        s, c = _parse_stats_file(entry)
        if c == 0:
            continue
        if hour not in hour_state:
            hour_state[hour] = {"days": set(), "sum_count": 0, "cycles": 0}
        hour_state[hour]["days"].add(day)
        hour_state[hour]["sum_count"] += s
        hour_state[hour]["cycles"] += c

    result: dict[int, dict] = {}
    for hour, state in hour_state.items():
        cycles = state["cycles"]
        result[hour] = {
            "days": len(state["days"]),
            "cycles": cycles,
            "mean": state["sum_count"] / cycles if cycles > 0 else None,
        }
    return result


def aggregate_stats_by_hour(
    stats_dir: Path, band: str, protocol: str = "FT8"
) -> dict[int, dict[str, dict]]:
    """Stats fuer ein Band stunden-aggregiert ueber alle drei Modi.

    Args:
        stats_dir: ``<repo>/statistics`` — App-Root-relativ.
        band: ``"40m"``, ``"20m"`` etc.
        protocol: aktuell nur ``"FT8"`` (Stats-Logger filtert FT4/FT2).

    Returns: ``{hour: {mode_code: {"days", "cycles", "mean"}}}``.
             Stunden ohne Daten in einem Modus → mode-Key fehlt im inneren
             dict. Stunden ohne Daten in ALLEN Modi fehlen komplett.
    """
    result: dict[int, dict[str, dict]] = {}
    for code in CODE_MODES:
        mode_dir = stats_dir / STATS_DIR[code] / band / protocol
        per_hour = _aggregate_mode_by_hour(mode_dir)
        for hour, summary in per_hour.items():
            if hour not in result:
                result[hour] = {}
            result[hour][code] = summary
    return result


def recommend_for_hour(
    summary_24h: dict[int, dict[str, dict]],
    hour: int,
    current_mode: str | None,
    allowed_modes: tuple[str, ...] | None = None,
) -> dict | None:
    """Empfehlung fuer eine bestimmte UTC-Stunde + aktuellen Modus.

    Args:
        summary_24h: Output von ``aggregate_stats_by_hour()``.
        hour: UTC-Stunde 0..23.
        current_mode: aktueller RX-Modus-String oder ``None`` (z.B.
            waehrend dx_tuning) — None → keine Empfehlung.
        allowed_modes: Bundle H (v0.97.25) — wenn gesetzt, wird das
            Ranking nur aus diesen Code-Modi gebildet (statt aus den
            3 CODE_MODES). Wenn ``current_mode not in allowed_modes``,
            wird die Tolerance-Logik geskippt und ``decision="switch"``
            mit ``decision_mode=top1`` returnt (User-explizite
            Subset-Wahl).
            Default ``None`` = 3-Wege-Vergleich wie bisher.

    Returns:
        ``None`` wenn ``current_mode`` ist ``None`` ODER fuer die Stunde
        nicht alle relevanten Modi MIN_DAYS_HOUR + MIN_CYCLES_HOUR
        erfuellen ODER ``current_mode`` nicht im Vergleich vorkommt
        (nur bei allowed_modes=None).

        Sonst: ``dict`` mit:
            - ``top1``: Code-String des Top-Modus
            - ``top1_mean``: Pooled Mean Top-1
            - ``ranking``: ``[(mode, mean), ...]`` desc sortiert
              (3-elementig bei allowed_modes=None, sonst len(allowed_modes))
            - ``decision``: ``"no_change"`` | ``"switch"``
            - ``decision_mode``: empfohlener neuer Modus (kann == current_mode
              sein bei ``no_change``)

    Toleranz-Regel (R1-Finding A, V3-AK 12):
        Kein Wechsel wenn ``current_mean >= top1_mean - max(5%·top1_mean, 1)``.
        Toleranz wird gegen den AKTUELLEN Modus gemessen, nicht gegen Top-2.
        Bundle H: bei `allowed_modes` + `current_mode not in allowed_modes`
        wird Tolerance geskippt (User will explizit aus Subset wählen).
    """
    if current_mode is None:
        return None

    modes_in_hour = summary_24h.get(hour, {})
    if not modes_in_hour:
        return None

    # Bundle H: wenn allowed_modes gesetzt, nur dieses Subset prüfen
    modes_to_check = allowed_modes if allowed_modes is not None else CODE_MODES

    means: dict[str, float] = {}
    for code in modes_to_check:
        entry = modes_in_hour.get(code, {})
        if (entry.get("days", 0) < MIN_DAYS_HOUR or
                entry.get("cycles", 0) < MIN_CYCLES_HOUR or
                entry.get("mean") is None):
            return None
        means[code] = entry["mean"]

    # Sortieren descending → Top-1 erster Eintrag
    ranking = sorted(means.items(), key=lambda x: x[1], reverse=True)
    top1_mode, top1_mean = ranking[0]

    # Bundle H: bei allowed_modes-Subset-Pfad current_mode nicht im
    # Ranking → User will eh wechseln, Tolerance-Skip.
    if allowed_modes is not None and current_mode not in means:
        return {
            "top1": top1_mode,
            "top1_mean": top1_mean,
            "ranking": ranking,
            "decision": "switch",
            "decision_mode": top1_mode,
        }

    if current_mode not in means:
        # Kann nicht passieren wenn alle Modi vorhanden,
        # aber defensive: unbekannter current_mode-String.
        return None

    current_mean = means[current_mode]
    tolerance = max(0.05 * top1_mean, 1.0)

    if current_mean >= top1_mean - tolerance:
        decision = "no_change"
        decision_mode = current_mode
    else:
        decision = "switch"
        decision_mode = top1_mode

    return {
        "top1": top1_mode,
        "top1_mean": top1_mean,
        "ranking": ranking,
        "decision": decision,
        "decision_mode": decision_mode,
    }


def code_mode_to_scoring(decision_mode: str) -> str:
    """Bundle H (v0.97.25): Bandpilot-Code-Modus → DiversityController.scoring_mode.

    Code-Modi (CODE_MODES): „normal" / „diversity_normal" / „diversity_dx"
    Scoring-Modi (DiversityController): „normal" (Standard) / „dx"

    Naming-Kollision: „normal" als Code-Mode = Normal-RX, „normal" als
    Scoring = Standard-Scoring in Diversity. Mapping:
        diversity_normal → "normal" (Std-Scoring)
        diversity_dx     → "dx"
        andere           → "normal" (Default-Fallback)
    """
    return "dx" if decision_mode == "diversity_dx" else "normal"


class HourlyBandpilotCache:
    """Persistenter Cache pro Band fuer stunden-aggregierte Stats.

    Datei ``~/.simpleft8/bandpilot_hourly.json``, Format:
    ``{band: {ts: <unix>, summary: {hour_str: {mode: {...}}}}}``
    JSON serialisiert int-Keys als Strings — beim Lesen zurueck konvertiert.

    Atomares Schreiben via tmp+replace.
    """

    def __init__(self, cache_path: Path | None = None):
        if cache_path is None:
            cache_path = Path.home() / ".simpleft8" / "bandpilot_hourly.json"
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

    def get(self, band: str) -> dict[int, dict[str, dict]] | None:
        """Cached Summary fuer band, wenn nicht abgelaufen. Sonst ``None``."""
        entry = self._data.get(band)
        if not entry:
            return None
        ts = entry.get("ts", 0)
        if (time.time() - ts) > CACHE_TTL_S:
            return None
        summary = entry.get("summary")
        if not isinstance(summary, dict):
            return None
        # JSON-int-Keys sind Strings — zurueck konvertieren
        try:
            return {int(k): v for k, v in summary.items()}
        except (TypeError, ValueError):
            return None

    def set(self, band: str, summary: dict[int, dict]) -> None:
        """Summary fuer band cachen + atomar persistieren."""
        # Int-Hours als Strings serialisieren (JSON-Limitation)
        serialized = {str(k): v for k, v in summary.items()}
        self._data[band] = {"ts": time.time(), "summary": serialized}
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


class HourlyBandpilot:
    """High-Level-API fuer das UI: Empfehlung pro (band, hour, current_mode).

    Kapselt Aggregator + Cache. Lazy-Aggregation pro Band — Cache wird
    erst beim ersten Aufruf gefuellt.
    """

    def __init__(
        self,
        stats_dir: Path | None = None,
        cache: HourlyBandpilotCache | None = None,
    ):
        if stats_dir is None:
            stats_dir = Path(__file__).parent.parent / "statistics"
        self._stats_dir = Path(stats_dir)
        self._cache = cache if cache is not None else HourlyBandpilotCache()

    def get_summary(self, band: str) -> dict[int, dict[str, dict]]:
        """Stunden-Summary fuer band, mit Cache-Fast-Path."""
        cached = self._cache.get(band)
        if cached is not None:
            return cached
        summary = aggregate_stats_by_hour(self._stats_dir, band)
        self._cache.set(band, summary)
        return summary

    def recommend(
        self, band: str, hour: int, current_mode: str | None,
        allowed_modes: tuple[str, ...] | None = None,
    ) -> dict | None:
        """Empfehlung fuer (band, hour, current_mode).

        Bundle H: ``allowed_modes`` für Subset-Vergleich
        (z.B. Diversity-only beim Klick auf DIVERSITY-Button).
        """
        summary = self.get_summary(band)
        return recommend_for_hour(summary, hour, current_mode, allowed_modes)

    def invalidate(self, band: str) -> None:
        """Cache fuer band invalidieren — naechster Aufruf re-aggregiert."""
        self._cache.invalidate(band)
