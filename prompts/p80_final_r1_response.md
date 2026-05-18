[deepseek] ~35544 Tokens, 5 File(s) → deepseek-v4-pro
[deepseek] V4-Pro denkt — kann 6-30s dauern ...
[deepseek] in=40716 out=4890 total=45606
## Final-R1 Review: P80 Unified Gain Store (v0.97.52)

### 1. R1-Findings korrekt umgesetzt
- **F1 ROT** → `_check_diversity_preset` prüft `ant2_calibrated`; bei `False` wird zwingend DXTuneDialog ausgelöst, kein direkter Diversity-Start. ✅  
- **F2 ROT** → `is not None`-Guards in `_apply_normal_mode` und `_on_connected` vorhanden; `ant1_gain=0` wird als gültiger Wert akzeptiert. ✅  
- **F3 ORANGE** → Std/DX-Divergenz-Log in `_on_dx_tune_accepted` eingebaut. ✅  
- **F4 ORANGE** → Cancel-Pfad (`_on_dx_tune_rejected`) prüft `ant2_calibrated is True` vor Stale-Acceptance; bei `False` wird Diversity deaktiviert. ✅  
- **F5 GELB** → Migration-Side-Effect im Modul-Docstring dokumentiert. ✅  
- **F7 GELB** → `ts=0.0`-Test in zwei Testdateien vorhanden. ✅  
- **F6 GELB** → README/Doku optional, kein Code-Eingriff nötig. ⚪ (nicht blockierend)

### 2. Production-Bug-Fix `gain_scoring`
Die fehlende Variable in `_check_diversity_preset` wurde korrekt rekonstruiert (`"snr"` für DX, `"stations"` sonst) und an `_start_dx_tuning` übergeben. Keine weiteren Variablen-Lücken ersichtlich. ✅

### 3. Aufrufer-Komplettheit
- Alle alten Store-Referenzen (`_standard_store`, `_dx_store`, `_get_diversity_store`) sind entfernt.
- `get_normal_preset` / `save_normal_preset` nur noch als deprecated Stubs in `settings.py`; **kein** Aufruf in Productions-Code (`mw_radio.py`, `main_window.py`).
- MainWindow nutzt ausschließlich `self._gain_store = PresetStore()`. ✅

### 4. Migration-Edge-Cases
- `_safe_load_json` fängt `FileNotFoundError`, `JSONDecodeError`, `OSError` → robust.  
- `normal_presets` ohne parsebares Datum → `ts=0.0`.  
- Idempotenz: zweiter Init ist no-op; keine Duplikate.  
- Kein File-Lock nötig (Single-Process). ✅

### 5. Backwards-Compat-Aliase
`is_valid` und `get_age_minutes` leiten korrekt auf die neuen Gain-Methoden um. ✅

### 6. Hardware-Pflicht ⛔
TX-Pfade unberührt. ANT1-Pflicht intakt. `ant2_calibrated=False` (Migration) verhindert Diversity mit `ant2_gain=0`. ✅

### 7. Test-Coverage
21 neue Tests + 21 angepasste Alttests. Die wichtigsten Pfade (Migration, API-Change, R1-Verhalten, Settings) sind abgedeckt. Keine offensichtlichen Lücken. ✅

### 8. Doku-Updates
HISTORY/HANDOFF/CLAUDE/TODO/Memory stehen noch aus – keine funktionale Auswirkung, kein Push-Blocker.

---

## **Push-Empfehlung: PUSH FREIGEGEBEN**

Keine Regression, alle ROT/ORANGE-Findings korrekt implementiert, Code konsistent, Tests grün. Der Unified Gain Store kann produktiv eingesetzt werden.
