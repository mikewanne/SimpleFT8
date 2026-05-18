"""SimpleFT8 Unified Gain Store (P80, v0.97.52).

1 Eintrag pro Band — Hardware-Gain ist Antennen/Vorverstaerker-
Eigenschaft, modus-unabhaengig. FT8/FT4/FT2 nutzen identische Werte.
Normal-Modus liest ant1_gain, Diversity Std/DX nutzt beide Antennen.

Schema (`~/.simpleft8/kalibrierung/presets.json`):
```
{
  "20m": {
    "ant1_gain": 10, "ant2_gain": 20,
    "ant1_avg": -15.0, "ant2_avg": -11.5,
    "rxant": "ANT1",
    "ant2_calibrated": true,
    "gain_timestamp": 1779081747.65,
    "measured": "2026-05-18 07:22"
  }
}
```

`ant2_calibrated` (P80, R1-F1 ROT): markiert ob aus echter ANT1+ANT2-
Messung (True) oder Normal-only-Migration (False). Diversity-Wechsel
verlangt True — sonst Re-Kalibrierung. Schutz gegen ant2_gain=0
Hardware-Fehlanwendung.

Side-Effect-Hinweis: `PresetStore.__init__` ruft beim Default-Filename
`presets.json` einmalig `migrate_legacy_files()` (idempotent). Tests
muessen CALIB_DIR umlenken (tmp_path + monkeypatch).
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".simpleft8"
CALIB_DIR = CONFIG_DIR / "kalibrierung"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
GAIN_VALIDITY_SECONDS = 6 * 3600  # 6 Stunden (Hardware-Verstaerker)
# Backwards-Compat-Alias fuer externe Importe
VALIDITY_SECONDS = GAIN_VALIDITY_SECONDS


def _safe_load_json(path: Path) -> dict:
    """Robust gegen fehlende oder korrupte JSON. Print + leeres dict."""
    try:
        with path.open("r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[P80] Konnte {path.name} nicht lesen: {exc} → uebersprungen")
        return {}


def migrate_legacy_files() -> int:
    """P80: einmalige Migration alter Files in unified ``presets.json``.

    Quellen:
    1. ``presets_standard.json`` (alte Diversity-Standard-Werte)
    2. ``presets_dx.json`` (alte Diversity-DX-Werte)
    3. ``settings.json`` → ``normal_presets`` (Normal-Modus-Gains)

    Strategie: pro Band wird der Eintrag mit MAX(gain_timestamp) zur
    Wahrheit. ``ant2_calibrated=True`` bei PresetStore-Quelle (echte
    ANT1+ANT2-Messung), ``False`` bei normal_presets-Quelle (nur
    ANT1-Wert).

    Idempotent: wenn ``presets.json`` existiert UND nicht-leer → no-op.
    Robust gegen korrupte JSON (``_safe_load_json``).

    Returns: Anzahl migrierter Baender (0 = no-op oder leer).
    """
    new_path = CALIB_DIR / "presets.json"
    existing_new = _safe_load_json(new_path)
    if existing_new:
        return 0  # bereits migriert

    candidates: dict[str, dict] = {}

    # 1+2) Legacy PresetStore-Files
    for legacy in ("presets_standard.json", "presets_dx.json"):
        legacy_data = _safe_load_json(CALIB_DIR / legacy)
        for key, entry in legacy_data.items():
            if not isinstance(entry, dict):
                continue
            # "20m_FT8" → "20m"; "20m" bleibt "20m"
            band = key.split("_")[0]
            ts = entry.get("gain_timestamp")
            if not band or ts is None:
                continue
            try:
                ts = float(ts)
            except (TypeError, ValueError):
                continue
            existing = candidates.get(band)
            if existing is None or ts > existing["gain_timestamp"]:
                candidates[band] = {
                    "ant1_gain":       int(entry.get("ant1_gain", 10)),
                    "ant2_gain":       int(entry.get("ant2_gain", 10)),
                    "ant1_avg":        float(entry.get("ant1_avg", 0.0)),
                    "ant2_avg":        float(entry.get("ant2_avg", 0.0)),
                    "rxant":           entry.get("rxant", "ANT1"),
                    "ant2_calibrated": True,
                    "gain_timestamp":  ts,
                    "measured":        entry.get("measured", "?"),
                }

    # 3) settings.normal_presets (nur ANT1 — kein ANT2-Wert)
    settings_data = _safe_load_json(SETTINGS_PATH)
    normal_presets = settings_data.get("normal_presets", {})
    if isinstance(normal_presets, dict):
        for band, entry in normal_presets.items():
            if not isinstance(entry, dict):
                continue
            measured = entry.get("measured", "")
            try:
                ts = time.mktime(time.strptime(measured, "%Y-%m-%d %H:%M"))
            except (ValueError, TypeError):
                ts = 0.0  # uralt → is_valid_gain returnt False
            existing = candidates.get(band)
            if existing is None or ts > existing["gain_timestamp"]:
                candidates[band] = {
                    "ant1_gain":       int(entry.get("gain", 10)),
                    "ant2_gain":       0,
                    "ant1_avg":        0.0,
                    "ant2_avg":        0.0,
                    "rxant":           entry.get("rxant", "ANT1"),
                    "ant2_calibrated": False,
                    "gain_timestamp":  ts,
                    "measured":        measured,
                }

    if candidates:
        CALIB_DIR.mkdir(parents=True, exist_ok=True)
        tmp = new_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(candidates, indent=2))
        os.replace(str(tmp), str(new_path))
        print(f"[P80] Migration: {len(candidates)} Baender → presets.json")

    return len(candidates)


class PresetStore:
    """Unified Gain-Store (P80, v0.97.52).

    Thread-sicher via ``threading.Lock``. Atomic write via tempfile +
    ``os.replace`` (P22-Pattern, P80 beibehalten).

    Stage/Commit/Discard (P22): Phase-2-Werte landen via ``stage_gain``
    im Memory-Buffer, Phase-3-Erfolg committet via ``commit_gain``.
    Ohne Commit kein Disk-Write — verhindert Half-State.
    """

    def __init__(self, filename: str = "presets.json"):
        """filename: Default ``presets.json`` (unified, P80).

        Side-Effect: bei Default-Filename triggert einmalige Migration
        aus Legacy-Files (idempotent, fail-silent).
        """
        self._filename = filename
        self._filepath = CALIB_DIR / filename
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._staged: dict[str, dict] = {}
        # P80: Migration vor Load (idempotent, kein Crash bei Fehlern)
        if filename == "presets.json":
            try:
                migrate_legacy_files()
            except Exception as exc:
                print(f"[P80] Migration-Fehler (fail-silent): {exc}")
        self._load()

    # ── Laden / Speichern ──────────────────────────────────────────

    def _load(self) -> None:
        self._data = _safe_load_json(self._filepath)
        for band, entry in self._data.items():
            if not isinstance(entry, dict):
                continue
            age = self._age_minutes_from_timestamp(entry.get("gain_timestamp"))
            age_str = f"{age} Min." if age is not None else "?"
            ant2_cal = entry.get("ant2_calibrated", False)
            print(f"[Kalibrierung] Geladen: {band} — "
                  f"ANT1={entry.get('ant1_gain', '?')}dB "
                  f"ANT2={entry.get('ant2_gain', '?')}dB "
                  f"ant2_cal={ant2_cal} ({age_str} alt)")

    def _save_locked(self) -> None:
        """Atomic Write via tempfile + os.replace (P22-Pattern)."""
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(self._filepath.parent),
            delete=False,
            prefix=".tmp_",
            suffix=".json",
        )
        try:
            json.dump(self._data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp.close()
            os.replace(tmp.name, str(self._filepath))
        except Exception:
            try:
                tmp.close()
            except Exception:
                pass
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    @staticmethod
    def _age_minutes_from_timestamp(ts: Optional[float]) -> Optional[int]:
        if ts is None or ts == 0.0:
            return None
        return int((time.time() - ts) / 60)

    # ── Lesen ───────────────────────────────────────────────────────

    def get(self, band: str) -> Optional[dict]:
        """Preset fuer Band laden oder None."""
        with self._lock:
            return self._data.get(band)

    def is_valid_gain(self, band: str) -> bool:
        """True wenn Gain-Kalibrierung vorhanden UND < 6h alt UND ts > 0.

        ts==0.0 ist Migration-Marker (uralt, normal_preset ohne parsbares
        Datum) → False → triggert Re-Kalibrierung.
        """
        with self._lock:
            entry = self._data.get(band)
        if not entry or "gain_timestamp" not in entry:
            return False
        ts = entry["gain_timestamp"]
        if ts == 0.0:
            return False  # Migration-Marker
        return (time.time() - ts) < GAIN_VALIDITY_SECONDS

    def get_gain_age_minutes(self, band: str) -> Optional[int]:
        """Alter der Kalibrierung in Minuten oder None."""
        with self._lock:
            entry = self._data.get(band)
        if not entry:
            return None
        return self._age_minutes_from_timestamp(entry.get("gain_timestamp"))

    # ── Schreiben (direkt) ─────────────────────────────────────────

    def save_gain(self, band: str, *,
                  rxant: str, ant1_gain: int, ant2_gain: int,
                  ant1_avg: float = 0.0, ant2_avg: float = 0.0,
                  ant2_calibrated: bool = True) -> bool:
        """Gain-Kalibrierung speichern (setzt gain_timestamp → 6h-Frist).

        ant2_calibrated (P80, R1-F1): True = aus echter ANT1+ANT2-
        Messung (DXTuneDialog), False = nur ANT1 (Normal-only-Migration).
        Diversity-Wechsel verlangt True.

        Returns: False bei Disk-Fehler statt Exception bis GUI-Thread.
        """
        with self._lock:
            old = self._data.get(band)
            entry = dict(old or {})
            entry.update({
                "rxant":           rxant,
                "ant1_gain":       int(ant1_gain),
                "ant2_gain":       int(ant2_gain),
                "ant1_avg":        round(float(ant1_avg), 1),
                "ant2_avg":        round(float(ant2_avg), 1),
                "ant2_calibrated": bool(ant2_calibrated),
                "gain_timestamp":  time.time(),
                "measured":        time.strftime("%Y-%m-%d %H:%M"),
            })
            self._data[band] = entry
            try:
                self._save_locked()
            except Exception as exc:
                if old is None:
                    self._data.pop(band, None)
                else:
                    self._data[band] = old
                print(f"[PresetStore] save_gain Disk-Fehler {band}: {exc}")
                return False
        print(f"[Kalibrierung] Gespeichert: {band} — "
              f"ANT1={ant1_gain}dB ANT2={ant2_gain}dB "
              f"ant2_cal={ant2_calibrated}")
        return True

    # ── P22 Atomic Stage / Commit / Discard ────────────────────────

    def stage_gain(self, band: str, *,
                   rxant: str, ant1_gain: int, ant2_gain: int,
                   ant1_avg: float = 0.0, ant2_avg: float = 0.0,
                   ant2_calibrated: bool = True) -> None:
        """P22: Phase-2-Werte in Memory parken. KEIN Disk-Write."""
        with self._lock:
            self._staged[band] = {
                "rxant":           rxant,
                "ant1_gain":       int(ant1_gain),
                "ant2_gain":       int(ant2_gain),
                "ant1_avg":        round(float(ant1_avg), 1),
                "ant2_avg":        round(float(ant2_avg), 1),
                "ant2_calibrated": bool(ant2_calibrated),
            }
        print(f"[Kalibrierung] Staged: {band} — "
              f"ANT1={ant1_gain}dB ANT2={ant2_gain}dB")

    def commit_gain(self, band: str) -> bool:
        """P34-Stufe2: staged Gain atomar persistieren.

        Returns True bei Erfolg, False bei nichts-staged oder Disk-Fehler.
        """
        with self._lock:
            staged = self._staged.get(band)
            if staged is None:
                return False
            old = self._data.get(band)
            entry = dict(old or {})
            entry.update(staged)
            entry["gain_timestamp"] = time.time()
            entry["measured"] = time.strftime("%Y-%m-%d %H:%M")
            self._data[band] = entry
            try:
                self._save_locked()
            except Exception as exc:
                if old is None:
                    self._data.pop(band, None)
                else:
                    self._data[band] = old
                print(f"[PresetStore] commit_gain Disk-Fehler "
                      f"{band}: {exc}. Staged bleibt erhalten.")
                return False
            self._staged.pop(band, None)
        print(f"[Kalibrierung] Atomar committed: {band}")
        return True

    def discard_staged(self, band: str) -> bool:
        """P22: einzelner staged-Eintrag verwerfen."""
        with self._lock:
            removed = self._staged.pop(band, None) is not None
        if removed:
            print(f"[Kalibrierung] Staged verworfen: {band}")
        return removed

    def discard_all_staged(self) -> int:
        """P22: alle staged-Eintraege verwerfen (App-Quit-Pfad)."""
        with self._lock:
            n = len(self._staged)
            self._staged.clear()
        return n

    def has_staged(self, band: str) -> bool:
        with self._lock:
            return band in self._staged

    # ── Backwards-Compat (v0.92-API, leitet auf Gain-Variante) ─────

    def is_valid(self, band: str) -> bool:
        """[v0.92-Alias] Aequivalent zu is_valid_gain()."""
        return self.is_valid_gain(band)

    def get_age_minutes(self, band: str) -> Optional[int]:
        """[v0.92-Alias] Aequivalent zu get_gain_age_minutes()."""
        return self.get_gain_age_minutes(band)
