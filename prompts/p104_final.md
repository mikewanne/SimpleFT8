# P104 — Final-R1 Push-Check

Bundle nach Mike-Diskussion 21.05.2026.

**Bug-Fix-Loop für Bug 1+2 abgeschlossen:**

## Implementierungs-Zusammenfassung

### Settings-Vereinfachung
- `config/settings.py`: `power_watts` aus DEFAULTS + Property raus.
  `load()` pop't `power_watts` + `tx_level` (Migration idempotent).
- `ui/settings_dialog.py`: „Sendeleistung"-Spinbox + „TX Audio-Pegel"-
  Spinbox + zugehörige Load/Save/Reset-Stellen entfernt. HINTS-Dict
  bereinigt.
- `ui/mw_qso.py`: ADIF-Log nutzt `control_panel._current_power_watts`
  (Default 10).
- `ui/mw_radio.py`: tx_level fest auf 75 (war Cap, Setting weg).
- `ui/main_window.py`: tx_audio_level-Setter aus _on_settings_clicked raus.

### RF-Band-Buttons (Tabelle ersetzt)
- `ui/settings_dialog.py`: alte rf_table + rf_band_combo + Band-löschen-
  Button raus. Neu: `_rf_band_buttons`-Dict mit Buttons für alle 9 Bänder
  aus `BAND_FREQUENCIES`.
- `_refresh_rf_status` (alias `_refresh_rf_table` für Rückwärts-
  Kompatibilität): grüner Hintergrund wenn Presets vorhanden, rot wenn
  leer, grau wenn kein Radio.
- `_on_rf_band_clicked(band)`: bei grünen Buttons → Confirm-Dialog →
  `store.clear_band(...)`. Bei roten Buttons → silent no-op.
- `_update_rf_buttons_tx_state`: alle Band-Buttons + „Alle löschen"
  disabled während TX.
- Legende-Label „Grün = RF-Werte vorhanden …" unter den Buttons.

Tests 1700 → 1709 (+9 P104).

## Bitte prüfen

1. **Edge-Case Power-Preset == None**: `getattr(self.control_panel,
   '_current_power_watts', 10) or 10` — Default 10 W wenn None oder
   Attribut fehlt. Korrekt für ADIF?

2. **tx_level Closed-Loop-Verhalten**: war vorher `min(75,
   settings.get("tx_level", 75))`. Jetzt fest 75. Closed-Loop justiert
   dynamisch. Risiko dass User der das tatsächlich auf 50% gestellt
   hatte plötzlich 75% bekommt? Mike's Beobachtung: niemand stellt das
   um, war eh immer auf Cap.

3. **RF-Band-Buttons Click-Hit-Area** bei roten Buttons: no-op statt
   Tooltip. Sollte ein dezenter Hover-Hinweis kommen?

4. **Backwards-Compat-Alias** `_refresh_rf_table = _refresh_rf_status`:
   nötig falls externer Code die alte Methode aufruft. Verbleibender
   Tech-Debt oder OK?

5. **Was übersehen wir?** — Push-Freigabe.

## Code-Files
- `config/settings.py`
- `ui/settings_dialog.py`
- `ui/main_window.py`
- `ui/mw_qso.py`
- `ui/mw_radio.py`
- `tests/test_p104_settings_cleanup.py` (neu)
- `tests/test_p103_statusbar_div_subtype.py` (T3 angepasst)
- `tests/test_settings_dialog_smoke.py` (Refs angepasst)
