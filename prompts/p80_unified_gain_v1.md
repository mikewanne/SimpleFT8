# P80 — Unified Gain Store (1 Messung pro Band)

**Status:** V1 (Draft, vor Self-Review V2).
**Datum:** 2026-05-18 nach Compact, Mike unterwegs — autonomer Workflow.
**Mike-Trigger:** „nein mache p80 vollen workflow mit deepseek völlig
autonom debbugt und fix selber wenn probleme oder fragen rücksprache mit
deepseek halten ich muss weg".

---

## Problem-Bild (Mike-Wortlaut)

> „wir müssen unbedingt die gain messung nur für das band machen und nicht
> noch für die einzelnen modis wie ft8 / ft4 / ft2. sondern einfach nur für
> das band speichern und wenn man auf das band geht egal ob direkt ft2 oder
> ft4 oder ft8 diese gain werte laden. für alle 3 modis einen wert."
>
> „es reicht doch eine einzige messung für Normal Diversity standart und
> dx und egal welcher modus oder nicht?"

**Mike-Logik (technisch korrekt):**
- ANT1+ANT2-Gain ist Hardware-Eigenschaft (Antennen-Resonanz + Vorverstärker).
- FT8/FT4/FT2 nutzen gleiche Frequenz, gleiche ~3 kHz Bandbreite,
  gleichen Audio-Pegel-Zielwert (−12 dBFS RMS).
- Normal = ANT1-only, Diversity = beide aktiv, aber Hardware-Gain identisch.
- Std vs DX = nur Scoring-Unterschied (Stations vs SNR<-10), Hardware-Gain
  identisch (P51 v0.97.28 hat das bereits genutzt).
- DXTuneDialog misst IMMER ANT1+ANT2 (selbst in Normal-Mode laut Z.30-40
  Interleaved-Schedule).
- → **1 Messung pro Band reicht für alle Modi/Kombinationen.**

**Daten-Realitäts-Check (`~/.simpleft8/kalibrierung/`):**
- 20m_FT8: in BEIDEN Files identisch (P51-Effekt — Werte gleich)
- 20m_FT4: nur in DX (P51-pre Messung)
- 40m_FT8: in BEIDEN Files identisch
- 15m_FT8, 30m_FT8: gemischt
→ Wertehöhe-Konflikte unwahrscheinlich, aber Migration muss alle Quellen
   konsolidieren.

---

## Architektur-Spec

### Neuer Store

**Datei:** `~/.simpleft8/kalibrierung/presets.json`

**Schema:**
```json
{
  "20m": {
    "ant1_gain": 10,
    "ant2_gain": 10,
    "ant1_avg": -15.0,
    "ant2_avg": -15.8,
    "rxant": "ANT1",
    "gain_timestamp": 1779081747.65,
    "measured": "2026-05-18 07:22"
  },
  "40m": {...}
}
```

**Was rausfällt vs. heute:**
- Key-Suffix `_FT8`/`_FT4`/`_FT2` weg — Key ist nur Band.
- Kein 2-Store-Split mehr (standard + dx) — 1 Store, Auswertung im Aufrufer.
- `ratio`/`dominant`/`ratio_timestamp` bleiben unangetastet (P34-Stufe2 hat
  sie schon irrelevant gemacht, Dynamic-Pipeline regelt live).
- `normal_presets` in Settings → migriert in den unified Store (gain wird
  zum ANT1-only-Wert; ANT2 bleibt 0/null falls keine Messung).

### API-Änderung

**Neu `core/preset_store.py`:**

```python
class PresetStore:
    """Unified Gain-Store (P80, v0.97.52).

    1 Eintrag pro Band — Hardware-Gain identisch fuer FT8/FT4/FT2,
    Normal-Modus nutzt ant1_gain, Diversity Std/DX nutzen beide.
    Scoring-Auswertung (Stations vs SNR) ist Aufrufer-Sache.
    """

    def __init__(self, filename: str = "presets.json"): ...

    def get(self, band: str) -> Optional[dict]: ...
    def is_valid_gain(self, band: str) -> bool: ...
    def get_gain_age_minutes(self, band: str) -> Optional[int]: ...

    def save_gain(self, band: str, *,
                  rxant: str, ant1_gain: int, ant2_gain: int,
                  ant1_avg: float = 0.0, ant2_avg: float = 0.0) -> bool: ...

    # P22 Stage/Commit/Discard (bleiben — atomares Persist):
    def stage_gain(self, band: str, *, rxant, ant1_gain, ant2_gain,
                   ant1_avg=0.0, ant2_avg=0.0) -> None: ...
    def commit_gain(self, band: str) -> bool: ...
    def discard_staged(self, band: str) -> bool: ...
    def discard_all_staged(self) -> int: ...
    def has_staged(self, band: str) -> bool: ...
```

**Komplett raus:** `ft_mode`-Parameter überall.
**Legacy-Aliase:** `is_valid(band, ft_mode=None)` als Wrapper, der
`ft_mode` ignoriert — verhindert Crash bei Übergangs-Code, deprecated-Print.

### Migration aus alten Files

**Strategie:** „Jüngster gain_timestamp wins pro Band".

```python
def migrate_legacy_files() -> int:
    """Einmalig: presets_standard.json + presets_dx.json + normal_presets
    aus settings.json zu presets.json mergen.

    Pro Band: nimmt Eintrag mit MAX(gain_timestamp). normal_presets liefert
    nur ant1_gain (ant2_gain=0). PresetStore-Files mit beiden Antennen
    schlagen normal_presets falls jünger.

    Idempotent: wenn presets.json schon existiert und nicht-leer, no-op.
    Alte Files bleiben in-place fuer 1-Version-Rollback, dann manuelle
    Cleanup-Empfehlung im Print.
    """
    new_store_path = CALIB_DIR / "presets.json"
    if new_store_path.exists():
        with new_store_path.open() as f:
            existing = json.load(f)
        if existing:
            return 0  # bereits migriert
    candidates: dict[str, dict] = {}
    # Read presets_standard.json + presets_dx.json
    for legacy in ("presets_standard.json", "presets_dx.json"):
        path = CALIB_DIR / legacy
        if not path.exists():
            continue
        with path.open() as f:
            data = json.load(f)
        for key, entry in data.items():
            band, _, _ft = key.partition("_")  # "20m_FT8" → "20m", "FT8"
            if not band or not entry.get("gain_timestamp"):
                continue
            existing = candidates.get(band)
            if existing is None or entry["gain_timestamp"] > existing["gain_timestamp"]:
                candidates[band] = {
                    "ant1_gain": int(entry.get("ant1_gain", 10)),
                    "ant2_gain": int(entry.get("ant2_gain", 10)),
                    "ant1_avg":  float(entry.get("ant1_avg", 0.0)),
                    "ant2_avg":  float(entry.get("ant2_avg", 0.0)),
                    "rxant":     entry.get("rxant", "ANT1"),
                    "gain_timestamp": float(entry["gain_timestamp"]),
                    "measured":  entry.get("measured", "?"),
                }
    # Read settings.normal_presets (gain only — no ANT2)
    settings_data = _load_settings_raw()
    for band, entry in settings_data.get("normal_presets", {}).items():
        if not isinstance(entry, dict):
            continue
        # normal_preset hat kein gain_timestamp — nutze measured-String
        measured = entry.get("measured", "")
        try:
            ts = time.mktime(time.strptime(measured, "%Y-%m-%d %H:%M"))
        except (ValueError, TypeError):
            ts = 0.0  # uralt
        existing = candidates.get(band)
        if existing is None or ts > existing["gain_timestamp"]:
            candidates[band] = {
                "ant1_gain": int(entry.get("gain", 10)),
                "ant2_gain": 0,  # normal_preset hat keinen ANT2
                "ant1_avg":  0.0,
                "ant2_avg":  0.0,
                "rxant":     entry.get("rxant", "ANT1"),
                "gain_timestamp": ts,
                "measured":  measured,
            }
    if candidates:
        CALIB_DIR.mkdir(parents=True, exist_ok=True)
        tmp = new_store_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(candidates, indent=2))
        tmp.replace(new_store_path)
        print(f"[P80] Migration: {len(candidates)} Baender → presets.json")
    return len(candidates)
```

**Edge-Cases:**
- Wenn normal_preset nur `gain` (ant2_gain=0) und das gewinnt → Diversity-
  Wechsel löst Re-Kalibrierung aus (`is_valid_gain` evtl. via `ant2_gain==0`
  Check als „braucht Re-Mess"? — V2 prüfen).
- Edge: alle Files leer → keine candidates → presets.json bleibt nicht
  existent, normales App-Verhalten (Erst-Kalibrierung).

### Aufrufer-Updates

**`ui/main_window.py:208-211`:**
```python
# ALT:
self._standard_store = PresetStore("presets_standard.json")
self._dx_store = PresetStore("presets_dx.json")
# NEU:
self._gain_store = PresetStore("presets.json")  # P80 unified
```

**`ui/mw_radio.py:_get_diversity_store(scoring)` → entfällt.** Alle
Aufrufer rufen `self._gain_store` direkt.

**`ui/mw_radio.py:_assess_gain(band, ft_mode, scoring)`:**
```python
def _assess_gain(self, band: str) -> str:
    """P80: ft_mode + scoring entfallen — 1 Wert pro Band."""
    store = self._gain_store
    if store.is_valid_gain(band):
        return "fresh"
    entry = store.get(band)
    if entry and "gain_timestamp" in entry:
        return "stale"
    return "missing"
```

**`ui/mw_radio.py:_on_dx_tune_accepted` (Z.1558-1627):**
- Dual-Save (Std + DX) raus.
- 1 Save in `_gain_store.save_gain(band, ...)`.
- Schreibt ant1_gain + ant2_gain immer (kommt aus Dialog).
- Normal-Mode-Branch (Z.1646-1661) bleibt ANT1-only-Anwendung
  (`set_rfgain(ant1_g)`), aber speichert ebenfalls in `_gain_store`
  statt `settings.save_normal_preset`.

**`ui/mw_radio.py:_apply_normal_preset` / `_show_normal_preset_age_info`:**
- Liest aus `_gain_store.get(band)` statt `settings.get_normal_preset`.
- Wenn `ant2_gain==0` (von normal_preset migriert) → trotzdem ok für Normal.
- Wenn nur `ant1_gain` da und kein ANT2 → bei Diversity-Wechsel als
  „missing" werten (Re-Kalibrierung).

**`config/settings.py:get_normal_preset` / `save_normal_preset`:**
- Deprecated, returnen leeres dict / no-op mit Print.
- `Settings.load()` poppt `normal_presets`-Key idempotent (analog P47).

### `_apply_normal_preset` Logik

```python
def _apply_normal_preset(self, band: str):
    """P80: Normal-Modus laedt ant1_gain aus dem unified gain_store."""
    entry = self._gain_store.get(band) or {}
    if entry.get("ant1_gain"):
        gain = entry["ant1_gain"]
        label = "kalibriert"
        measured = entry.get("measured", "")
    else:
        gain = PREAMP_PRESETS.get(band, 10)
        label = "Standard"
        measured = ""
    if self.radio.ip:
        self.radio.set_rx_antenna("ANT1")
        self.radio.set_tx_antenna("ANT1")
        self.radio.set_rfgain(gain)
    self.control_panel.dx_info.setText(f"G{gain}dB ({label})")
```

---

## Aenderungs-Liste (kompakt)

| Datei | Aenderung | LOC |
|---|---|---|
| `core/preset_store.py` | API: `ft_mode` raus, default filename, migrate_legacy_files() | -50/+80 |
| `ui/main_window.py:208-211` | 2 Stores → 1 Store | -2/+1 |
| `ui/mw_radio.py` | _get_diversity_store raus, _assess_gain vereinfacht, _on_dx_tune_accepted single-save, _apply_normal_preset aus gain_store | -80/+50 |
| `config/settings.py` | get/save_normal_preset deprecated, load() poppt | -25/+10 |
| `main.py` oder `core/preset_store.py` | migrate_legacy_files()-Call beim Boot | +5 |
| `tests/test_p80_unified_gain.py` NEU | Migration + API + Aufrufer | ~25 Tests |
| Old Tests | An neue API anpassen (3-5 Files mit `save_gain(band, ft_mode, ...)`) | ~30 Zeilen |
| `main.py` | APP_VERSION 0.97.51 → 0.97.52 | +1/-1 |

**Geschätzt netto:** Code -120 LOC (Vereinfachung!), Tests +200 LOC.

---

## Test-Plan

**Source-Level (PresetStore-Methode-Signaturen):**
- T1: `PresetStore` Default-Filename = `"presets.json"`.
- T2: `save_gain` Signature ohne `ft_mode`-Parameter.
- T3: `is_valid_gain(band)` ohne ft_mode-Parameter.
- T4: `migrate_legacy_files` ist callable.

**Funktional (PresetStore-Unit):**
- T5: `save_gain` + `get` + `is_valid_gain` Round-Trip.
- T6: `is_valid_gain` False wenn > 6h alt.
- T7: `stage_gain` + `commit_gain` Atomic-Persist (analog P22).
- T8: `discard_staged` löscht Memory-Buffer.

**Migration (PresetStore-Integration):**
- T9: Migration aus 2 Legacy-Files → 1 Eintrag pro Band, jüngster wins.
- T10: Migration mit normal_presets → ant2_gain=0 bei ANT1-only-Source.
- T11: Migration idempotent (2. Aufruf no-op).
- T12: Migration robust gegen leere/fehlende Files.
- T13: Migration robust gegen korrupte JSON (Skip mit Print).

**Aufrufer (Source-Level + Smoke):**
- T14: `mw_radio._assess_gain` Signature: nur `band`.
- T15: `mw_radio._on_dx_tune_accepted` ruft `_gain_store.save_gain` (single, kein dual).
- T16: `mw_radio._apply_normal_preset` liest aus `_gain_store`, nicht Settings.
- T17: `settings.get_normal_preset` returnt leeres dict (deprecated).

**Old-Tests-Anpassung:**
- alle `save_gain(band, ft_mode, ...)` → `save_gain(band, ...)`.
- alle `is_valid_gain(band, ft_mode)` → `is_valid_gain(band)`.
- alle `PresetStore("presets_standard.json")` / `_dx.json` → testen
  mit beliebigem Filename (z.B. tmp_path) → API gleich.

---

## Hardware-Pflicht-Check ⛔

P80 ist Daten-Schicht (PresetStore + Settings). Keine Antennen-Schaltung,
kein TX-Trigger neu. ANT1-Pflicht intakt.

**Wichtig:** Normal-Modus-Migration setzt ant2_gain=0, NICHT ant2_gain=10.
Wenn `_apply_normal_preset` ANT2 unbenutzt lässt, ist 0 harmlos (kein
RX-Path aktiv). Bei Diversity-Wechsel ohne valide ANT2-Werte fällt es
in „missing" → Re-Kalibrierung (DXTuneDialog) → ANT2 misst sich neu.
Kein Hardware-Risiko.

---

## Offene Fragen für V2/R1

1. **`ant2_gain==0` als „braucht Re-Mess"?** Wenn Diversity-Wechsel und
   Migration aus normal_preset (ohne ANT2-Wert): soll `is_valid_gain`
   False zurückgeben damit Re-Kalibrierung läuft? V1 Vorschlag: ja, via
   Sentinel-Wert oder dediziertem Feld `ant2_calibrated: bool`.
2. **Disk-Räumung der alten Files:** sofort beim Migration-Run löschen,
   oder eine Version warten + Print-Hinweis? V1: 1 Version warten,
   nächste Major-Version cleanup.
3. **`save_normal_preset` API:** komplett raus oder Deprecated-Stub mit
   internem Forward an `_gain_store.save_gain`? V1: Stub mit Forward
   um Backwards-Compat von externen Tools (gibt's nicht, aber sicher).
4. **`gain_timestamp` der `normal_preset`-Migration:** das `measured`-
   String ist nur „2026-05-18 07:22"-Format, kann zu Sekunde 0 parsen.
   Akzeptabel oder soll `time.time() - 24h` als „uralt" gesetzt werden?
   V1: parse `measured`, fallback `0.0`.
5. **DT-Korrektur (`FT8_20m`):** bleibt mode-aware. Nicht vermischen
   mit Gain. Klarer Unterschied: DT = Decoder-Timing (FT8-Buffer 2.0s,
   FT4 1.0s, FT2 0.8s), Gain = Hardware-Pegel (modus-unabhängig).

---

## Push-Plan

P80 als v0.97.52. Field-Test pending:
- F1 (ohne Radio): App-Start mit alten Files → Migration läuft, presets.json
  erstellt, Print-Log zeigt N Bänder migriert.
- F2 (ohne Radio): Erneuter Start → presets.json unverändert (idempotent).
- F3 (mit Radio): Normal-Kalibrierung 20m FT8 → ANT1+ANT2 in presets.json.
- F4 (mit Radio): Wechsel auf 20m FT4 → KEIN Re-Mess, Gain-Werte vorhanden,
  Statusbar zeigt „fresh".
- F5 (mit Radio): Wechsel auf 20m FT2 → ebenso fresh.
- F6 (mit Radio): Diversity-Wechsel 20m → keine neue Messung nötig, Werte
  übernommen.

---

**Naechster Schritt:** V2 Self-Review:
- Halluzinations-Check Methoden-Namen (`_apply_normal_preset` existiert?)
- Edge-Case `ant2_gain==0`-Erkennung sauber durchdacht?
- Migration-Atomicity: tempfile.rename oder os.replace?
- Locking: PresetStore hat threading.Lock — neue API auch?
