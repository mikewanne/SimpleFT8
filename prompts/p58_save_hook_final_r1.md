# P58 Final-R1 — Push-Freigabe-Check

Du bist Senior-Reviewer. P58 (SWR-Limit Live-Propagation Bug-Fix) ist
implementiert. Code-Diff angehängt. Frage: PUSH FREIGEGEBEN oder
KORREKTUR NÖTIG?

## Was geändert wurde

### `ui/settings_dialog.py` (vorher 4 Zeilen, jetzt 3 Kommentar-Zeilen)

**RAUS:**
```python
# P53: Live an Radio propagieren wenn verbunden
parent = self.parent()
if parent is not None and hasattr(parent, "radio") and getattr(parent.radio, "ip", None):
    parent.radio.set_swr_limit(self.swr_limit.value())
```

**REIN (Kommentar):**
```python
# P58 (v0.97.31): Live-Propagation an Radio NICHT mehr hier — wird
# in main_window._on_settings_clicked nach dialog.exec() gemacht
# (Architektur-Konsistenz mit set_power/tx_audio_level).
```

### `ui/main_window.py:_on_settings_clicked`

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
```

**NACHHER (R1-V4-pro-F1 Setter-Block gruppiert):**
```python
if dialog.exec():
    self._update_statusbar()
    self.qso_sm.max_calls = self.settings.get("max_calls", 3)
    # P58 (v0.97.31): Alle 3 Live-Setter unter gemeinsamem radio.ip-Guard
    # (Architektur-Konsistenz, R1-V4-pro-F1)
    if self.radio.ip:
        self.radio.tx_audio_level = self.settings.get("tx_level", 100) / 100.0
        self.radio.set_power(self.settings.get("power_preset", 15))
        self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))
```

### `tests/test_p58_save_hook.py` NEU (6 Tests T1-T6)

- T1: settings_dialog `_save_and_close` ruft NICHT mehr `set_swr_limit`
- T2: main_window `_on_settings_clicked` ruft `set_swr_limit`
- T3: Setter unter `if self.radio.ip:` Guard
- T4: Setter innerhalb `if dialog.exec():` Block (Cancel-Schutz)
- T5: Connect-Hook in `mw_radio.py:179` Regression-Schutz
- T6: Alte Inline-Propagation NICHT mehr in settings_dialog Source

### `tests/test_p53_swr_watchdog.py` T10 angepasst

T10 testete vorher `parent.radio.set_swr_limit` in settings_dialog —
jetzt testet er `self.radio.set_swr_limit` in main_window
(neuer Pfad).

### `main.py` APP_VERSION 0.97.30 → 0.97.31

### `HISTORY.md`, `HANDOFF.md`, `CLAUDE.md` Header, Memory, TODO

Wird im letzten Commit gemacht.

## Test-Status

```
1268 passed, 35 warnings in 16.48s
```

vorher 1262, jetzt 1268 (+6 netto: +6 P58, +0 P53 T10 angepasst).

## AC-Check

- **AC1:** ✓ Settings → Save → Setter ruft sofort (Mike-Field-Test
  später bestätigen)
- **AC2:** ✓ Logisch — Setter setzt `_swr_limit` neu, Watchdog-Bedingung
  Z.1394 in flexradio.py nutzt den neuen Wert
- **AC3:** ✓ Guard `if self.radio.ip:` schützt vor None-Crash
- **AC4:** ✓ Setter innerhalb `if dialog.exec():` Block
- **AC5:** ✓ Connect-Hook in `mw_radio.py:179` unverändert
- **AC6:** ✓ Alle 3 Setter unter gemeinsamem Guard

## Hardware-Check

- Kein `set_tx_antenna` im Pfad → ANT1-Pflicht nicht verletzt
- Setter hat Clamp `[1.5, 10.0]` → Hardware-Schutz aktiv
- Watchdog-Logik unverändert (`_on_swr_alarm` in mw_tx.py)

## Frage an dich

1. Push-Freigabe oder Bug entdeckt?
2. Test-Coverage ausreichend?
3. Race-Conditions zwischen Dialog-Save und Connect-Hook möglich?
4. Sonstige Findings?
