"""SimpleFT8 RFPresetStore — konvergierte rfpower-Werte pro (Radio, Band, Watt).

Persistiert den finalen rfpower-Slider-Wert (0-100) damit der Closed-Loop nach
Band/Watt-Wechsel nicht von Null hochtasten muss. Hybrid-Lade-Strategie:
exakter Treffer → lineare Interpolation/Extrapolation → None.

Datei: ~/.simpleft8/rf_presets.json
Format:
    {
      "flexradio": {
        "40m": {"30": {"rf": 24, "ts": 1735203015.5},
                "80": {"rf": 67, "ts": 1735206015.0}}
      },
      "ic7300": {}
    }

Beim IC-7300-Fork ggf. Spline-Interpolation prüfen (PA-Sättigung im oberen Bereich
kann lineare Interpolation systematisch unterschätzen).
"""

import json
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".simpleft8"
DEFAULT_PATH = CONFIG_DIR / "rf_presets.json"

PLAUSIBILITY_THRESHOLD = 0.20
MIN_RF = 0
MAX_RF = 100


class RFPresetStore:
    """Persistiert konvergierte RF-Slider-Werte pro (Radio, Band, Watt)."""

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else DEFAULT_PATH
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, dict[str, dict]]] = {}
        self._load()

    # ── Laden / Speichern ────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        try:
            with self._path.open("r") as f:
                raw = json.load(f)
        except Exception as e:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = self._path.with_name(self._path.name + f".bak.{stamp}")
            try:
                shutil.copy2(str(self._path), str(backup))
                print(f"[RF-Preset] JSON korrupt — gesichert als {backup.name}: {e}")
            except Exception as ex:
                print(f"[RF-Preset] JSON korrupt, Backup fehlgeschlagen: {ex}")
            self._data = {}
            return

        self._data = {}
        if not isinstance(raw, dict):
            return
        for radio, bands in raw.items():
            if not isinstance(bands, dict):
                continue
            self._data[radio] = {}
            for band, watts in bands.items():
                if not isinstance(watts, dict):
                    continue
                self._data[radio][band] = {}
                for watt_str, entry in watts.items():
                    rf, ts = self._parse_entry(entry)
                    if rf is None or not (MIN_RF <= rf <= MAX_RF):
                        continue
                    self._data[radio][band][str(watt_str)] = {"rf": rf, "ts": ts}

    @staticmethod
    def _parse_entry(entry):
        if isinstance(entry, dict):
            rf = entry.get("rf")
            ts = entry.get("ts", 0.0)
            if isinstance(rf, (int, float)):
                return int(rf), float(ts)
            return None, 0.0
        if isinstance(entry, (int, float)):
            return int(entry), 0.0
        return None, 0.0

    def _save_locked(self) -> None:
        """Atomic write: Tempfile + os.replace (POSIX-atomic)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_name(self._path.name + ".tmp")
        with tmp_path.open("w") as f:
            json.dump(self._data, f, indent=2)
        os.replace(str(tmp_path), str(self._path))

    # ── Lesen ────────────────────────────────────────────────────────────────

    def load(self, radio: str, band: str, watt: int) -> Optional[int]:
        """Hybrid-Lade-Strategie:
        1. exakter Treffer → return rf (mit Plausibilitäts-Check wenn ≥2 Nachbarn)
        2. ≥2 Stützpunkte im (radio, band) → lineare Interpolation/Extrapolation
        3. sonst → None (Default-Verhalten, kein hochtasten gespart)
        """
        with self._lock:
            band_data = self._data.get(radio, {}).get(band, {})
            if not band_data:
                return None

            watt_str = str(int(watt))

            if watt_str in band_data:
                rf = int(band_data[watt_str]["rf"])
                others = {int(w): e["rf"] for w, e in band_data.items()
                          if w != watt_str}
                if len(others) >= 2:
                    interp = self._interpolate(others, int(watt))
                    if interp is not None:
                        self._check_plausibility(rf, interp, f"{band}_{watt}W")
                return rf

            points = {int(w): e["rf"] for w, e in band_data.items()}
            if len(points) >= 2:
                interp = self._interpolate(points, int(watt))
                if interp is not None:
                    return max(MIN_RF, min(MAX_RF, int(round(interp))))

            return None

    @staticmethod
    def _interpolate(points: dict, target: int) -> Optional[float]:
        """Lineare Interpolation/Extrapolation zwischen 2 nächsten Stützpunkten."""
        if len(points) < 2:
            return None
        sorted_watts = sorted(points.keys())

        if target <= sorted_watts[0]:
            w1, w2 = sorted_watts[0], sorted_watts[1]
        elif target >= sorted_watts[-1]:
            w1, w2 = sorted_watts[-2], sorted_watts[-1]
        else:
            w1, w2 = sorted_watts[0], sorted_watts[1]
            for i, w in enumerate(sorted_watts):
                if w >= target:
                    w1, w2 = sorted_watts[i - 1], w
                    break

        rf1, rf2 = points[w1], points[w2]
        if w2 == w1:
            return float(rf1)
        slope = (rf2 - rf1) / (w2 - w1)
        return rf1 + slope * (target - w1)

    @staticmethod
    def _check_plausibility(stored: int, interpolated: float, key: str) -> None:
        if interpolated <= 0:
            return
        delta = abs(stored - interpolated) / abs(interpolated)
        if delta > PLAUSIBILITY_THRESHOLD:
            pct = int(round(delta * 100))
            print(
                f"[RF-Preset] {key}: stored rf={stored}, "
                f"interpolated rf={int(round(interpolated))} ({pct}% Δ) "
                f"— evtl. veraltet"
            )

    def get_all(self, radio: str) -> dict:
        """Snapshot aller Einträge für aktuelles Radio (für UI-Tabelle)."""
        with self._lock:
            bands = self._data.get(radio, {})
            return {
                band: {int(w): dict(entry) for w, entry in watts.items()}
                for band, watts in bands.items()
            }

    # ── Schreiben ────────────────────────────────────────────────────────────

    def save(self, radio: str, band: str, watt: int, rf: int) -> None:
        """Speichert konvergierten rfpower-Wert. Validiert 0-100, sonst Reject + Log."""
        rf = int(rf)
        if not (MIN_RF <= rf <= MAX_RF):
            print(
                f"[RF-Preset] save abgelehnt: rf={rf} außerhalb "
                f"[{MIN_RF},{MAX_RF}]"
            )
            return
        with self._lock:
            self._data.setdefault(radio, {}).setdefault(band, {})[str(int(watt))] = {
                "rf": rf,
                "ts": time.time(),
            }
            self._save_locked()
        print(f"[RF-Preset] gespeichert: {band}_{watt}W → rf={rf}")

    def clear_band(self, radio: str, band: str) -> None:
        with self._lock:
            radio_data = self._data.get(radio, {})
            if band in radio_data:
                del radio_data[band]
                self._save_locked()
                print(f"[RF-Preset] Band gelöscht: {radio}/{band}")

    def clear_all(self, radio: str) -> None:
        with self._lock:
            if radio in self._data:
                self._data[radio] = {}
                self._save_locked()
                print(f"[RF-Preset] alle Presets gelöscht für radio={radio}")

    # ── Migration ────────────────────────────────────────────────────────────

    def migrate_from_settings(
        self,
        settings_data: dict,
        radio: str = "flexradio",
        default_watts: int = 10,
    ) -> None:
        """Einmalige Migration aus config.json `rfpower_per_band` → `rf_presets.json`.

        Nur ausgeführt wenn Tabelle für `radio` bisher leer ist (idempotent).
        """
        with self._lock:
            if self._data.get(radio):
                return
            rfpower_per_band = settings_data.get("rfpower_per_band", {})
            if not rfpower_per_band:
                return
            self._data.setdefault(radio, {})
            migrated = 0
            now = time.time()
            for band, rf in rfpower_per_band.items():
                try:
                    rf_int = int(rf)
                except (TypeError, ValueError):
                    continue
                if not (MIN_RF <= rf_int <= MAX_RF):
                    continue
                self._data[radio].setdefault(band, {})[str(default_watts)] = {
                    "rf": rf_int,
                    "ts": now,
                }
                migrated += 1
            if migrated:
                self._save_locked()
                print(
                    f"[RF-Preset] Migration: {migrated} Band-Einträge "
                    f"aus config.json übernommen (Default-Watt={default_watts}W)"
                )
