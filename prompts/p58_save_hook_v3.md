# P58 — V3: Finale Spec (R1 V4-pro freigegeben, F1 eingearbeitet)

## R1-Findings

| ID | Klasse | Status |
|---|---|---|
| F1 | GELB Verbesserung — Setter-Reihenfolge | **angenommen** |
| F2 | GRAU Hinweis | Keine Aktion |
| F3 | ROT — von V4-pro selbst abgelehnt | Keine Aktion |
| F4 | ORANGE — Clamping bereits aktiv | Keine Aktion |
| F5 | T7 Clamping-Test optional | **abgelehnt** (UI-Range 1.5+ deckt ab) |

**Final-Empfehlung: PUSH FREIGEGEBEN**

## Code-Änderungen

### C1 — `ui/settings_dialog.py:680-683` LÖSCHEN

```python
# RAUS (4 Zeilen):
# P53: Live an Radio propagieren wenn verbunden
parent = self.parent()
if parent is not None and hasattr(parent, "radio") and getattr(parent.radio, "ip", None):
    parent.radio.set_swr_limit(self.swr_limit.value())
```

### C2 — `ui/main_window.py:_on_settings_clicked` Setter-Block neu strukturieren (F1)

**VORHER:**
```python
if dialog.exec():
    self._update_statusbar()
    self.qso_sm.max_calls = self.settings.get("max_calls", 3)
    self.radio.tx_audio_level = (
        self.settings.get("tx_level", 100) / 100.0
    )
    if self.radio.ip:
        self.radio.set_power(self.settings.get("power_preset", 15))
    # Debug-Konsole Toggle aus Settings
    debug_vis = self.settings.get("debug_console_visible", False)
```

**NACHHER (alle 3 Live-Setter unter ein `if self.radio.ip:`):**
```python
if dialog.exec():
    self._update_statusbar()
    self.qso_sm.max_calls = self.settings.get("max_calls", 3)
    if self.radio.ip:
        self.radio.tx_audio_level = self.settings.get("tx_level", 100) / 100.0
        self.radio.set_power(self.settings.get("power_preset", 15))
        self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))
    # Debug-Konsole Toggle aus Settings
    debug_vis = self.settings.get("debug_console_visible", False)
```

**Anmerkung F1:** Bislang wurde `tx_audio_level` ohne `radio.ip`-Guard
gesetzt — das ist okay weil das Attribut auch in-memory funktioniert
bei nicht-verbundenem Radio. Aber zur Wartbarkeits-Konsistenz nach
V4-pro-F1 alle 3 Setter unter denselben Guard.

### C3 — `tests/test_p58_save_hook.py` NEU mit T1-T6

- T1: Dialog `_save_and_close` setzt nur settings, kein Radio-Call
- T2: `_on_settings_clicked` mit dialog.exec()=True + radio.ip="1.2.3.4" → set_swr_limit(2.5) gerufen
- T3: `radio.ip is None` → set_swr_limit NICHT gerufen
- T4: Cancel-Pfad (dialog.exec()=False) → kein Setter
- T5: Connect-Hook in mw_radio.py:179 Regression (Setter wird mit Settings-Wert gerufen)
- T6: Bestehende SWR-Watchdog-Tests grün (sanity)

### C4 — `main.py` APP_VERSION 0.97.30 → 0.97.31

### C5 — HISTORY.md + HANDOFF.md + CLAUDE.md + Memory + MEMORY.md Index

## Acceptance Criteria

- **AC1:** Settings öffnen, swr_limit ändern, Save → Terminal zeigt
  sofort `[FlexRadio] SWR-Limit auf X.X gesetzt`
- **AC2:** Beim nächsten TX greift der neue Limit-Wert (Watchdog
  triggert bei swr >= neuer_limit)
- **AC3:** Bei `radio.ip is None` → kein Crash, kein Setter-Call
  (Settings persistiert trotzdem, Connect-Hook setzt beim
  nächsten App-Start)
- **AC4:** Cancel/Esc im Dialog → KEIN Setter-Call (Settings-Werte
  nicht gespeichert dank `dialog.exec()=False`)
- **AC5:** Connect-Hook in `mw_radio.py:179` unverändert
- **AC6 (F1):** `tx_audio_level` + `set_power` + `set_swr_limit`
  unter einheitlichem `if self.radio.ip:` Guard

## Mike Field-Test (nach Code)

| F# | Was prüfen |
|---|---|
| F1 | App läuft + verbunden → Settings öffnen → swr_limit auf 2.0 → Save → Terminal `[FlexRadio] SWR-Limit auf 2.0 gesetzt` SOFORT sichtbar |
| F2 | Cancel/Esc im Dialog → keine Setter-Zeile (Settings unverändert) |
| F3 | Während TX swr_limit von 2.0 auf 1.5 ändern + Save → bei nächster SWR-Überschreitung greift neuer Wert |
| F4 | Regression Bundle J etc. — Dialog-Settings funktionieren normal |
