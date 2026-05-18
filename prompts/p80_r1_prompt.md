# DeepSeek R1 — P80 Unified Gain Store

## Kontext

V4-pro im R1-Rolle. SimpleFT8 v0.97.51 → 0.97.52. Mike (DA1MHH) ist
unterwegs, autonomer Workflow. Voller V1→V2→R1→V3→Code-Workflow.

**Mike-Trigger (Wortlaut):**
> „wir müssen unbedingt die gain messung nur für das band machen und
> nicht noch für die einzelnen modis wie ft8 / ft4 / ft2. … es reicht
> doch eine einzige messung für Normal Diversity standart und dx und
> egal welcher modus oder nicht?"

**Mike-Logik (technisch korrekt):**
- ANT1+ANT2-Gain ist Hardware-Eigenschaft (Antenne + Vorverstärker).
- FT8/FT4/FT2 nutzen gleiche Frequenz, gleiche ~3 kHz Bandbreite, gleiches
  Audio-Pegel-Ziel (−12 dBFS RMS).
- Normal = ANT1-only, Diversity = beide aktiv, Hardware-Gain identisch.
- P51 (v0.97.28) hatte Std+DX bereits zu „1 Messung, 2 Auswertungen"
  vereinheitlicht — Werte auf Disk SIND identisch (verifiziert).
- DXTuneDialog misst IMMER ANT1+ANT2 interleaved (Z.30-40).
- → 1 Messung pro Band reicht für alle Modi/Kombinationen.

**V4-pro Empirische Bilanz:** 26 Cycles, 0 Halluzinationen.

---

## V2 hat 5 V1-Halluzinationen aufgedeckt

1. Methodenname `_apply_normal_preset` → tatsaechlich `_apply_normal_mode`.
2. Aufrufer `_on_connected:149` vergessen (Normal-Preset bei Connect).
3. Aufrufer `_on_dx_tune_rejected:1733` vergessen (Cancel-Pfad Diversity).
4. „3-5 Test-Files" → tatsaechlich 6+ Files.
5. `ant2_gain==0`-Sentinel zu fragil → `ant2_calibrated: bool`.

V2 hat Korrekturen vorgeschlagen. Du sollst V2 jetzt durchgehen.

---

## V3-Vorschlag aus V2

### Neuer Store `presets.json`

```json
{
  "20m": {
    "ant1_gain": 10, "ant2_gain": 10,
    "ant1_avg": -15.0, "ant2_avg": -15.8,
    "rxant": "ANT1",
    "ant2_calibrated": true,
    "gain_timestamp": 1779081747.65,
    "measured": "2026-05-18 07:22"
  },
  "40m": {...}
}
```

`ft_mode` raus aus Key + API. `ratio`/`dominant` raus (P34-Stufe2-Reste).
Normal-Preset migriert hierhin mit `ant2_calibrated=false`.

### Migration

`migrate_legacy_files()` läuft in `PresetStore.__init__` wenn
`filename="presets.json"`. Strategie:
- Pro Band: MAX(gain_timestamp) wins über alle Quellen
  (presets_standard.json + presets_dx.json + settings.normal_presets).
- `ant2_calibrated`: True wenn aus PresetStore-File (echte Diversity-
  Messung), False wenn aus settings.normal_presets.
- Idempotent: presets.json existiert + non-empty → no-op.
- Robust gegen korrupte JSON via `_safe_load_json`.

### API-Refactor

**Alle Methoden:** `band` only, kein `ft_mode`.
- `get(band)`, `is_valid_gain(band)`, `get_gain_age_minutes(band)`
- `save_gain(band, *, rxant, ant1_gain, ant2_gain, ant1_avg, ant2_avg, ant2_calibrated=True)`
- `stage_gain(band, ...)`, `commit_gain(band)`, `discard_staged(band)`,
  `has_staged(band)`, `discard_all_staged()`

### Aufrufer

**`ui/main_window.py:210-211`:** 2 Stores → 1 Store
```python
self._gain_store = PresetStore()  # default presets.json
```

**`ui/mw_radio.py`:**
- `_on_connected:149-154`: liest aus `_gain_store.get(band)`, Fallback PREAMP_PRESETS.
- `_apply_normal_mode:1811-1858`: liest aus `_gain_store.get(band)`.
- `_get_diversity_store(scoring)`: entfällt.
- `_assess_gain(band)`: ohne ft_mode/scoring.
- `_check_diversity_preset(band)`: ohne ft_mode/scoring (ggf. rx_mode-Branch).
- `_on_dx_tune_accepted:1558`: single-save in `_gain_store`, ant2_calibrated=True.
  Normal-Mode-Branch (Z.1646-1661) speichert ebenfalls in `_gain_store`
  (Dialog misst beide).
- `_on_dx_tune_rejected:1733`: `_gain_store.get(band)` mit
  `ant2_calibrated`-Check für Diversity-Stale-Acceptance.

**`config/settings.py`:**
- `get_normal_preset`, `save_normal_preset` deprecated.
- `Settings.load()` poppt `normal_presets`-Key.

### Tests

6 alte Test-Files anpassen + 1 neuer `test_p80_unified_gain.py` (25
Tests: API + Migration + Aufrufer-Smoke).

---

## Was du als R1 leisten sollst

### Findings nach Schweregrad

🔴 ROT: Bug, Sicherheit, Datenverlust, Race
🟠 ORANGE: Risiko, Edge-Case, KISS-Verletzung
🟡 GELB: Verbesserung, Doku
⚪ WEISS: INFO

### Spezielle Pruef-Punkte

1. **Migration-Edge-Cases:**
   - Was wenn `gain_timestamp=0.0` (von settings.normal_presets ohne
     parsbares `measured`)? V2-Vorschlag: `is_valid_gain` returnt False bei
     ts=0.0 → Re-Kalibrierung. Sinnvoll?
   - Was wenn `presets_standard.json` und `presets_dx.json` beide den
     gleichen Band-Key haben (z.B. 20m_FT8), aber unterschiedliche
     `gain_timestamp`? V2 nimmt MAX. P51 hat sie aber bewusst synchron
     gemacht — Konflikt sollte nicht auftreten. R1: ist das defensiv
     genug?
   - Was wenn ein Band in 3 Quellen ist (Standard + DX + normal_preset)?
     V2: MAX-wins.

2. **`ant2_calibrated`-Konzept:**
   - V2 wählt boolesches Feld statt `ant2_gain==0`-Sentinel.
   - Alternative-Vorschlag aus V2: Aufrufer-Pflicht (mw_radio prüft
     `entry.get("ant2_calibrated", False)` bei Diversity-Wechsel).
   - R1: ist das die richtige Schicht (PresetStore vs Aufrufer)?
     Oder soll `is_valid_gain` einen optionalen `for_diversity: bool`-
     Parameter haben?

3. **Migration im `__init__`:**
   - V2 baut `migrate_legacy_files()` in `PresetStore.__init__` ein.
   - Pros: idempotent, automatisch beim ersten Boot.
   - Cons: Side-Effect im Konstruktor — Tests brauchen Mock-FS oder
     `tmp_path`. Aktuelle PresetStore-Tests instanziieren via
     `tmp_path`/`monkeypatch` → V3 muss CALIB_DIR umlenken können.
   - Konkrete Frage: ist Migration im `__init__` akzeptabel oder
     separater Boot-Call in `main.py`? R1-Vote.

4. **Backwards-Compat:**
   - V2 entscheidet: keine deprecated-Wrapper für 2-args-API. Alle
     Aufrufer im Repo, 1 Refactor sauberer.
   - Risiko: Externe Tools/Skripte? Mike's Use-Case ist privat → kein
     externes Coupling. OK?

5. **DXTuneDialog `get_results`:**
   - Hat heute Sub-Keys `"standard"` + `"dx"` (P51).
   - P80 nimmt nur EINEN Sub-Key (welcher?) für `_gain_store.save_gain`.
   - V2-Vorschlag: nimm „standard" (Stations-Scoring) weil das immer
     funktioniert auch ohne SNR<-10-Stationen.
   - R1: ist das richtig? Sollte stattdessen die ANT1/ANT2-Gain-Werte
     beider Sub-Keys gemerged werden (z.B. Mittel) oder einer als Master?

6. **Race-Conditions:**
   - Migration läuft beim 1. PresetStore-Init. Was wenn 2 Instanzen
     parallel instanziiert werden (unwahrscheinlich)? V2 hat dafür kein
     File-Lock. Single-Process-Garantie ausreichend?

7. **Test-Coverage Lücken:**
   - V2 plant 25 Tests. Was fehlt vor allem?
   - Vorschlag: Migration-Roundtrip mit echter `tmp_path`-Datei (nicht
     nur Mock), `is_valid_gain` False-Cases, `ant2_calibrated`-Auswertung
     in mw_radio Diversity-Wechsel.

8. **Hardware-Pflicht:**
   - P80 berührt keine TX-Pfade. ANT1-Pflicht intakt.
   - Aber: `_apply_normal_mode` ruft `set_rfgain(gain)` mit ant1_gain aus
     Store. Wenn Migration ant1_gain=0 setzt (z.B. korrupte normal_preset),
     wäre Hardware-Gain 0 → RX taub. Soll Default `PREAMP_PRESETS`
     greifen?

### Push-Empfehlung

Am Ende „**PUSH FREIGEGEBEN nach V3**" oder „**BLOCKIERT WEGEN F<x>**".

---

Anbei: V1, V2, sowie 5 Files (core/preset_store.py, ui/main_window.py
Auszug, ui/mw_radio.py, ui/dx_tune_dialog.py, config/settings.py Auszug,
tests/test_preset_store.py).
