# P80 — Unified Gain Store V2 (Self-Review)

**Status:** V2 (Self-Review nach V1, vor R1 DeepSeek).
**Methodik:** alle V1-Behauptungen mit Read+Grep gegen aktuellen Code
verifiziert. Findings F1-F10 mit „Quelle / Korrektur / Wirkung auf V3".

---

## V1-Verifikation

| V1-Behauptung | Verifikation | Status |
|---|---|---|
| `mw_radio.py:208-211` 2 Stores | tatsaechlich `main_window.py:210-211` | ❌ Datei falsch |
| `_get_diversity_store` Z.1247 | bestätigt | ✓ |
| `_assess_gain(band, ft_mode, scoring)` Z.1252 | bestätigt | ✓ |
| `_on_dx_tune_accepted` Z.1558 | bestätigt | ✓ |
| `_apply_normal_mode` (nicht `_apply_normal_preset`!) Z.1811 | V1 hat Methode falsch benannt | ❌ HALLU |
| Settings `get_normal_preset` Z.271 | bestätigt | ✓ |
| Settings `save_normal_preset` Z.279 | bestätigt | ✓ |
| `_normal_preset_warned_bands` set Z.268 main_window | bestätigt | ✓ |
| `_on_connected` (Z.149) liest `get_normal_preset` | nicht in V1 erwähnt — neuer Aufrufer | ❌ Lücke |
| `_on_dx_tune_rejected` (Z.1736) ruft `_get_diversity_store(scoring).get(band, ft_mode)` | nicht in V1 erwähnt — neuer Aufrufer | ❌ Lücke |
| Tests: `test_p51_unified_gain.py`, `test_p34_stufe2.py`, `test_p1_cache_simple.py`, `test_preset_store.py`, `test_p22_preset_atomic.py`, `test_diversity_cache_reuse.py` mit alter API | V1 sagte „3-5 Files" | ❌ Tatsaechlich 6+ Files |

---

## Findings (V2-Self-Review)

### F1 — Methoden-Halluzination `_apply_normal_preset` ❌

**V1 schrieb:** „`ui/mw_radio.py:_apply_normal_preset` / `_show_normal_preset_age_info`"

**Code-Realitaet:** Die Methode heißt `_apply_normal_mode` (Z.1811),
nicht `_apply_normal_preset`. Außerdem gibt es noch `_on_connected` (Z.140)
der `get_normal_preset` ruft.

**Korrektur fuer V3:**
- Aufrufer `get_normal_preset` zu fixen: `_apply_normal_mode` (Z.1821) +
  `_on_connected` (Z.149).
- Aufrufer `save_normal_preset` zu fixen: `_on_dx_tune_accepted` (Z.1650).
- `_show_normal_preset_age_info` heißt korrekt — ruft nichts weiter relevantes.

### F2 — Zusätzlicher Aufrufer in `_on_dx_tune_rejected` ❌

**V1 hat übersehen:** `_on_dx_tune_rejected` (Z.1733-1737) ruft beim
Cancel-Pfad `_get_diversity_store(scoring).get(band, ft_mode)` um zu
prüfen ob Gain-Werte da sind → Stale-Acceptance oder Diversity-Aus.

**Korrektur fuer V3:** in der API-Migration auch diesen Pfad anpassen:
```python
store = self._gain_store
entry = store.get(band)  # ohne ft_mode
```

### F3 — `_on_connected` Normal-Preset-Pfad ❌

**V1 hat übersehen:** `mw_radio:149-154` ruft beim Connect
`settings.get_normal_preset(band)` und setzt `radio.set_rfgain(gain)`.
Das ist ein wichtiger Initial-Pfad und muss gleichermaßen auf
`_gain_store` umgestellt werden — sonst greift Init-Gain nicht.

**Korrektur fuer V3:** `_on_connected` auch refactorn.

### F4 — Test-Migration unterschätzt ❌

**V1 sagte „3-5 Files".** **Tatsaechlich 6+ Files mit alter API:**
- `tests/test_p51_unified_gain.py` (Dual-Store-Tests — werden komplett
  überholt, evtl. ganze Tests obsolet weil 1-Store)
- `tests/test_p34_stufe2.py` (z.B. `commit_gain("40m", "FT8")`)
- `tests/test_p1_cache_simple.py` (Mock-Store mit `is_valid_gain` 2-args)
- `tests/test_preset_store.py` (Unit-Tests der API)
- `tests/test_p22_preset_atomic.py` (Stage/Commit-Tests)
- `tests/test_diversity_cache_reuse.py`

**Korrektur fuer V3:**
- Globale Sed: `save_gain(band, ft_mode, ` → `save_gain(band, `
- Globale Sed: `is_valid_gain(band, ft_mode)` → `is_valid_gain(band)`
- Globale Sed: `get(band, ft_mode)` → `get(band)` (im PresetStore-Scope)
- `PresetStore("presets_standard.json")` Konstruktor: nur als
  Default-Test akzeptabel — V3 zeigt einen konkreten Migrations-Plan.
- `tests/test_p51_unified_gain.py` komplett überdenken — Dual-Save
  ist Geschichte. Test wird neu: „single save in gain_store".

### F5 — `ant2_gain==0` Sentinel zu fragil 🟠

**V1 schlug:** „`ant2_gain==0` deutet auf Normal-only-Migration".

**Problem:** ein gültiger Gain-Wert kann theoretisch 0 sein (z.B. wenn
Antenne sehr empfindlich + Vorverstärker minimal). Falsch-positiv.

**Korrektur fuer V3:** dediziertes boolesches Feld
`ant2_calibrated: bool` (True nur wenn echte ANT2-Messung erfolgte).
Migration setzt: True wenn aus PresetStore-File, False wenn aus
settings.normal_presets.

**Logik in `is_valid_gain`:** zusätzlicher Parameter `requires_ant2: bool=False`?
ODER: einfach „missing" returnen wenn rx_mode=diversity und
`ant2_calibrated=False`. Mike-Logik: das ist Aufrufer-Sache.

Empfehlung V3: PresetStore bleibt simpel (`is_valid_gain(band)` checkt
nur Alter), Aufrufer in mw_radio prüft `entry.get("ant2_calibrated", False)`
wenn rx_mode=diversity. Belastung im Aufrufer-Code, aber klarere Semantik.

### F6 — Settings.normal_presets Migration vs. Disk-Inhalt 🟡

**V1 hat nicht verifiziert:** wo speichert Settings tatsaechlich
normal_presets? Antwort: in `~/.simpleft8/settings.json` (Settings ist
Wrapper). Migration muss diese Datei lesen.

**Korrektur fuer V3:** `migrate_legacy_files()` braucht Zugriff auf das
Settings-Object oder direkt `settings.json`-Pfad. Da die Migration im
`PresetStore`-Modul steht, kein direkter Settings-Zugriff. Optionen:
- (a) Migration ruft `from config.settings import Settings; s = Settings(); s.load()`
- (b) Migration nimmt `settings.json`-Pfad direkt
- (c) Migration läuft in `main.py`-Boot-Phase, übergibt Daten an
  PresetStore.

**Empfehlung V3:** (b) — `presets.normal_presets`-Migration liest
`CONFIG_DIR / "settings.json"` direkt als JSON, kein Settings-Object
nötig. KISS, kein Coupling auf Settings-Klasse.

### F7 — Race beim ersten Start: Boot-Reihenfolge 🟠

V1 hatte: „`main.py` ruft `migrate_legacy_files()` beim Boot".

**Problem:** `PresetStore.__init__` ruft `_load()`. Wenn `presets.json`
noch nicht existiert und Migration nicht gelaufen, ist `_data={}`. Erst
nach Migration sind Werte da → aber `__init__` wurde schon ausgeführt.

**Korrektur fuer V3:** Migration MUSS vor `PresetStore("presets.json")`
laufen. Alternative: `__init__` ruft `migrate_legacy_files()` selbst
(idempotent, schadet nicht). Empfehlung: ins `__init__` einbauen,
fail-silent.

```python
def __init__(self, filename: str = "presets.json"):
    ...
    self._filepath = CALIB_DIR / filename
    if filename == "presets.json":
        try:
            migrate_legacy_files()
        except Exception as exc:
            print(f"[P80] Migration-Fehler (fail-silent): {exc}")
    self._load()
```

### F8 — Locking-Konsistenz neue API 🟡

**V1-Code zeigte:** alle neuen Methoden haben weiterhin `with self._lock`.
**Verifiziert:** Original-`PresetStore` nutzt `threading.Lock()` (Z.45).
✓ behalten, P80 ändert nichts daran.

### F9 — Test-Coverage Edge-Case Migration mit korrupter JSON 🟡

V1 erwähnte T13 (robust gegen korrupte JSON), aber konkrete
Implementation fehlt:

```python
def _safe_load_json(path: Path) -> dict:
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[P80] Konnte {path.name} nicht lesen: {exc} → übersprungen")
        return {}
```

### F10 — `_normal_preset_warned_bands` Set 🟡

Das Set `_normal_preset_warned_bands` (`main_window.py:268`) wird in
`_apply_normal_mode` (Z.1852) genutzt um 30-Tage-Warnung pro Band+Session
einmalig zu zeigen. Bei Umstellung auf `_gain_store` bleibt die Logik —
nur Daten-Quelle ändert sich (`entry.get("measured")` statt
`preset.get("measured")`).

→ kein Refactor nötig, nur Datenquelle anpassen.

---

## Halluzinations-Check V1 → V2

| V1-Claim | Verifikation | Status |
|---|---|---|
| `_apply_normal_preset` als Methodenname | ❌ heißt `_apply_normal_mode` | KORRIGIERT |
| 3-5 Test-Files | ❌ 6+ Files | KORRIGIERT |
| `ant2_gain==0` als Sentinel | ⚠ fragil | KORRIGIERT zu `ant2_calibrated:bool` |
| `_on_connected` Aufrufer | ❌ vergessen | KORRIGIERT |
| `_on_dx_tune_rejected` Aufrufer | ❌ vergessen | KORRIGIERT |
| Migration in `__init__` oder `main.py` | unklar | KORRIGIERT zu `__init__` (idempotent) |
| Settings.normal_presets Pfad | unklar | KORRIGIERT zu Direkt-Read `settings.json` |

**Halluzinations-Rate V1:** ca. 5 von 12 verifizierbaren Claims daneben.
Höher als P79 — Grund: P80 ist komplexerer Refactor mit mehr Aufruferpfaden.
V2 hat alle aufgedeckt.

---

## Korrigierter V3-Vorschlag (kompakt)

### 1. `core/preset_store.py` (Refactor + Migration)

```python
"""SimpleFT8 Unified Gain Store (P80, v0.97.52).

1 Eintrag pro Band — Hardware-Gain identisch fuer FT8/FT4/FT2,
Normal-Modus nutzt ant1_gain, Diversity Std/DX nutzen beide.
"""
import json, os, shutil, tempfile, threading, time
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".simpleft8"
CALIB_DIR  = CONFIG_DIR / "kalibrierung"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
GAIN_VALIDITY_SECONDS = 6 * 3600

def _safe_load_json(path: Path) -> dict:
    try:
        with path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[P80] Konnte {path.name} nicht lesen: {exc} → übersprungen")
        return {}


def migrate_legacy_files() -> int:
    """P80: einmalige Migration der 2 Legacy-PresetStore-Files +
    settings.normal_presets in unified presets.json.

    Strategie: pro Band der Eintrag mit MAX(gain_timestamp) wins.
    `ant2_calibrated: bool` markiert ob aus echter Diversity-Messung
    (True) oder Normal-only-Migration (False).

    Idempotent: wenn presets.json existiert UND nicht-leer, no-op.
    """
    new_path = CALIB_DIR / "presets.json"
    if new_path.exists():
        existing = _safe_load_json(new_path)
        if existing:
            return 0
    candidates: dict[str, dict] = {}
    # 1) Legacy PresetStore-Files
    for legacy in ("presets_standard.json", "presets_dx.json"):
        data = _safe_load_json(CALIB_DIR / legacy)
        for key, entry in data.items():
            if not isinstance(entry, dict):
                continue
            band = key.split("_")[0]  # "20m_FT8" → "20m"
            ts = entry.get("gain_timestamp")
            if not band or ts is None:
                continue
            existing = candidates.get(band)
            if existing is None or ts > existing["gain_timestamp"]:
                candidates[band] = {
                    "ant1_gain":        int(entry.get("ant1_gain", 10)),
                    "ant2_gain":        int(entry.get("ant2_gain", 10)),
                    "ant1_avg":         float(entry.get("ant1_avg", 0.0)),
                    "ant2_avg":         float(entry.get("ant2_avg", 0.0)),
                    "rxant":            entry.get("rxant", "ANT1"),
                    "gain_timestamp":   float(ts),
                    "measured":         entry.get("measured", "?"),
                    "ant2_calibrated":  True,
                }
    # 2) settings.normal_presets (nur ant1_gain)
    settings_data = _safe_load_json(SETTINGS_PATH)
    for band, entry in settings_data.get("normal_presets", {}).items():
        if not isinstance(entry, dict):
            continue
        measured = entry.get("measured", "")
        try:
            ts = time.mktime(time.strptime(measured, "%Y-%m-%d %H:%M"))
        except (ValueError, TypeError):
            ts = 0.0
        existing = candidates.get(band)
        if existing is None or ts > existing["gain_timestamp"]:
            candidates[band] = {
                "ant1_gain":       int(entry.get("gain", 10)),
                "ant2_gain":       0,
                "ant1_avg":        0.0,
                "ant2_avg":        0.0,
                "rxant":           entry.get("rxant", "ANT1"),
                "gain_timestamp":  ts,
                "measured":        measured,
                "ant2_calibrated": False,
            }
    if candidates:
        CALIB_DIR.mkdir(parents=True, exist_ok=True)
        tmp = new_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(candidates, indent=2))
        tmp.replace(new_path)
        print(f"[P80] Migration: {len(candidates)} Baender → presets.json")
    return len(candidates)


class PresetStore:
    """Unified Gain-Store (P80, v0.97.52)."""

    def __init__(self, filename: str = "presets.json"):
        self._filename = filename
        self._filepath = CALIB_DIR / filename
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._staged: dict[str, dict] = {}
        # P80: Migration vor Load (idempotent)
        if filename == "presets.json":
            try:
                migrate_legacy_files()
            except Exception as exc:
                print(f"[P80] Migration-Fehler (fail-silent): {exc}")
        self._load()

    def _load(self) -> None:
        self._data = _safe_load_json(self._filepath)
        for band, entry in self._data.items():
            age = self._age_minutes_from_timestamp(entry.get("gain_timestamp"))
            age_str = f"{age} Min." if age is not None else "?"
            print(f"[Kalibrierung] Geladen: {band} — "
                  f"ANT1={entry.get('ant1_gain', '?')}dB "
                  f"ANT2={entry.get('ant2_gain', '?')}dB "
                  f"calibrated={entry.get('ant2_calibrated', '?')} ({age_str} alt)")

    @staticmethod
    def _age_minutes_from_timestamp(ts: Optional[float]) -> Optional[int]:
        if ts is None or ts == 0.0:
            return None
        return int((time.time() - ts) / 60)

    def get(self, band: str) -> Optional[dict]:
        with self._lock:
            return self._data.get(band)

    def is_valid_gain(self, band: str) -> bool:
        with self._lock:
            entry = self._data.get(band)
        if not entry or "gain_timestamp" not in entry:
            return False
        ts = entry["gain_timestamp"]
        if ts == 0.0:
            return False  # Migration-Marker, soll Re-Kalibrierung triggern
        return (time.time() - ts) < GAIN_VALIDITY_SECONDS

    def get_gain_age_minutes(self, band: str) -> Optional[int]:
        with self._lock:
            entry = self._data.get(band)
        if not entry:
            return None
        return self._age_minutes_from_timestamp(entry.get("gain_timestamp"))

    def save_gain(self, band: str, *, rxant: str, ant1_gain: int,
                  ant2_gain: int, ant1_avg: float = 0.0,
                  ant2_avg: float = 0.0, ant2_calibrated: bool = True) -> bool:
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
        print(f"[Kalibrierung] Gespeichert: {band} — ANT1={ant1_gain}dB "
              f"ANT2={ant2_gain}dB calibrated={ant2_calibrated}")
        return True

    # stage_gain / commit_gain / discard_staged / has_staged
    # — identische API, nur `band`-Param.

    def _save_locked(self) -> None: ...  # unverändert P22-Pattern
```

### 2. `ui/main_window.py:210-211` (1 Store)

```python
# ALT:
self._standard_store = PresetStore("presets_standard.json")
self._dx_store = PresetStore("presets_dx.json")
# NEU:
self._gain_store = PresetStore()  # default presets.json, mit auto-migration
```

### 3. `ui/mw_radio.py`

- `_on_connected:149-154`: liest aus `_gain_store.get(band)` statt
  `settings.get_normal_preset(band)`. Fallback `PREAMP_PRESETS`.
- `_apply_normal_mode:1811-1858`: liest aus `_gain_store.get(band)`,
  Logik (Alter, Warnung) bleibt identisch.
- `_get_diversity_store`: ENTFAELLT.
- `_assess_gain:1252`: nur `band`-Parameter.
- `_check_diversity_preset:1267`: nur `band`-Parameter.
- `_on_dx_tune_accepted:1558`: single-save `_gain_store.save_gain(band, ...)`.
  Dual-Save-Block weg. Normal-Mode-Branch (Z.1646-1661) speichert ebenfalls
  in `_gain_store` (mit `ant2_calibrated=True` weil DXTuneDialog beide misst).
- `_on_dx_tune_rejected:1733-1748`: `_gain_store.get(band)` statt
  `_get_diversity_store(scoring).get(band, ft_mode)`. Diversity-Cancel mit
  vorhandenen Werten: prüfen ob `ant2_calibrated=True` → Stale-Acceptance.

### 4. `config/settings.py`

- `get_normal_preset(band)`: deprecated, returnt `{}` + Print.
- `save_normal_preset(...)`: deprecated, no-op + Print.
- `Settings.load()`: poppt `normal_presets`-Key idempotent.

### 5. `main.py`

APP_VERSION → 0.97.52. Kein expliziter Migration-Call nötig, läuft im
PresetStore-`__init__`.

### 6. Tests-Anpassung

**Komplett zu überarbeiten:**
- `tests/test_preset_store.py`: API neu (`band`-only).
- `tests/test_p51_unified_gain.py`: Dual-Save-Tests obsolet → 1-Save-Tests.
- `tests/test_p34_stufe2.py`: `commit_gain(band)` ohne ft_mode.
- `tests/test_p22_preset_atomic.py`: `stage_gain(band, ...)` ohne ft_mode.
- `tests/test_p1_cache_simple.py`: Mock-Stores mit neuer API.
- `tests/test_diversity_cache_reuse.py`: API-Anpassung.

**NEU `tests/test_p80_unified_gain.py`:**
- T1-T8 PresetStore-Unit (siehe V1)
- T9-T13 Migration (siehe V1, robuster mit `_safe_load_json`)
- T14-T17 Aufrufer-Smoke

---

## LOC-Bilanz Final V2

| Datei | LOC |
|---|---|
| `core/preset_store.py` | -90/+110 (Refactor + Migration) |
| `ui/main_window.py` | -2/+1 |
| `ui/mw_radio.py` | -100/+60 (4 Aufrufer-Stellen) |
| `config/settings.py` | -25/+10 |
| `main.py` | +0/+1 (APP_VERSION) |
| `tests/test_p80_unified_gain.py` NEU | +250 |
| Old-Tests-Anpassung (6 Files) | ~60 Zeilen geändert |
| **Netto Code** | **~-90 LOC** (deutlich schlanker) |
| **Netto + Tests** | **+220 LOC** |

---

## Offene Fragen für R1 DeepSeek-Review

1. **`ant2_calibrated`-Sentinel:** ist ein boolesches Feld sauberer als
   `ant2_gain==0`-Check? Alternative: separate Schwelle (`ant2_gain<5` =
   uncalibrated)? V1 schlug 0, V2 schlug boolean. R1-Vote.
2. **Migration in `__init__`:** Side-Effects im Konstruktor — schlecht
   für Tests (Mock-Filesystem nötig). Alternative: lazy via Property
   oder explicit-Call in `main.py`. R1-Empfehlung.
3. **`presets_standard.json` + `presets_dx.json` nach Migration:** löschen,
   umbenennen zu `.bak`, oder bleiben lassen? V2-Default: bleiben (1
   Version Rollback-Puffer). R1-Vote.
4. **`is_valid_gain` Diversity-Check:** soll PresetStore intern wissen ob
   ANT2 nötig ist, oder bleibt das Aufrufer-Sache? V2-Empfehlung Aufrufer
   (KISS).
5. **`commit_gain` ohne FT-Mode:** alte Stage-Mit-Mode-Pfade (z.B.
   `mw_cycle._handle_diversity_measure`) müssen auf neue API. Tests
   sicher überall korrigiert?
6. **Backwards-Compat-Aliase:** soll `save_gain(band, ft_mode, ...)` als
   deprecated-Wrapper mit Print bleiben für 1 Version? V2-Empfehlung:
   nein (alle Aufrufer im Repo, 1 Refactor sauberer).
7. **DXTuneDialog `_get_results`:** liefert heute „standard"/„dx"-Sub-Keys
   (P51). Nach P80 wird der single-save in `_gain_store.save_gain` nur
   eine der beiden Auswertungen nehmen — welche? Vorschlag: nimm die
   `best_gain`-Daten der „standard"-Auswertung (Stations-Score), weil
   die immer existiert und Std+DX-Gain-Werte identisch sind. Aber: was
   wenn Std und DX leicht abweichen (z.B. unterschiedliche Top-5-SNR-
   Auswahl)?

---

**Naechster Schritt:** R1-Prompt schreiben mit V1+V2 + PresetStore +
mw_radio (4 Pfade) + dx_tune_dialog (1 Sektion) + settings.py.
Frage R1 zur ant2_calibrated-Strategie + Migration-in-init Side-Effect.
