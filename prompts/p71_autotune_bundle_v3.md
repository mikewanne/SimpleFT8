# P71 Auto-Tune Bundle (V3 — Final-Spec nach R1-V4-pro) — 18.05.2026

## R1-Findings-Übernahme

| Finding | Klassif. | Status V3 | Begründung |
|---------|----------|-----------|------------|
| F1 Backup-Race | 🔴 | **ÜBERNOMMEN** | Fix wie V2-F1 (Grace=12s konstant) |
| F2 App-Start | 🟠 | **ÜBERNOMMEN** | Belt-and-suspenders Guard-Flag + RFPreset-Anker-Check |
| F3 Settings-Migration | 🟡 | **ÜBERNOMMEN** | findData(-1)-Fallback + Settings.load()-Pop |
| F4 FWDPWR tight coupling | 🟡 | **AKZEPTIERT (KISS)** | try/except mit Fallback 0.0 reicht |
| F5 Logging mode+ant | 🟡 | **ÜBERNOMMEN** | Kostet nichts, Diagnose-Win |
| F6 Backup-Grace konstant | ⚪ | Akademisch | Konstante mit Kommentar (V2-F1) |
| F7 ANT1-Hardware | ⚪ | Bestätigt sicher | FlexRadio behält Antennen-State |
| F8 Test-Coverage | ⚪ | **Tests erweitert** | T4 Migration + T11 Cancel-during-Phase-B |

## Acceptance-Criteria

**AC1 (F1):** AutoTuneDialog Backup-Timer = `(duration_s + 12) * 1000` ms.
Konstante `_BACKUP_GRACE_S = 12` mit Kommentar (Phase B max 6.5s + Post-Check
2s + Safety 3.5s).

**AC2 (F2-A):** `MainWindow.__init__` initialisiert `self._initial_band_set =
True` als erste Zeile nach `super().__init__()`. Setzt am Ende der __init__
(NACH `apply_visible_bands()`, vor `_init_psk_polling`) auf `False`.

**AC3 (F2-B):** `_on_band_changed` (mw_radio.py:498) prüft VOR Auto-Tune-
Trigger zwei zusätzliche Bedingungen:
- `not getattr(self, '_initial_band_set', False)` (Guard-Flag)
- `not self.rf_preset_store.has_anchor(self.radio.radio_type, band, watt=10)`
  (Belt-and-suspenders gegen Bandpilot-Re-Trigger)

**AC4 (F2-C):** `RFPresetStore.has_anchor(radio_type, band, watt)` neu — gibt
True zurück wenn ein Eintrag im Store für (radio_type, band, watt) existiert.
Fail-silent bei fehlendem Schlüssel.

**AC5 (F3-A):** ComboBox `tune_duration_combo` Items: `addItem("5 s", 5)`,
`addItem("10 s", 10)`, `addItem("15 s", 15)`. Default-Selection = Item für 15.

**AC6 (F3-B):** ComboBox-Load mit `findData(_dur)`-Fallback:
```python
_dur = self.settings.get("tune_duration_s", 15)
idx = self.tune_duration_combo.findData(_dur)
if idx < 0:
    idx = self.tune_duration_combo.findData(15)  # Fallback Default
self.tune_duration_combo.setCurrentIndex(idx)
```

**AC7 (F3-C):** Reset-Button setzt `setCurrentIndex(findData(15))`.

**AC8 (F3-D):** `Settings.load()` poppt alten `tune_duration_s`-Wert wenn er
nicht in (5, 10, 15) ist und ersetzt durch 15.

**AC9 (F3-E):** `mw_tx.py:473` Whitelist `duration_s in (5, 10, 15)` (statt
(15, 30)). Default-Fallback bleibt 15.

**AC10 (Bug 4-A):** `AutoTuneDialog.__init__` neue Signatur:
`(parent, band: str, duration_s: int = 15, mode: str = "FT8")`.
`_title_label` Format: `f"🔧 Auto-TUNE läuft — {band.lower()} {mode}"` → z.B.
"Auto-TUNE läuft — 17m FT8".

**AC11 (Bug 4-B + F5):** Status-Label Format mit Live-FWDPWR:
```python
try:
    fwdpwr = float(self._parent._fwdpwr_samples[-1])
except (AttributeError, IndexError, TypeError, ValueError):
    fwdpwr = 0.0
self._status_label.setText(
    f"ANT1, 10W → {self._mode} — {self._elapsed_s}/{self._duration_s} s "
    f"· SWR {swr:.1f} · FWDPWR {fwdpwr:.1f}W"
)
```

**AC12 (Bug 4-C):** `_start_auto_tune_for_band_change` ruft Dialog mit
`mode=self.settings.mode`.

**AC13 (Bug 5 + F5):** Logging-Erweiterung. Alle Zeilen 1-zeilig, key=value für
grep:
- `_tune_post_swr_check` SWR-OK + Auto:
  `[P54a] DONE OK band={band} mode={mode} ant=ANT1 swr={swr:.1f} fwdpwr={avg:.1f} rf={rf} duration={duration_s}s`
- `_tune_post_swr_check` SWR-bad + Auto:
  `[P54a] DONE FAIL reason=swr_bad band={band} mode={mode} swr={swr:.1f} limit={limit:.1f}`
- `_tune_post_swr_check` radio.ip=None + Auto:
  `[P54a] DONE FAIL reason=disconnect band={band}`
- `auto_tune_dialog._on_cancel_clicked`:
  `[P54a] DONE FAIL reason=cancelled band={band} mode={mode}`
- `auto_tune_dialog._on_backup_timeout`:
  `[P54a] DONE FAIL reason=timeout band={band} mode={mode} after={duration_s+12}s`

**AC14 (Tests):** `tests/test_p71_autotune_bundle.py` — 12 Tests:
- T1: Backup-Timer-Wert = `(duration_s + 12) * 1000` ms
- T2: Title-Label `"... — {band.lower()} {mode}"`
- T3: Status-Label-Format mit Mode + FWDPWR-Token
- T4: Settings-Migration `tune_duration_s=30` → 15 nach load
- T5: ComboBox findData-Fallback bei unbekanntem Wert (4 → 15)
- T6: ComboBox-Items sind {5, 10, 15} (currentData iterativ)
- T7: `_initial_band_set` True nach __init__, False nach Init-Fertig
- T8: App-Start triggert KEIN Auto-Tune (Flag True greift)
- T9: User-Bandwechsel triggert Auto-Tune (Flag False, alle Bedingungen wahr)
- T10: Auto-Tune skippt wenn `RFPresetStore.has_anchor()` True (Belt-and-suspenders)
- T11: Cancel während Phase B → `_tune_convergence_cancelled=True` + DONE FAIL cancelled-Log
- T12: Logging-Format `[P54a] DONE OK/FAIL ...` (capsys-Capture) für 4 Pfade

## Code-Plan V3 (8 atomare Commits)

**C1: `ui/auto_tune_dialog.py`** (AC1, AC10, AC11, AC13-cancel/timeout)
- `__init__` Signatur: `(parent, band, duration_s=15, mode="FT8")`
- `self._mode = mode`
- `_title_label`: `f"🔧 Auto-TUNE läuft — {band.lower()} {mode}"`
- `_status_label` initial: `f"ANT1, 10W → {mode} — 0 / {duration_s} s"`
- Konstante `_BACKUP_GRACE_S = 12`
- Backup-Timer: `(duration_s + _BACKUP_GRACE_S) * 1000`
- `_on_tick`: erweiterter Status mit FWDPWR
- `_on_cancel_clicked`: `print(f"[P54a] DONE FAIL reason=cancelled band={self._band} mode={self._mode}")`
- `_on_backup_timeout`: `print(f"[P54a] DONE FAIL reason=timeout band={self._band} mode={self._mode} after={self._duration_s + _BACKUP_GRACE_S}s")`

**C2: `ui/mw_tx.py`** (AC9, AC12, AC13-tune_post_swr_check)
- Dialog-Call: `AutoTuneDialog(self, band, duration_s, mode=self.settings.mode)`
- Whitelist `(15, 30)` → `(5, 10, 15)`
- `_tune_post_swr_check`:
  - radio.ip=None + Auto: DONE FAIL disconnect-Log VOR `dlg.auto_tune_done.emit`
  - SWR-OK + Auto: DONE OK-Log nach Save-Block, VOR `dlg.auto_tune_done.emit`
  - SWR-bad + Auto: DONE FAIL swr_bad-Log VOR `dlg.auto_tune_done.emit`

**C3: `ui/settings_dialog.py`** (AC5, AC6, AC7)
- ComboBox `addItem` 3× für 5/10/15
- `_load_settings` mit findData-Fallback
- `_reset_to_defaults` mit findData(15)
- Tooltip aktualisiert: "TUNE-Dauer in Sekunden (5/10/15)"

**C4: `ui/mw_radio.py`** (AC3)
- `_on_band_changed` Auto-Tune-Block (Z.498) erweitert um zwei Conditions

**C5: `ui/main_window.py`** (AC2)
- `__init__`: `self._initial_band_set = True` als erste Instance-Var nach `super().__init__()`
- Am Ende von `__init__` (nach `apply_visible_bands()`, vor `_init_psk_polling`):
  `self._initial_band_set = False`

**C6: `config/settings.py`** (AC8)
- `Settings.load()`: nach JSON-Read defensive Migration `tune_duration_s`
- `core/rf_preset_store.py`: neue Methode `has_anchor(radio_type, band, watt) -> bool` (AC4)

**C7: `tests/test_p71_autotune_bundle.py`** NEU (AC14, 12 Tests)

**C8: `main.py` APP_VERSION 0.97.46 → 0.97.47**
   + HISTORY.md + HANDOFF.md + CLAUDE.md + TODO.md + FIELDTESTS.md Update

## Field-Test-Punkte (V3 §5)

- **F1 (kein Radio):** App-Start ohne Settings → KEIN Auto-Tune-Dialog (AC2+AC3)
- **F2 (Radio):** Bandwechsel 20m → 17m → Auto-Tune läuft mit 15s, schließt VOR
  27s Backup auch bei langsamer Convergenz (AC1). Title "17m FT8". Status zeigt
  Mode/SWR/FWDPWR (AC10+AC11). DONE OK-Log (AC13).
- **F3 (kein Radio):** Settings → tune_duration_s ComboBox zeigt 5/10/15. Default
  15. Save + Reopen behält Wert (AC5+AC6).
- **F4 (kein Radio):** Settings-Migration: 30 manuell in JSON → App-Start → Settings
  zeigt 15 (AC8). Wert 4 → Settings zeigt 15 (AC6 Fallback).
- **F5 (Radio):** Console-Log zeigt klare DONE OK/FAIL-Zeilen für alle 4 Pfade
  (AC13).
- **F6 (Radio):** SWR-blockiertes Band → Marker greift, kein Auto-Tune (P63-
  Regression-Schutz unverändert).
- **F7 (Radio):** Cancel-Button während TUNE → `_tune_convergence_cancelled=True`,
  Phase B bricht ab, DONE FAIL cancelled-Log (AC13 + T11).

## Aus Scope (NICHT in P71)

- P72 Connect-Cancel-Fix („Ohne Radio weiter") → eigener Workflow.
- ALC-Pegel-Regelung → P70 (radio-pflichtig).
- Iter-Update-Pipeline mit Live-Convergenz-Anzeige → overkill.
- Property `radio.last_fwdpwr` → KISS-Akzeptanz F4, evtl. v0.98+.

## Push-Freigabe-Kriterien

- Alle 12 Tests grün
- 8 atomare Commits sauber
- Final-R1 V4-pro Round 2 ohne neue ROT/ORANGE
- HISTORY/HANDOFF/CLAUDE/TODO/FIELDTESTS dokumentiert

Field-Test pending bei Mike nach Rückkehr (F1+F3+F4 ohne Radio sofort,
F2+F5+F6+F7 mit Radio).
