# P80 — Final-R1 Review nach Code-Phase

## Kontext

Voller V1→V2→R1→V3→Code-Workflow durchgezogen. R1 hat „PUSH FREIGEGEBEN
nach V3" gesagt nach 9 Findings (2 ROT F1+F2, 2 ORANGE F3+F4, 3 GELB F5-F7).
ALLE übernommen. Code ist jetzt eingespielt + 1517 Tests grün (von 1496 →
+21 P80 inkl. neue T1-T19 + 2 Old-Test-Adaptions).

**Du sollst jetzt FINAL-R1:** den tatsaechlich eingebauten Code gegen die
V3-Spec + R1-V1-Findings pruefen. Findest du Regressionen, übersehene
Edge-Cases, KISS-Verletzungen, falsche Implementation der R1-Findings?

**V4-pro 26→27-Cycle-Bilanz:** 0 Halluzinationen.

---

## Was implementiert wurde

### C1 `core/preset_store.py` (komplett-rewrite)
- API: `band`-only (kein `ft_mode` mehr).
- `_SYMBOL_COLORS` raus (war P79), neues `ant2_calibrated`-Feld.
- `migrate_legacy_files()` im `PresetStore.__init__` wenn
  `filename="presets.json"`. Idempotent + robust (`_safe_load_json`).
- Migration-Strategie: pro Band MAX(gain_timestamp) über
  `presets_standard.json` + `presets_dx.json` + `settings.normal_presets`.
- `ant2_calibrated=True` bei PresetStore-Quelle, `False` bei normal_presets.
- `is_valid_gain` returnt False bei `ts==0.0` (Migration-Marker).
- Stage/Commit/Discard alle nur `band`.
- Legacy-Aliase `is_valid`, `get_age_minutes` weiterhin auf neue API.

### C2 `ui/main_window.py`
- 2 Stores → 1 Store `self._gain_store = PresetStore()`.
- `closeEvent` discard_all_staged für 1 Store.

### C3 `ui/mw_radio.py` Aufrufer (6 Pfade)
- `_on_connected:149-154`: `_gain_store.get(band)` mit `is not None`-Check
  (R1-F2 ROT).
- `_apply_normal_mode:1811`: `_gain_store.get(band)` mit `is not None`-Check.
- `_get_diversity_store`: entfernt.
- `_assess_gain(band)`: ohne `ft_mode`/`scoring`.
- `_check_diversity_preset(band, scoring)`: prüft `ant2_calibrated=True`
  für Diversity-Wechsel (R1-F1 ROT).
- `_on_dx_tune_accepted`: single-save in `_gain_store.save_gain(band,
  ant2_calibrated=True)`, Std/DX-Divergenz-Log-Warning (R1-F3 ORANGE),
  Normal-Mode-Branch ohne `save_normal_preset`-Aufruf mehr.
- `_on_dx_tune_rejected`: `_gain_store.get(band)` + `ant2_calibrated`-Check
  für Stale-Acceptance (R1-F4 ORANGE).
- `_enable_diversity` Preset-Load über `_gain_store.get(band)`.
- `_disable_diversity` discard_staged.
- `_apply_dx_preset_for_band`: `_gain_store.get(band)`.
- `_on_mode_changed` Normal-Modus-Warnung über `_gain_store.get(band)`.

### C4 `config/settings.py`
- `get_normal_preset(band)` → `{}` mit Deprecated-Print.
- `save_normal_preset(...)` → no-op mit Deprecated-Print.
- `Settings.load()` poppt `normal_presets` idempotent.

### C5 `main.py`
- APP_VERSION 0.97.51 → 0.97.52.

### C6 Tests (`tests/`)
- `test_p80_unified_gain.py` NEU mit 19 Tests:
  - Migration (jüngster-wins, ant2_calibrated, normal_presets,
    Idempotenz, korrupte JSON, ts=0.0).
  - API-Signatur-Locks (kein ft_mode in `_assess_gain`/
    `_check_diversity_preset`, kein `_get_diversity_store`).
  - R1-F1 Verhalten (`ant2_calibrated=False` → DXTuneDialog).
  - R1-F2 Source-Level (`is not None`-Check).
  - R1-F3 Source-Level (Std/DX-Divergenz-Log).
  - Settings-Deprecation.
  - main_window unified store.
- `test_preset_store.py` komplett neu mit P80-API (23 Tests).
- `test_p51_unified_gain.py` umgeschrieben auf single-save (3 Tests).
- `test_p1_cache_simple.py` API umgestellt (5 Tests + 2 redundante).
- `test_p34_stufe2.py` 1 Test API-Anpassung.
- `test_p62_bandchange_ux.py` Signatur-Anpassung + Marker-Text.
- `test_p79_ui_bundle.py` APP_VERSION 0.97.52.

### C7 Backup
- `Appsicherungen/2026-05-18_v0.97.51_vor_p80/` mit 5 Files.

---

## Final-R1 Pruefliste

1. **R1-Findings korrekt umgesetzt?**
   - F1 ROT (ant2_calibrated-Check in `_check_diversity_preset`)
   - F2 ROT (`is not None`-Fallback in `_apply_normal_mode` und
     `_on_connected`)
   - F3 ORANGE (Std/DX-Divergenz-Log)
   - F4 ORANGE (Cancel-Pfad ant2_calibrated)
   - F5 GELB (Migration-Side-Effect dokumentiert in Klassen-Docstring)
   - F7 GELB (ts=0.0 Test)
   - F6 GELB (README/Doku — TODO später, optional)

2. **Production-Bug-Fix:** `gain_scoring` Variable wurde im V3-Refactor
   versehentlich aus `_check_diversity_preset` entfernt, aber Z.1329
   nutzte sie noch (NameError im Live). Nachfix eingebaut. Prüfen ob
   das die einzige Variable-Lücke war.

3. **Aufrufer-Komplettheit:** habe ich alle Aufrufer von alten Stores
   erwischt? Pflicht-Check: `_standard_store`, `_dx_store`,
   `_get_diversity_store`, `get_normal_preset`, `save_normal_preset`
   in Production-Code dürfen NICHT mehr referenziert sein.

4. **Migration-Edge-Cases:**
   - `_safe_load_json` returnt `{}` bei FileNotFoundError / JSONDecodeError
   - normal_presets-Migration mit unparseable measured → ts=0.0
   - Idempotenz: 2. Init = no-op
   - Race-Condition: 1 Instanz Single-Process — kein File-Lock nötig

5. **Backwards-Compat-Aliase:** `is_valid` und `get_age_minutes` leiten
   weiter auf neue API. Externe Skripte bekommen kein Crash, höchstens
   ein deprecated-Verhalten.

6. **Hardware-Pflicht ⛔:** P80 berührt keine TX-Pfade. ANT1-Pflicht
   intakt. R1-F1 schützt ANT2 vor Migration-induziertem 0-dB-Bug.

7. **Test-Coverage:** 21 neue Tests + 21 angepasste alte Tests. Reicht
   das? Wo bestehen noch Lücken?

8. **Doku-Updates:** HISTORY/HANDOFF/CLAUDE/TODO/Memory noch ausstehend.

---

## Push-Empfehlung

„**PUSH FREIGEGEBEN**" oder „**PUSH BLOCKIERT WEGEN F<x>**".

Anbei: V1, V2, V3, sowie die geänderten Files (core/preset_store.py,
ui/mw_radio.py, ui/main_window.py, config/settings.py,
tests/test_p80_unified_gain.py, tests/test_preset_store.py, main.py).
