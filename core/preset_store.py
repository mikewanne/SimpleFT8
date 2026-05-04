"""SimpleFT8 PresetStore — Separate JSON-Datei pro Diversity-Modus.

Speichert Gain-Kalibrierung + Diversity-Ratio pro Band+FTMode.
Standard → ~/.simpleft8/kalibrierung/presets_standard.json
DX       → ~/.simpleft8/kalibrierung/presets_dx.json

Zwei Validity-Fenster (v0.93):
  - Gain  → 6 h (Hardware-Eigenschaft des RX-Verstaerkers)
  - Ratio → 1 h (atmosphaerische Antennen-Charakteristik)

Migration: alte Caches mit nur 'timestamp' werden beim Load auf beide
Felder (gain_timestamp + ratio_timestamp) gespiegelt.
"""

import json
import shutil
import threading
import time
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".simpleft8"
CALIB_DIR  = CONFIG_DIR / "kalibrierung"
GAIN_VALIDITY_SECONDS  = 6 * 3600  # 6 Stunden (Hardware-Verstaerker)
RATIO_VALIDITY_SECONDS = 3600      # 1 Stunde (atmosphaerisch)
# Backwards-Compat-Alias fuer externe Importe (Default = Gain)
VALIDITY_SECONDS = GAIN_VALIDITY_SECONDS


class PresetStore:
    """Thread-sicherer Preset-Speicher für einen Diversity-Modus."""

    def __init__(self, filename: str):
        """filename: 'presets_standard.json' oder 'presets_dx.json'"""
        self._filename   = filename
        self._mode_label = self._derive_mode_label(filename)
        self._migrate_old_file()                # Alt → Neu verschieben
        self._filepath = CALIB_DIR / filename
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._load()

    # ── Hilfsmethoden ────────────────────────────────────────────────────────

    @staticmethod
    def _derive_mode_label(filename: str) -> str:
        mapping = {
            "presets_standard.json": "Diversity Standard",
            "presets_dx.json":       "Diversity DX",
        }
        return mapping.get(filename, filename.replace(".json", ""))

    def _migrate_old_file(self) -> None:
        old_path = CONFIG_DIR / self._filename
        new_path = CALIB_DIR  / self._filename
        if old_path.exists() and not new_path.exists():
            CALIB_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_path), str(new_path))
            print(f"[Kalibrierung] Migration: {old_path.name} → kalibrierung/{self._filename}")

    @staticmethod
    def _format_band(key: str) -> str:
        """'40m_FT8' → '40m FT8'"""
        return key.replace("_", " ")

    @staticmethod
    def _age_minutes_from_timestamp(ts: Optional[float]) -> Optional[int]:
        if ts is None:
            return None
        return int((time.time() - ts) / 60)

    @staticmethod
    def _migrate_timestamps_in_entry(entry: dict) -> None:
        """v0.92 → v0.93 Migration: alter 'timestamp' wird auf beide neuen
        Felder gespiegelt. Idempotent — wenn 'gain_timestamp' schon existiert,
        bleibt der Eintrag unangetastet.

        Mutiert das entry-dict in-place. Der alte 'timestamp'-Key bleibt drin
        fuer Backwards-Read-Kompatibilitaet, wird aber nicht mehr aktualisiert.
        """
        if "gain_timestamp" in entry:
            return  # bereits migriert
        old_ts = entry.get("timestamp")
        if old_ts is None:
            return  # nichts zu migrieren
        entry["gain_timestamp"]  = old_ts
        entry["ratio_timestamp"] = old_ts

    # ── Laden / Speichern ────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._filepath.exists():
            try:
                with self._filepath.open("r") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        for key, entry in self._data.items():
            # v0.93 Migration: alter 'timestamp' → gain_timestamp + ratio_timestamp
            self._migrate_timestamps_in_entry(entry)
            band_fmt = self._format_band(key)
            ant1     = entry.get("ant1_gain", "?")
            ant2     = entry.get("ant2_gain", "?")
            measured = entry.get("measured", "unbekannt")
            age      = self._age_minutes_from_timestamp(entry.get("gain_timestamp"))
            age_str  = f"{age} Min." if age is not None else "?"
            print(f"[Kalibrierung] Geladen: {band_fmt} {self._mode_label} — "
                  f"ANT1={ant1}dB ANT2={ant2}dB (gemessen {measured}, {age_str} alt)")

    def _save_locked(self) -> None:
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        with self._filepath.open("w") as f:
            json.dump(self._data, f, indent=2)

    def _key(self, band: str, ft_mode: str) -> str:
        return f"{band}_{ft_mode}"

    # ── Lesen ────────────────────────────────────────────────────────────────

    def get(self, band: str, ft_mode: str) -> Optional[dict]:
        """Preset für Band+FTMode laden oder None."""
        with self._lock:
            return self._data.get(self._key(band, ft_mode))

    def is_valid_gain(self, band: str, ft_mode: str) -> bool:
        """True wenn Gain-Kalibrierung vorhanden UND < 6h alt."""
        with self._lock:
            entry = self._data.get(self._key(band, ft_mode))
        if not entry or "gain_timestamp" not in entry:
            return False
        return (time.time() - entry["gain_timestamp"]) < GAIN_VALIDITY_SECONDS

    def is_valid_ratio(self, band: str, ft_mode: str) -> bool:
        """True wenn Diversity-Ratio vorhanden UND < 1h alt."""
        with self._lock:
            entry = self._data.get(self._key(band, ft_mode))
        if not entry or "ratio_timestamp" not in entry:
            return False
        if "ratio" not in entry:
            return False
        return (time.time() - entry["ratio_timestamp"]) < RATIO_VALIDITY_SECONDS

    def get_gain_age_minutes(self, band: str, ft_mode: str) -> Optional[int]:
        """Alter der Gain-Kalibrierung in Minuten oder None."""
        with self._lock:
            entry = self._data.get(self._key(band, ft_mode))
        if not entry or "gain_timestamp" not in entry:
            return None
        return self._age_minutes_from_timestamp(entry["gain_timestamp"])

    def get_ratio_age_minutes(self, band: str, ft_mode: str) -> Optional[int]:
        """Alter der Diversity-Ratio in Minuten oder None."""
        with self._lock:
            entry = self._data.get(self._key(band, ft_mode))
        if not entry or "ratio_timestamp" not in entry:
            return None
        return self._age_minutes_from_timestamp(entry["ratio_timestamp"])

    # ── Backwards-Compat (v0.92-API, leitet auf Gain-Variante) ──────────────

    def is_valid(self, band: str, ft_mode: str) -> bool:
        """[v0.92-Alias] Aequivalent zu is_valid_gain()."""
        return self.is_valid_gain(band, ft_mode)

    def get_age_minutes(self, band: str, ft_mode: str) -> Optional[int]:
        """[v0.92-Alias] Aequivalent zu get_gain_age_minutes()."""
        return self.get_gain_age_minutes(band, ft_mode)

    # ── Schreiben ────────────────────────────────────────────────────────────

    def save_gain(self, band: str, ft_mode: str, *,
                  rxant: str, ant1_gain: int, ant2_gain: int,
                  ant1_avg: float = 0.0, ant2_avg: float = 0.0) -> None:
        """Gain-Kalibrierung speichern (setzt gain_timestamp → startet 6h-Frist)."""
        key = self._key(band, ft_mode)
        with self._lock:
            entry = dict(self._data.get(key) or {})
            entry.update({
                "rxant":          rxant,
                "ant1_gain":      int(ant1_gain),
                "ant2_gain":      int(ant2_gain),
                "ant1_avg":       round(float(ant1_avg), 1),
                "ant2_avg":       round(float(ant2_avg), 1),
                "gain_timestamp": time.time(),
                "measured":       time.strftime("%Y-%m-%d %H:%M"),
            })
            self._data[key] = entry
            self._save_locked()
        band_fmt = self._format_band(key)
        print(f"[Kalibrierung] Gespeichert: {band_fmt} {self._mode_label} — "
              f"ANT1={ant1_gain}dB ANT2={ant2_gain}dB")

    def save_ratio(self, band: str, ft_mode: str, *,
                   ratio: str, dominant: Optional[str]) -> None:
        """Diversity-Ratio nach Einmessen ergänzen (setzt ratio_timestamp → 1h-Frist)."""
        key = self._key(band, ft_mode)
        with self._lock:
            entry = dict(self._data.get(key) or {})
            entry["ratio"]           = ratio
            entry["dominant"]        = dominant or "A1"
            entry["ratio_timestamp"] = time.time()
            self._data[key]          = entry
            self._save_locked()
        band_fmt = self._format_band(key)
        print(f"[Kalibrierung] Ratio gespeichert: {band_fmt} {self._mode_label} "
              f"→ {ratio} (dominant: {dominant or 'A1'})")

    # ── Migration aus config.json ─────────────────────────────────────────────

    def migrate_from_settings(self, settings_data: dict, mode: str = "standard") -> None:
        """Einmalige Migration aus altem config.json-Format."""
        with self._lock:
            if self._data:
                return

            gain_key = "dx_presets" if mode == "standard" else "dx_gain_presets"
            migrated = 0

            for raw_key, entry in settings_data.get(gain_key, {}).items():
                if not isinstance(entry, dict):
                    continue
                key = self._normalize_key(raw_key)
                if not key:
                    continue
                existing = dict(self._data.get(key) or {})
                old_ts = entry.get("timestamp", time.time() - GAIN_VALIDITY_SECONDS - 1)
                existing.update({
                    "rxant":          entry.get("rxant", "ANT1"),
                    "ant1_gain":      int(entry.get("ant1_gain", entry.get("gain", 10))),
                    "ant2_gain":      int(entry.get("ant2_gain", entry.get("gain", 10))),
                    "ant1_avg":       float(entry.get("ant1_avg", 0.0)),
                    "ant2_avg":       float(entry.get("ant2_avg", 0.0)),
                    "gain_timestamp": old_ts,
                    "measured":       entry.get("measured", ""),
                })
                self._data[key] = existing
                migrated += 1

            for raw_key, entry in settings_data.get("diversity_presets", {}).items():
                if not isinstance(entry, dict):
                    continue
                key = self._normalize_key(raw_key)
                if not key:
                    continue
                existing = dict(self._data.get(key) or {})
                existing["ratio"]           = entry.get("ratio", "50:50")
                existing["dominant"]        = entry.get("dominant", "A1")
                # Ratio aus Migration: timestamp aus altem Eintrag oder konservativ alt
                existing["ratio_timestamp"] = entry.get(
                    "timestamp", time.time() - RATIO_VALIDITY_SECONDS - 1
                )
                self._data[key] = existing

            if migrated:
                self._save_locked()
                print(f"[Kalibrierung] Migriert: {migrated} Einträge → {self._filepath.name}")

    def _normalize_key(self, raw_key: str) -> Optional[str]:
        """Verschiedene Key-Formate auf band_FTMODE normalisieren."""
        FT_MODES = ("FT8", "FT4", "FT2")
        if "_" not in raw_key:
            return f"{raw_key}_FT8"
        parts = raw_key.split("_", 1)
        if parts[0] in FT_MODES:
            return f"{parts[1]}_{parts[0]}"
        if parts[1] in FT_MODES:
            return raw_key
        return None
