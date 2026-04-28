"""SimpleFT8 RX-History-Cache — persistente Empfangs-Stationen pro Band+Modus.

Speichert die in den letzten 60 Min empfangenen Stationen, damit die
Karten-Ansicht beim Open (oder nach App-Restart) sofort einen vollen
60-Min-Snapshot zeigt — nicht nur das was waehrend der aktuellen
Karten-Sitzung live reinkommt.

Architektur (analog LocatorDB v0.70):
- In-Memory `dict[(band, mode), list[RxEntry]]` waehrend Laufzeit.
- Auto-Save alle 5 Min via QTimer im main_window (gemeinsam mit LocatorDB).
- closeEvent → finaler save().
- kill_old_instances (SIGKILL) bypassed closeEvent → Auto-Save als
  Sicherheitsnetz (max 5 Min Datenverlust akzeptiert, Hobby-Use).

JSON-Format pro Datei `~/.simpleft8/cache/rx_history/{band}_{mode}.json`:
    {
        "version": 1,
        "band": "40m",
        "mode": "FT8",
        "entries": [
            {"ts": ..., "call": "...", "locator": "...", "snr": ...,
             "antenna": "A1", "freq_hz": ...},
            ...
        ]
    }

TTL: Eintraege aelter als 60 Min werden beim save() + load_all() entfernt.

Cache ist BAND-AGNOSTISCH — speichert was Mike aktiv empfaengt. Kein
Filter auf LOGGED_BANDS (das ist Stats-Filter, separate Concern).
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path


RX_HISTORY_TTL_S = 3600  # 60 Min
RX_HISTORY_DIR = Path.home() / ".simpleft8" / "cache" / "rx_history"
SCHEMA_VERSION = 1


@dataclass
class RxEntry:
    """Eine empfangene Station zu einem bestimmten Zeitpunkt."""
    ts: float
    call: str
    locator: str | None
    snr: float
    antenna: str  # "A1" / "A2" / "rescue" / ""
    freq_hz: int


class RxHistoryStore:
    """In-Memory + JSON-persistierter Empfangs-Cache.

    Thread-safe (RLock) — Decoder-Thread schreibt via add_entry, GUI-Thread
    liest via get_band_entries, Auto-Save-Timer ruft save() — alle drei
    duerfen konkurrent laufen.

    Save-Strategie:
    - dirty-set merkt welche (band, mode)-Files seit letztem Save geaendert
      wurden — Save schreibt nur diese, nicht alle 27 moeglichen Files.
    - Atomic-Write via `.tmp` + `os.replace` (kein partial-write-Risiko).
    - OSError beim Write wird gefangen + geloggt — kein Crash.
    """

    def __init__(self, base_dir: Path | str | None = None):
        self._base_dir = Path(base_dir) if base_dir is not None else RX_HISTORY_DIR
        self._entries: dict[tuple[str, str], list[RxEntry]] = {}
        self._dirty: set[tuple[str, str]] = set()
        self._lock = threading.RLock()

    # ── Add ───────────────────────────────────────────────

    def add_entry(self, band: str, mode: str, entry: RxEntry) -> None:
        """Eintrag fuer (band, mode) hinzufuegen + dirty markieren.

        Keine Dedup im Store — Canvas dedupliziert via _station_history[call].
        Kein TTL-Check beim Add (KISS — Cleanup beim Save).
        """
        if not band or not mode:
            return
        key = (band, mode)
        with self._lock:
            if key not in self._entries:
                self._entries[key] = []
            self._entries[key].append(entry)
            self._dirty.add(key)

    # ── Read ──────────────────────────────────────────────

    def get_band_entries(self, band: str) -> list[RxEntry]:
        """Alle Eintraege des Bandes (alle Modi gemerged), TTL-gefiltert.

        Returns chronologisch sortiert (aelteste zuerst).
        """
        if not band:
            return []
        cutoff = time.time() - RX_HISTORY_TTL_S
        result: list[RxEntry] = []
        with self._lock:
            for (b, _mode), entries in self._entries.items():
                if b != band:
                    continue
                for e in entries:
                    if e.ts >= cutoff:
                        result.append(e)
        result.sort(key=lambda e: e.ts)
        return result

    # ── Cleanup ───────────────────────────────────────────

    def cleanup_all(self) -> int:
        """Eintraege aelter als TTL ueberall entfernen.

        Returns: Anzahl entfernter Eintraege. Markiert betroffene
        (band, mode)-Paare als dirty.
        """
        cutoff = time.time() - RX_HISTORY_TTL_S
        removed = 0
        with self._lock:
            for key, entries in list(self._entries.items()):
                old_count = len(entries)
                fresh = [e for e in entries if e.ts >= cutoff]
                if len(fresh) != old_count:
                    self._entries[key] = fresh
                    self._dirty.add(key)
                    removed += old_count - len(fresh)
        return removed

    # ── Save / Load ───────────────────────────────────────

    def save(self) -> int:
        """Nur dirty Files atomar schreiben.

        Returns: Anzahl tatsaechlich geschriebener Files. Bei OSError
        (Disk full, Permission) wird geloggt + 0 returned (kein Crash).
        """
        self.cleanup_all()  # vor dem Save TTL-Cleanup
        with self._lock:
            dirty = list(self._dirty)
            # Snapshots der dirty-entries — Lock waehrend Disk-I/O minimieren
            payload: dict[tuple[str, str], list[dict]] = {}
            for key in dirty:
                payload[key] = [asdict(e) for e in self._entries.get(key, [])]
            self._dirty.clear()

        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"[RxHistory] mkdir failed: {exc}")
            # dirty wieder reaktivieren — naechster Save versucht erneut
            with self._lock:
                self._dirty.update(dirty)
            return 0

        written = 0
        for (band, mode), entries_dict in payload.items():
            file_path = self._base_dir / f"{band}_{mode}.json"
            tmp_path = file_path.with_suffix(".tmp")
            data = {
                "version": SCHEMA_VERSION,
                "band": band,
                "mode": mode,
                "entries": entries_dict,
            }
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, separators=(",", ":"))
                os.replace(tmp_path, file_path)
                written += 1
            except OSError as exc:
                print(f"[RxHistory] save {file_path.name} failed: {exc}")
                # dirty erneut markieren — naechster Save retry
                with self._lock:
                    self._dirty.add((band, mode))
        return written

    def load_all(self) -> int:
        """Alle Files unter base_dir lesen, TTL-filtern.

        Korrupte JSONs oder falsche Schema-Version werden uebersprungen.
        Returns: Anzahl gueltiger Eintraege.
        """
        if not self._base_dir.exists():
            return 0
        cutoff = time.time() - RX_HISTORY_TTL_S
        total = 0
        for file_path in self._base_dir.glob("*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                print(f"[RxHistory] load {file_path.name} failed: {exc}")
                continue
            if not isinstance(data, dict):
                continue
            if data.get("version") != SCHEMA_VERSION:
                continue  # andere Schema-Version → ignorieren
            band = data.get("band")
            mode = data.get("mode")
            entries_raw = data.get("entries", [])
            if not (isinstance(band, str) and isinstance(mode, str)
                    and isinstance(entries_raw, list)):
                continue

            fresh: list[RxEntry] = []
            for raw in entries_raw:
                if not isinstance(raw, dict):
                    continue
                try:
                    e = RxEntry(
                        ts=float(raw["ts"]),
                        call=str(raw["call"]),
                        locator=raw.get("locator"),
                        snr=float(raw["snr"]),
                        antenna=str(raw.get("antenna", "")),
                        freq_hz=int(raw.get("freq_hz", 0)),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                if e.ts >= cutoff:
                    fresh.append(e)
            if fresh:
                with self._lock:
                    self._entries[(band, mode)] = fresh
                total += len(fresh)
        return total

    # ── Introspection ──────────────────────────────────────

    def __len__(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._entries.values())

    @property
    def base_dir(self) -> Path:
        return self._base_dir
