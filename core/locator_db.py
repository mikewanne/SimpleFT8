"""Persistenter Locator-Cache fuer SimpleFT8 (V3, Hobby-Funker-konform).

Sammelt pro Callsign den besten bekannten Maidenhead-Locator aus mehreren
Quellen mit Priorisierung. Persistiert als eine JSON-Datei (~/.simpleft8/
locator_cache.json), in-memory waehrend Laufzeit, save() bei App-Close.

Quellen (hoeher gewinnt):
    1. cq_6      → 5 km    (eigene FT8-Decode mit 6-stelligem Locator)
    2. psk_6     → 5 km    (PSK-Reporter-Spot)
    3. qso_log_6 → 5 km    (ADIF-Import vom QSO-Log)
    4. cq_4 / psk_4 / qso_log_4 → 110 km (nur 4-stellig)

Slash-Calls:
    /P           → erlaubt, gleiche Priority (portable, stationaer)
    /MM /AM /QRP → erlaubt, prec_km x 1.5 (mobile, ungenauer)

Regeln:
    - 6-stellig wird nie durch 4-stellig ueberschrieben (Source-Priority)
    - first_ts ist immutable, nur last_ts wird aktualisiert
    - Korrupte JSON beim Load → leeres Dict, App startet trotzdem
    - Threading: RLock zentral, set/get/save/bulk-import safe
    - Atomic-Write: .tmp + os.replace (Pattern aus core/psk_reporter.py)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from core.geo import safe_locator_to_latlon

LOG = logging.getLogger(__name__)

# ── Source-Priority (numerisch, hoeher gewinnt) ────────────
SOURCE_PRIORITY: dict[str, int] = {
    "cq_6": 600,
    "psk_6": 500,
    "qso_log_6": 400,
    "cq_4": 300,
    "psk_4": 200,
    "qso_log_4": 100,
}
PREC_KM_BY_LEN: dict[int, int] = {6: 5, 4: 110}
MOBILE_SUFFIXES: tuple[str, ...] = ("/MM", "/AM", "/QRP")
DEFAULT_PATH: Path = Path.home() / ".simpleft8" / "locator_cache.json"
SCHEMA_VERSION: int = 1


@dataclass
class LocatorEntry:
    """Ein Eintrag pro Callsign in der DB."""
    locator: str
    source: str       # "cq_6", "psk_4", ...
    prec_km: int      # 5 / 110 (mobile: x1.5)
    first_ts: float
    last_ts: float


class LocatorDB:
    """In-memory Locator-Cache mit Source-Priority + atomarer JSON-Persistenz."""

    def __init__(self, path: Path | None = None):
        self._path: Path = path if path is not None else DEFAULT_PATH
        self._calls: dict[str, LocatorEntry] = {}
        self._lock = threading.RLock()
        self._dirty: bool = False  # noch nie gesaved seit letztem save?

    # ── Persistenz ─────────────────────────────────────────

    def load(self) -> None:
        """JSON-Datei einlesen. Bei Fehler: leeres Dict, kein Crash."""
        with self._lock:
            self._calls = {}
            if not self._path.exists():
                return
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                LOG.warning("LocatorDB load failed (%s) — starting empty", e)
                return
            calls_raw = raw.get("calls") if isinstance(raw, dict) else None
            if not isinstance(calls_raw, dict):
                return
            for call, data in calls_raw.items():
                try:
                    self._calls[call] = LocatorEntry(
                        locator=str(data["loc"]),
                        source=str(data["src"]),
                        prec_km=int(data["prec_km"]),
                        first_ts=float(data["first"]),
                        last_ts=float(data["last"]),
                    )
                except (KeyError, TypeError, ValueError):
                    continue

    def save(self) -> None:
        """Atomar schreiben (.tmp + os.replace). Erzeugt Parent-Dir falls noetig."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": SCHEMA_VERSION,
                "calls": {
                    call: {
                        "loc": e.locator,
                        "src": e.source,
                        "prec_km": e.prec_km,
                        "first": e.first_ts,
                        "last": e.last_ts,
                    }
                    for call, e in self._calls.items()
                },
            }
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
            os.replace(tmp, self._path)
            self._dirty = False

    # ── Lookup ─────────────────────────────────────────────

    def get(self, call: str) -> LocatorEntry | None:
        """Eintrag fuer Call zurueckgeben, oder None.

        Returnt eine Kopie — Caller-Mutation aendert die DB nicht.
        """
        if not isinstance(call, str) or not call:
            return None
        with self._lock:
            e = self._calls.get(call.upper())
            if e is None:
                return None
            return LocatorEntry(**asdict(e))

    def get_position(self, call: str) -> tuple[float, float, int] | None:
        """(lat, lon, prec_km) oder None — fuer Karte / km-Spalte."""
        entry = self.get(call)
        if entry is None:
            return None
        latlon = safe_locator_to_latlon(entry.locator)
        if latlon is None:
            return None
        return (latlon[0], latlon[1], entry.prec_km)

    # ── Update ─────────────────────────────────────────────

    def set(self, call: str, locator: str, source: str) -> bool:
        """Eintrag setzen wenn neu oder Priority hoeher.

        Args:
            call:     Rufzeichen (Slash-Suffixe werden beruecksichtigt).
            locator:  4- oder 6-stelliger Maidenhead-Locator.
            source:   "cq" / "psk" / "qso_log" (intern wird _4/_6 angehaengt).
        Returns:
            True wenn Eintrag geschrieben/aktualisiert wurde, sonst False.
        """
        if not isinstance(call, str) or not call:
            return False
        if not isinstance(locator, str):
            return False
        loc = locator.strip().upper()
        if safe_locator_to_latlon(loc) is None:
            return False
        if source not in ("cq", "psk", "qso_log"):
            return False

        # Length-Tag bestimmen (4 oder 6)
        length_tag = 6 if len(loc) >= 6 else 4
        source_tag = f"{source}_{length_tag}"
        new_priority = SOURCE_PRIORITY[source_tag]
        prec_km = PREC_KM_BY_LEN[length_tag]

        # Mobile-Suffix → prec_km x 1.5
        call_upper = call.upper()
        if any(call_upper.endswith(suf) for suf in MOBILE_SUFFIXES):
            prec_km = int(round(prec_km * 1.5))

        now = time.time()
        with self._lock:
            existing = self._calls.get(call_upper)
            if existing is not None:
                # 6-stellig wird nie durch 4-stellig ueberschrieben
                old_priority = SOURCE_PRIORITY.get(existing.source, 0)
                if new_priority < old_priority:
                    return False
                # Gleiche Priority → nur last_ts updaten, Daten unveraendert
                if new_priority == old_priority and existing.locator == loc:
                    existing.last_ts = now
                    self._dirty = True
                    return True
                # Hoehere Priority oder gleiche Prio mit anderem Locator: ueberschreiben
                # first_ts bleibt immutable
                self._calls[call_upper] = LocatorEntry(
                    locator=loc,
                    source=source_tag,
                    prec_km=prec_km,
                    first_ts=existing.first_ts,
                    last_ts=now,
                )
            else:
                self._calls[call_upper] = LocatorEntry(
                    locator=loc,
                    source=source_tag,
                    prec_km=prec_km,
                    first_ts=now,
                    last_ts=now,
                )
            self._dirty = True
            return True

    # ── Bulk-Import ────────────────────────────────────────

    def bulk_import_adif(self, adif_path: Path | str) -> int:
        """ADIF-Datei einlesen und alle CALL+GRIDSQUARE-Paare als qso_log eintragen.

        Returns:
            Anzahl erfolgreich uebernommener Eintraege.
        """
        from log.adif import parse_adif_file
        path = Path(adif_path)
        if not path.exists():
            return 0
        try:
            records = parse_adif_file(path)
        except (OSError, UnicodeDecodeError) as e:
            LOG.warning("ADIF parse failed for %s: %s", path, e)
            return 0
        return self._bulk_import_records(records)

    def bulk_import_directory(self, directory: Path | str) -> int:
        """Alle .adi-Dateien eines Verzeichnisses einlesen."""
        from log.adif import parse_all_adif_files
        d = Path(directory)
        if not d.is_dir():
            return 0
        try:
            records = parse_all_adif_files(d)
        except OSError as e:
            LOG.warning("ADIF directory scan failed for %s: %s", d, e)
            return 0
        return self._bulk_import_records(records)

    def _bulk_import_records(self, records: Iterable[dict]) -> int:
        n = 0
        for rec in records:
            call = (rec.get("CALL") or "").strip()
            grid = (rec.get("GRIDSQUARE") or "").strip()
            if call and grid and self.set(call, grid, "qso_log"):
                n += 1
        return n

    # ── Diagnostik ─────────────────────────────────────────

    def __len__(self) -> int:
        with self._lock:
            return len(self._calls)

    def average_precision_km(self) -> float:
        """Durchschnittliche Genauigkeit in km ueber alle Eintraege (0.0 wenn leer)."""
        with self._lock:
            if not self._calls:
                return 0.0
            return sum(e.prec_km for e in self._calls.values()) / len(self._calls)

    def snapshot(self) -> dict[str, dict]:
        """Deep-copy-Snapshot fuer threadsicheres Read-Only-Iterieren."""
        with self._lock:
            return {call: asdict(e) for call, e in self._calls.items()}
