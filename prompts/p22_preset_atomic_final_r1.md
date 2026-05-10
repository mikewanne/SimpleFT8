[deepseek] ~59716 Tokens, 7 File(s) → deepseek-reasoner
[deepseek] R1 denkt — kann 6-30s dauern ...
[deepseek] in=66481 out=7098 total=73579
## Review-Ergebnis: P22.PRESET-ATOMARITAET + P8.MESS-MODAL

**KISS-Bewertung:** Gut strukturiert, die meisten Kriterien sauber umgesetzt. Ein **KRITISCHER Bug** in der Adaptiv-Stop-Logik muss vor dem Push behoben werden.

---

### KRITISCH (Bug, muss vor Push raus)

**1. Adaptiv-Stop persistiert trotzdem Ratio in alte Settings (`mw_cycle.py` ~Z. 301–305)**  

**Fundstelle:** `ui/mw_cycle.py` in `_handle_diversity_measure`, ca. Zeile 301 – 305  
**Auszug:**
```python
if _store and not _early_stopped:
    ok = _store.commit_with_ratio(...)
    if not ok:
        _store.save_ratio(...)
elif _early_stopped:
    _store.discard_staged(...)

# Rückwärtskompatibilität – läuft IMMER, auch bei early_stopped:
self.settings.save_diversity_preset(
    mode=self.settings.mode,
    band=self.settings.band,
    ratio=self._diversity_ctrl.ratio,
    dominant=self._diversity_ctrl.dominant,
)
```
**Problem:**  
Bei `_early_stopped=True` wird zwar der staged-Datensatz korrekt verworfen (**A11**), aber unmittelbar danach wird `settings.save_diversity_preset` aufgerufen. Das schreibt die Ratio sofort in die alte `config.json` als vollständigen (aber unzuverlässigen) Eintrag. Dies erzeugt einen **Half-State in den Alt-Settings**: Gain fehlt (oder ist veraltet), Ratio ist vorhanden. Bei einem späteren Laden aus diesen Settings könnte inkonsistentes Verhalten auftreten.

**Lösung:**  
- Die Zeile `self.settings.save_diversity_preset(...)` muss in den `if not _early_stopped`-Zweig (oder zwischen `commit_with_ratio`/`save_ratio` und dem `elif/else` von `_early_stopped`) verschoben werden.  
- Optional: nur aufrufen wenn `not _early_stopped`.  

---

### SOLLTE (Verbesserung empfohlen)

**1. `migrate_from_settings` fehlt Exception-Behandlung (`core/preset_store.py` → `_init_core_components` in `mw_radio.py`)**  

**Fundstelle:** `core/preset_store.py` Zeile ~315 und Aufruf in `ui/main_window.py` `_init_core_components` Zeile ~XX  
**Auszug:**
```python
self._standard_store.migrate_from_settings(self.settings._data, mode="standard")
self._dx_store.migrate_from_settings(self.settings._data, mode="dx")
```
**Problem:**  
`migrate_from_settings` ruft `_save_locked` auf, das bei Disk-Fehler eine Exception re-raised. Der Aufrufer `_init_core_components` fängt diese nicht, was zu einem Start-Crash führen kann. **R1-K3** verlangt, dass alle Schreibmethoden bool returnen – das gilt nicht für `migrate_from_settings`.  

**Lösung:**  
- Entweder `migrate_from_settings` try/except mit log + return False geben und im Aufrufer prüfen, oder im Aufrufer selbst einen try/except-Block um die Migration legen.  

---

### KOENNTE (Optionale Verbesserungen)

**1. Tick-Timer nach `accept()` könnte noch einmal feuern (`ui/mess_status_dialog.py`, `ui/mw_radio.py`)**  

**Begründung:**  
Wenn der Auto-Close (`_close_mess_status_dialog → dlg.accept()`) aufgerufen wird, könnte der `_tick_timer` (500ms) kurz danach noch ein Timeout auslösen, während der Dialog bereits im close ist. Die `_update_view` greift dann auf möglicherweise schon zerstörte Widgets zu.  

**Vorschlag:**  
- In `_close_mess_status_dialog` vor `dlg.accept()` den Timer stoppen:  
  ```python
  try:
      dlg._tick_timer.stop()
  except Exception:
      pass
  dlg.accept()
  ```

**2. `_disable_diversity` könnte staged-Daten bereinigen (`ui/mw_radio.py`)**  

**Begründung:**  
Wenn der User Diversity deaktiviert, während noch staged-Daten im Speicher sind (z.B. nach fehlgeschlagenem `commit_with_ratio`), bleiben diese hängen. Zwar werden sie bei App-Quit via `discard_all_staged` gelöscht, aber bei einer erneuten Diversity-Aktivierung in der gleichen Session könnten sie irreführend sein (z.B. `has_staged` true).  

**Vorschlag:**  
- In `_disable_diversity` optional:
  ```python
  store = self._get_diversity_store(scoring)
  if store:
      store.discard_staged(self.settings.band, self.settings.mode)
  ```

**3. Test für `migrate_from_settings` bei Disk-Fehler fehlt**  

**Begründung:**  
Es gibt keinen Test, der sicherstellt, dass ein Disk-Fehler in der Migration nicht crasht. Ein Integration-Test (Mock der Datei-Operation) wäre wünschenswert, aber nicht blockierend.

---

### Push-Empfehlung

**Push blockiert** – der **KRITISCHE Bug** (Adaptiv-Stop persistiert Ratio in alte Settings) muss zuerst behoben werden. Die SOLLTE-Items sind empfohlen, blockieren aber nicht. Nach dem Fix kann der Code commited werden.

**Checkliste vor Push:**
- [ ] `mw_cycle.py`: `save_diversity_preset` in den `not _early_stopped`-Zweig verschieben.
- [ ] Optional: Exception-Handling für `migrate_from_settings` ergänzen.
- [ ] Neue Tests für den Fix schreiben (z.B. ensure `save_diversity_preset` bei `early_stopped` nicht aufgerufen wird).
- [ ] Alte Tests laufen lassen (1049 grün erwartet).

---

*Review-Datum: 10.05.2026, Version v0.96.6 – alle weiteren Punkte (A1–A14, R1-K1/K2/K3) sind **korrekt adressiert**.*
