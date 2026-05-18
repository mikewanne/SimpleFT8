# P71 Auto-Tune Bundle — Final-R1 Push-Freigabe-Check

Du bist DeepSeek-V4-pro. Code-Phase ist fertig. R1-Findings F1-F3 (ROT/
ORANGE/GELB) und F5 (GELB Logging) wurden umgesetzt. 17 neue P71-Tests
grün, Komplette Suite **1452 Tests grün** (vorher 1435).

## Aufgabe

Push-Freigabe? Suche nach:

1. **Korrektheits-Bugs:** Logik, Cancel-Pfade, Race-Conditions, Off-by-One.
2. **Hardware-Pflicht:** ANT1-Pflicht für alle TX-Pfade gewahrt? `set_tx_antenna`
   nirgends auf ANT2 geändert?
3. **F1 Backup-Race-Fix:** `_BACKUP_GRACE_S = 12` korrekt verwendet?
4. **F2 App-Start-Guard:** `_initial_band_set` + `has_anchor`-Check Belt-and-
   suspenders sauber? Reihenfolge Init→Clear in `main_window.__init__`?
5. **F3 Settings-Migration:** `findData()`-Fallback in beiden Load+Reset?
   Settings.load()-Pop für unbekannte Werte? Auch für alte 30 → 15?
6. **F5 Logging:** alle 5 DONE-Log-Stellen vorhanden (OK + 4× FAIL: swr_bad,
   disconnect, cancelled, timeout)?
7. **Test-Coverage:** 17 P71-Tests reichen? Edge-Cases gut?
8. **Reverse-Kompatibilität:** alte Settings-Configs werden korrekt migriert,
   keine Crashes?

## Klassifikation

🔴 ROT / 🟠 ORANGE / 🟡 GELB / ⚪ HINWEIS.

Halte dich kurz. Wenn alles OK: **„PUSH FREIGEGEBEN"** sagen.
Wenn kritische Punkte: blockiere, Empfehlung nach Findings.

## Code-Stand

- `ui/auto_tune_dialog.py` — Modal-Dialog, `_BACKUP_GRACE_S=12`, mode-Param,
  band.lower() + mode im Title, FWDPWR im Status, DONE FAIL cancelled +
  timeout-Logs.
- `ui/mw_tx.py` — `_start_auto_tune_for_band_change` mit Whitelist 5/10/15
  + mode-Übergabe an Dialog. `_tune_post_swr_check` mit 3 DONE-Logs
  (OK, swr_bad, disconnect).
- `ui/mw_radio.py` — `_on_band_changed` Auto-Tune-Block erweitert um
  `_initial_band_set` + `has_anchor`-Check, plus Debug-Log für Skip-Grund.
- `ui/settings_dialog.py` — ComboBox 5/10/15 mit findData-Fallback bei
  Load + Reset.
- `ui/main_window.py` — Guard-Flag `_initial_band_set` Lifecycle.
- `config/settings.py` — Load-Migration `tune_duration_s ∉ (5,10,15) → 15`.
- `core/rf_preset_store.py` — neue Methode `has_anchor(radio, band, watt)`.
- `tests/test_p71_autotune_bundle.py` — 17 Tests.
- `main.py` APP_VERSION 0.97.47.

## V3-Spec im Anhang

`prompts/p71_autotune_bundle_v3.md`.
