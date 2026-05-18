# P80 — Unified Gain Store V3 (Final-Spec)

**Status:** V3 (für Code-Phase).
**R1-Bilanz:** 7 Findings (2 ROT F1+F2, 2 ORANGE F3+F4, 3 GELB F5-F7).
ALLE übernommen — auch GELB für Klarheit.
**Push-Empfehlung R1:** FREIGEGEBEN nach V3 wenn F1+F2 behoben.

---

## Acceptance Criteria

### AC1 — Unified `presets.json` Schema mit `ant2_calibrated`
- `~/.simpleft8/kalibrierung/presets.json`
- Key = Band only (`"20m"`, `"40m"`), kein FT-Modus-Suffix.
- Felder: `ant1_gain`, `ant2_gain`, `ant1_avg`, `ant2_avg`, `rxant`,
  `ant2_calibrated` (bool), `gain_timestamp`, `measured`.

### AC2 — `core/preset_store.py` API ohne `ft_mode`
- `get(band)`, `is_valid_gain(band)`, `get_gain_age_minutes(band)`
- `save_gain(band, *, rxant, ant1_gain, ant2_gain, ant1_avg, ant2_avg, ant2_calibrated=True)`
- `stage_gain`, `commit_gain`, `discard_staged`, `has_staged`,
  `discard_all_staged` — alle nur `band`.
- `is_valid_gain` returnt False bei `gain_timestamp==0.0` (Migration-Marker).

### AC3 — Migration `migrate_legacy_files()`
- Liest 2 Legacy-PresetStore-Files + `settings.json`-`normal_presets`.
- Pro Band: MAX(gain_timestamp) wins.
- `ant2_calibrated=True` bei PresetStore-Quelle, `False` bei normal_presets.
- Idempotent (no-op wenn `presets.json` existiert + non-empty).
- Robust gegen korrupte JSON (`_safe_load_json` mit Print + Skip).
- Läuft in `PresetStore.__init__` wenn `filename="presets.json"`.
- **Docstring im PresetStore-Header dokumentiert Migration-Side-Effect** (R1-F5).

### AC4 — `_check_diversity_preset` prüft `ant2_calibrated` (R1-F1 ROT)
**Pflicht — sonst Hardware-Risiko bei Diversity-Wechsel nach Migration!**

```python
def _check_diversity_preset(self, band: str, scoring: str) -> None:
    if not getattr(self, 'radio', None) or not self.radio.ip:
        return
    # P63 AC8: Marker-Pre-Check (unverändert)
    if band.upper() in self._swr_blocked_bands:
        ...
        return

    store = self._gain_store
    entry = store.get(band)
    # P80 (R1-F1 ROT): Diversity-Wechsel braucht ANT2-Kalibrierung.
    # Migration aus normal_preset hat ant2_calibrated=False → Re-Mess
    # nötig damit Diversity nicht mit ant2_gain=0 startet.
    gain_fresh = (
        store.is_valid_gain(band)
        and entry is not None
        and entry.get("ant2_calibrated") is True
    )
    if gain_fresh:
        self._enable_diversity(scoring_mode=scoring)
        self._update_statusbar()
        return
    # Sonst: stale oder ant2_calibrated=False → DXTuneDialog
    self._pending_dx_diversity = True
    self._pending_diversity_scoring = scoring
    ...DXTuneDialog öffnen...
```

### AC5 — `_apply_normal_mode` robuster Fallback (R1-F2 ROT)
```python
def _apply_normal_mode(self):
    band = self.settings.band
    tx_freq = self.settings.get_normal_tx_freq(band)
    self.encoder.audio_freq_hz = tx_freq
    ...

    entry = self._gain_store.get(band)
    # P80 (R1-F2 ROT): `is not None`-Check statt falsy. ant1_gain=0 ist
    # ein gueltiger (wenn auch unwahrscheinlicher) Wert.
    if entry is not None and entry.get("ant1_gain") is not None:
        gain = int(entry["ant1_gain"])
        measured_str = entry.get("measured", "")
        label = "kalibriert" if measured_str else "Standard"
    else:
        gain = PREAMP_PRESETS.get(band, 10)
        measured_str = ""
        label = "Standard"
    # ... (Rest unverändert: age_days-Check, set_rfgain, Warning)
```

Gleiche Logik in `_on_connected:149` Init-Pfad.

### AC6 — DXTuneDialog Log-Warning bei Std/DX-Divergenz (R1-F3 ORANGE)
In `_on_dx_tune_accepted`:
```python
if has_dual:
    std_data = r["standard"]
    dx_data  = r["dx"]
    # P80 (R1-F3): empirisch identisch, defensiv loggen bei Abweichung
    if (std_data.get("ant1_gain") != dx_data.get("ant1_gain")
            or std_data.get("ant2_gain") != dx_data.get("ant2_gain")):
        print(f"[P80] WARN Std/DX-Gain-Divergenz fuer {band}: "
              f"std=({std_data.get('ant1_gain')}/{std_data.get('ant2_gain')}) "
              f"dx=({dx_data.get('ant1_gain')}/{dx_data.get('ant2_gain')}) "
              f"→ nehme std-Werte")
    # Speichere Standard-Werte (Stations-Scoring — immer verfuegbar)
    save_data = std_data
else:
    save_data = r  # alt-Format
self._gain_store.save_gain(
    band,
    rxant=save_data.get("best_ant", "ANT1"),
    ant1_gain=save_data.get("ant1_gain", 0),
    ant2_gain=save_data.get("ant2_gain", 0),
    ant1_avg=save_data.get("ant1_avg", 0.0),
    ant2_avg=save_data.get("ant2_avg", 0.0),
    ant2_calibrated=True,  # DXTuneDialog misst immer beide
)
```

### AC7 — `_on_dx_tune_rejected` Cancel-Pfad (R1-F4 ORANGE Dokumentation)
```python
def _on_dx_tune_rejected(self):
    ...
    if self._rx_mode == "diversity" and self.radio.ip:
        scoring = getattr(self._diversity_ctrl, 'scoring_mode', 'normal')
        band = self.settings.band
        entry = self._gain_store.get(band)
        # P80 (R1-F4): stale-Acceptance braucht ant2_calibrated=True.
        # Reines „stale aber kalibriert" → User hat sich entschieden mit
        # alten Werten weiterzuarbeiten. ant2_calibrated=False (Migration
        # aus normal_preset) → kein Resume, Diversity AUS.
        if (entry is not None
                and "gain_timestamp" in entry
                and entry.get("ant2_calibrated") is True):
            print(f"[Diversity] Cancel → Stale-Acceptance: Gain bleibt")
            self._enable_diversity(scoring_mode=scoring)
            self._stats_warmup_cycles = 6
        else:
            print(f"[Diversity] Cancel ohne ANT2-Kalibrierung → Diversity AUS")
            self._disable_diversity()
            self.control_panel.set_rx_mode("normal")
            self._stats_warmup_cycles = 6
    else:
        ...
```

### AC8 — Aufrufer-Updates Komplett-Liste
1. **`ui/main_window.py:210-211`** — 2 Stores → 1 Store (`self._gain_store`).
2. **`ui/mw_radio.py:_on_connected:149-154`** — `_gain_store.get(band)` mit
   F2-Fallback.
3. **`ui/mw_radio.py:_apply_normal_mode:1811-1858`** — analog F2-Fallback.
4. **`ui/mw_radio.py:_get_diversity_store`** — ENTFAELLT.
5. **`ui/mw_radio.py:_assess_gain`** — nur `band`-Parameter.
6. **`ui/mw_radio.py:_check_diversity_preset`** — `band` + `scoring`, mit
   AC4-Diversity-Check.
7. **`ui/mw_radio.py:_on_dx_tune_accepted`** — single-save mit AC6-Logik.
   Normal-Mode-Branch (Z.1646-1661) ebenfalls in `_gain_store`.
8. **`ui/mw_radio.py:_on_dx_tune_rejected`** — AC7-Logik.
9. **`config/settings.py:get_normal_preset`** — deprecated, returnt `{}`.
10. **`config/settings.py:save_normal_preset`** — deprecated, no-op.
11. **`config/settings.py:Settings.load`** — poppt `normal_presets`-Key.

### AC9 — Tests
**Neue Datei `tests/test_p80_unified_gain.py`** mit 28 Tests:
- T1-T8: PresetStore-Unit (siehe V1).
- T9-T14: Migration (Roundtrip mit `tmp_path`, jüngster-wins, Idempotenz,
  korrupte JSON, normal_preset-Source, ant2_calibrated-Marker).
- T15: `gain_timestamp=0.0` → `is_valid_gain` False (R1-F7).
- T16-T20: Aufrufer Source-Level (kein `_get_diversity_store`, kein
  `_standard_store`, single-save).
- T21: `_check_diversity_preset` ohne `ant2_calibrated` startet KEINE
  Diversity (R1-F1 Test).
- T22: `_apply_normal_mode` mit `ant1_gain=0` nutzt 0 nicht PREAMP_PRESETS
  (R1-F2 Test).
- T23: Std/DX-Divergenz löst Log-Warning aus (R1-F3 Test).
- T24-T28: Smoke-Tests + APP_VERSION 0.97.52.

**Alte Test-Files anpassen (6+):**
- `test_preset_store.py` — neue API
- `test_p51_unified_gain.py` — Dual-Save-Tests obsolet, nun single-save
- `test_p34_stufe2.py` — `commit_gain(band)` ohne ft_mode
- `test_p22_preset_atomic.py` — `stage_gain(band, ...)`
- `test_p1_cache_simple.py` — Mock-Store-API
- `test_diversity_cache_reuse.py` — API-Anpassung

---

## Implementations-Reihenfolge (atomare Commits)

1. **C1** `core/preset_store.py` — komplett-rewrite API + Migration.
2. **C2** `tests/test_preset_store.py` + `test_p22_preset_atomic.py` +
   `test_p34_stufe2.py` — API-Anpassung.
3. **C3** `tests/test_p80_unified_gain.py` NEU.
4. **C4** `ui/main_window.py:210-211` — 1 Store.
5. **C5** `ui/mw_radio.py` Aufrufer-Updates (alle Pfade).
6. **C6** `config/settings.py` — deprecated + Pop.
7. **C7** `tests/test_p51_unified_gain.py` + `test_p1_cache_simple.py`
   + `test_diversity_cache_reuse.py` — Anpassung.
8. **C8** `main.py` APP_VERSION 0.97.51 → 0.97.52 + Backup.
9. **C9** HISTORY/HANDOFF/CLAUDE/TODO/Memory.

---

## Field-Test-Plan (V3 §6, alle ohne Radio möglich)

- **F1 — Migration Run:** App-Start mit alten Files → Print zeigt
  „[P80] Migration: N Bänder → presets.json". Datei existiert.
- **F2 — Idempotenz:** Erneuter App-Start → kein Migration-Log.
- **F3 — Modus-Wechsel ohne Re-Mess:** 20m FT8 → 20m FT4 → 20m FT2:
  KEIN DXTuneDialog, KEIN Re-Mess. Gain bleibt.
- **F4 (Radio):** Normal-Kalibrierung 20m → Wechsel auf Diversity 20m
  → fresh + ant2_calibrated=True → kein Re-Mess.
- **F5 (Radio):** Wechsel auf 30m wo nur normal_preset-Migration vorlag
  → Diversity-Klick → Re-Mess wird ausgelöst (ant2_calibrated=False).
- **F6 — Settings:** `settings.json` enthält `normal_presets` nach
  Load+Save NICHT mehr (idempotent gepoppt).

---

## Hardware-Pflicht-Check ⛔

P80 ist Daten-Schicht. Aber R1-F1 ROT war Hardware-relevant: Diversity-
Wechsel mit `ant2_gain=0` würde RX-Pegel auf ANT2 falsch setzen, mit
Konsequenzen für Empfangs-Qualität (kein TX-Risiko, aber „App ist
taub").

AC4-Fix verhindert das. ANT1-Pflicht (TX) komplett unverändert.

---

## LOC-Bilanz V3

| Datei | LOC |
|---|---|
| `core/preset_store.py` | -100/+130 (Refactor + Migration) |
| `ui/main_window.py` | -2/+1 |
| `ui/mw_radio.py` | -110/+70 (4 Aufrufer + AC4+AC5+AC6+AC7) |
| `config/settings.py` | -25/+12 |
| `main.py` | +0/+1 |
| `tests/test_p80_unified_gain.py` NEU | +280 |
| Old-Tests-Anpassung (6 Files) | ~70 Zeilen |
| **Netto Code** | **~-100 LOC** (deutlich schlanker) |
| **Netto + Tests** | **+250 LOC** |

---

**Naechster Schritt:** Code-Phase, beginnend mit C1
(`core/preset_store.py`-Rewrite). Backup vorher: `Appsicherungen/
2026-05-18_v0.97.51_vor_p80/` mit den 5 Files.
