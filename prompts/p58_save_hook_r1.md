# P58 R1-Review — SWR-Limit Save-Hook Live-Propagation

Du bist Senior-Reviewer für ein FT8-Funkprogramm-Projekt (Python +
PySide6 + FlexRadio TCP/VITA-49). Hardware-Safety ist höchste Priorität:
**ANT1 = TX immer, ANT2 = nur RX. NIEMALS TX auf ANT2.**

## Kontext

Mike-Field-Test 15.05.2026 morgens: SWR-Watchdog (P53, v0.97.29) hat
beim Live-Test NICHT funktioniert. Ursache: `set_swr_limit()` wurde
beim Settings-Save zur laufenden App **nicht propagiert**. Erst nach
App-Neustart (Connect-Hook in `mw_radio.py:179`) griff der Limit-Wert.

Settings-Persistenz funktioniert (JSON-Datei hatte 1.5). Bug ist
nur in der Live-Propagation während App lief.

## Wurzel-Erkenntnis aus V2-Self-Review

Die App hat **bereits eine etablierte Architektur** für Live-Settings:
sie werden **NACH `dialog.exec()` im MainWindow** propagiert (siehe
`tx_audio_level`, `set_power`). P53 hat das einzige Mal eine Inline-
Propagation IM DIALOG eingebaut (`ui/settings_dialog.py:680-683`) —
und genau die greift nicht.

## Geplanter Fix (V2-Option D)

**1 Zeile löschen + 1 Zeile hinzufügen:**

```python
# RAUS: ui/settings_dialog.py:680-683
# parent = self.parent()
# if parent is not None and hasattr(parent, "radio") and getattr(parent.radio, "ip", None):
#     parent.radio.set_swr_limit(self.swr_limit.value())

# REIN: ui/main_window.py:_on_settings_clicked nach Z.1067
if self.radio.ip:
    self.radio.set_power(self.settings.get("power_preset", 15))
    self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))  # NEU
```

## Aktueller Code (relevante Stellen)

### `ui/settings_dialog.py` Save-Methode (ab Z.~675)

```python
def _save_and_close(self):
    ...
    self.settings.set("swr_limit", self.swr_limit.value())
    # P53: Live an Radio propagieren wenn verbunden  ← DIESE LINE WEG
    parent = self.parent()
    if parent is not None and hasattr(parent, "radio") and getattr(parent.radio, "ip", None):
        parent.radio.set_swr_limit(self.swr_limit.value())
    self.settings.set("tune_power", self._current_tune_power)
    ...
    self.accept()
```

### `ui/main_window.py:_on_settings_clicked` (Z.~1056)

```python
@Slot()
def _on_settings_clicked(self):
    dialog = SettingsDialog(self.settings, self)
    if dialog.exec():
        self._update_statusbar()
        self.qso_sm.max_calls = self.settings.get("max_calls", 3)
        self.radio.tx_audio_level = (
            self.settings.get("tx_level", 100) / 100.0
        )
        if self.radio.ip:
            self.radio.set_power(self.settings.get("power_preset", 15))
        # NEU: + self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))
        ...
```

### `ui/mw_radio.py:177-179` (Connect-Hook, UNVERÄNDERT)

```python
self.radio.swr_alarm.connect(self._on_swr_alarm)
# P53: SWR-Limit aus Settings an Radio propagieren
self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))
```

## Hardware-Pflicht-Check

- **TX-Antennen-Wahl unverändert** — kein `set_tx_antenna()` im Fix-Pfad
- **Setter hat Clamp `[1.5, 10.0]`** in `radio/flexradio.py:947-951`
- **Connect-Hook bleibt bestehen** → App-Start setzt nach wie vor
  korrekt mit persistiertem Wert
- **Watchdog-Logik unverändert** — `_on_swr_alarm` in `ui/mw_tx.py`
  bleibt wie ist

## Acceptance Criteria

- **AC1:** Settings öffnen, swr_limit ändern, Save → Terminal zeigt
  sofort `[FlexRadio] SWR-Limit auf X.X gesetzt`
- **AC2:** Beim nächsten TX greift der neue Limit-Wert
- **AC3:** Bei `radio.ip is None` (Radio offline) → kein Crash, kein
  Setter-Call
- **AC4:** Cancel/Esc im Dialog → KEIN Setter-Call
- **AC5:** Connect-Hook in `mw_radio.py:179` unverändert

## Test-Plan

- **T1:** Dialog `_save_and_close` setzt nur `settings.set()` — kein
  Radio-Call (verifiziert mit MockRadio.set_swr_limit nicht aufgerufen)
- **T2:** `_on_settings_clicked` mit `dialog.exec()=True` + Mock-Radio
  `ip="1.2.3.4"` + swr_limit=2.5 → `mock.set_swr_limit.assert_called_once_with(2.5)`
- **T3:** `radio.ip is None` → `set_swr_limit` NICHT gerufen
- **T4:** Cancel-Pfad `dialog.exec()=False` → kein Setter
- **T5:** Connect-Hook in `mw_radio.py:_on_radio_connected` ruft
  Setter mit Settings-Wert (Regression)
- **T6:** Bestehende SWR-Watchdog-Tests (`test_p53_swr_watchdog.py`)
  bleiben grün

## Atomare Commits

- C1: `ui/settings_dialog.py` Inline-Propagation raus (Z.680-683)
- C2: `ui/main_window.py` Setter-Aufruf nach `set_power` einfügen
- C3: `tests/test_p58_save_hook.py` NEU mit T1-T6
- C4: APP_VERSION-Bump (0.97.30 → 0.97.31)
- C5: HISTORY.md + Doku-Update

## Frage an dich

1. **Architektur-Konsistenz:** Stimmst du zu dass Option D (Pattern
   wie `set_power`/`tx_audio_level`) sauberer ist als Signal-Pattern?
2. **Wurzel-Vermutung:** Glaubst du der Inline-Pfad in Dialog hat
   gar nie funktioniert (Bug seit P53-Code-Drop)? Oder gibt es einen
   Fall in dem `self.parent()` doch das MainWindow returnt?
3. **Hardware-Risiko:** Siehst du eine Gefahr im Plan? (Sollte nein
   weil nur Limit-Propagation, kein Antennen-Eingriff)
4. **Test-Coverage:** Reichen T1-T6 oder fehlt etwas?
5. **Sonstige Findings:** Race-Conditions? Lifecycle? Andere Bugs?

Bitte Reviewen wie üblich:
- Bug ROT, Risiko ORANGE, Verbesserung GELB, Hinweis GRAU
- Pro Finding: Nummerieren, Datei:Zeile, klare Aktion
- Am Ende: „PUSH FREIGEGEBEN" oder „KORREKTUR NÖTIG"
