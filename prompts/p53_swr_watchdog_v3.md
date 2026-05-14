# P53 — SWR-Live-Watchdog (Hardware-Sicherheit) — V3

Status: **freigegeben durch R1 (V4-pro)**, 4 Findings angenommen (2 Bug + 2 Risiko), 0 abgelehnt.
Vorgänger: V1 (Self-Review), V2, R1-Review, V3.

## 1. Ziel

Live-SWR-Schutz während TX. Wenn SWR ≥ `settings.swr_limit` für **2
aufeinanderfolgende** Messungen im VITA-49-Meter-Loop (innerhalb 500 ms)
**und `encoder.is_transmitting=True`** → TX sofort abbrechen (mid-slot),
Komplett-Stop aller Power-Modi, Modal-Warnung, QSO-Panel-Eintrag.
**Kein Auto-Resume** — User muss CQ/OMNI bewusst neu starten.

**Wurzel-Problem:** Mike-Field-Test 14.05.2026: nasse Antenne nach
Regen → SWR > 30 bei TX mit 70 W. `swr_limit` (3.0) aus Settings hat
NICHT gegriffen weil:

1. Existierender SWR-Check läuft nur **vor der Gain-Messung**
   (`ui/mw_radio.py:1336+1352`), nicht im normalen TX-Pfad.
2. `swr_alarm`-Signal feuert zwar aus VITA-Loop
   (`radio/flexradio.py:1388-1390`), aber Handler `ui/mw_tx.py:99-105`
   zeigt nur Statusbar-Message — **stoppt KEINEN TX**.
3. **Zweiter Bug:** `Settings.swr_limit` wird **NIRGENDS** an FlexRadio
   propagiert. `flexradio.py:68` hat `_swr_limit = 3.0` hardcoded.

FlexRadio-Hardware-Schutz + Tuner haben Mike's PA gerettet — Glück.

**Architektur-Korrektur zur TODO-V0-Spec:** Statt eigenem QTimer-200ms-
Polling reagieren wir auf das **bestehende `swr_alarm`-Signal**. VITA-
Meter-Loop liefert SWR alle ~50-100 ms, signal feuert wenn
`_is_transmitting and swr >= _swr_limit`. KISS.

## 2. Akzeptanzkriterien

| # | Kriterium | Verifikation |
|---|---|---|
| AC1 | Bei SWR ≥ Limit für 2 aufeinanderfolgende `swr_alarm`-Emits **innerhalb 500 ms** und `encoder.is_transmitting=True` → TX abgebrochen | Test mit 2 echten Signal-Emits |
| AC2 | 1 isolierter Alarm (kein 2. innerhalb 500 ms) → kein Stop | Spike-Schutz-Test |
| AC3 | Alarm aus `ptt_on()`-Pre-Check (`flexradio.py:957`, `is_transmitting=False`) → Handler returnt sofort, spike_count zurück auf 0, KEIN Stop-Block | Bug-Schutz-Test |
| AC4 | Stop-Block ruft in dieser Reihenfolge: (1) spike_count=0 reset, (2) `encoder.abort()`, (3) `radio.ptt_off()`, (4) `qso_sm.stop_cq()`+`cancel()`, (5) `control_panel.set_cq_active(False)`, (6) `_omni_cq.stop("swr_block")` falls aktiv, (7) `_auto_hunt.stop_auto_hunt("swr_block")` falls aktiv, (8) `qso_panel.add_info(...)`, (9) Modal | Spy/Order-Verify |
| AC5 | `radio.set_tx_antenna()` wird im Stop-Pfad **NIE** aufgerufen (ANT1 bleibt ANT1) | Spy negativ |
| AC6 | Modal `QMessageBox.warning` mit Titel „SWR-Schutz ausgelöst", Text enthält „SWR X.X (Limit Y.Y)" + Hinweis Antenne/Limit | UI-Test (Monkey-Patch) |
| AC7 | `qso_panel.add_info("⚠ TX abgebrochen — SWR X.X")` VOR Modal aufgerufen (Modal blockiert Panel-Update sonst) | Order-Verify |
| AC8 | **Kein Auto-Resume.** Nach Stop: `cq_mode=False`, spike_count=0, Watchdog passiv bis User neu klickt | Sequenz-Test |
| AC9 | `Settings.swr_limit` wird nach Radio-Connect (`mw_radio._start_radio` ~Z.177) an `flexradio.set_swr_limit(value)` propagiert | Init-Test |
| AC10 | Settings-Dialog-Save (`_save_and_close` ~Z.679) ruft `parent.radio.set_swr_limit(value)` wenn `parent.radio.ip` gesetzt | Save-Hook-Test |
| AC11 | `set_swr_limit(value)` clampt Eingabe auf `[1.5, 10.0]` (Schutz gegen manuell editierte settings.json) | Clamp-Test |
| AC12 | `RadioInterface` (`radio/base_radio.py`) hat `set_swr_limit(value)` als Default-Pass-Method definiert (Stil-Treue zur existierenden Property-Stub-Architektur — keine echte ABC) | grep + Test |
| AC13 | `MainWindow.__init__` initialisiert `_swr_spike_count = 0` und `_swr_first_alarm_t = 0.0` explizit (Bug-Schutz gegen AttributeError) | Init-Test |
| AC14 | Tests grün 1245 → ≥ 1257 (+12) | pytest |

## 3. Betroffene Module/Dateien

| Datei | Funktion | Änderung |
|---|---|---|
| `radio/base_radio.py` ~Z.222 | `RadioInterface` Klasse | NEU `def set_swr_limit(self, value: float) -> None: pass` (Default-Stub im Stil von `tx_audio_level.setter`) |
| `radio/flexradio.py:68` | `_swr_limit = 3.0` | unverändert (Default) |
| `radio/flexradio.py` ~Z.946 (nach `check_swr_safe`) | NEU `set_swr_limit(value)` | Setter mit Clamp auf [1.5, 10.0] + Debug-Print |
| `radio/flexradio.py:1388` | VITA-Meter Alarm-Emit | unverändert — Signal feuert schon korrekt |
| `ui/main_window.py` `__init__` | Instanz-Vars | NEU `self._swr_spike_count = 0`, `self._swr_first_alarm_t = 0.0` |
| `ui/mw_tx.py:99-105` | `_on_swr_alarm` | Komplett-Rewrite: Pre-Check + Spike-Counter + Stop-Block + Modal + Panel-Eintrag |
| `ui/mw_radio.py:177` (nach `swr_alarm.connect(...)`) | NEU 1 Zeile | `self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))` |
| `ui/settings_dialog.py` `_save_and_close` ~Z.679 | NEU Settings-Save-Hook | nach `settings.set("swr_limit", ...)` zusätzlich `parent.radio.set_swr_limit(...)` falls `parent.radio.ip` |
| `tests/test_p53_swr_watchdog.py` | NEU | T1-T13 (siehe §6) |

## 4. Randbedingungen

### Threading
- `swr_alarm.emit()` läuft im VITA-49-Decoder-Thread (`radio/flexradio.py`-
  Meter-Loop).
- `_on_swr_alarm` ist `@Slot(float)` — Qt verbindet aus Worker-Thread
  automatisch via `Qt.QueuedConnection` → läuft im GUI-Thread.
  → **Kein eigenes Lock nötig** für Spike-Counter.
- Spike-Counter und Zeitstempel sind Instanz-Variablen in `MainWindow`
  (Init in `__init__`, AC13).

### Spike-Schutz (Bug-Schutz gegen PTT-on-Glitch)
- Instanz-Vars: `_swr_spike_count: int = 0`, `_swr_first_alarm_t: float = 0.0`.
- 1. Alarm (oder Re-Start wenn altes Fenster > 500 ms):
  `_swr_spike_count=1`, `_swr_first_alarm_t = time.monotonic()`, return.
- 2. Alarm innerhalb 500 ms: Stop-Block läuft.
- **Keine untere Schranke** (R1-F3, V2-Korrektur): QueuedConnection
  serialisiert eh ≥ 1 Event-Loop-Tick zwischen Emits, also „≥ 100 ms" aus
  V2 war künstlich und widersprach der Code-Skizze. Streichen.
- **Reset-Reihenfolge im Stop-Block:** AC4(1) — SOFORT `_swr_spike_count
  = 0` setzen, **bevor** Stop-Calls laufen. Verhindert dass ein 3. Alarm
  der noch in der Qt-Queue steckt erneut den Stop-Block triggert.

### Pre-Check (AC3 — Bug-Schutz)
`_on_swr_alarm` MUSS als **erste Aktion** prüfen:
```python
if not self.encoder.is_transmitting:
    self._swr_spike_count = 0
    return
```
Begründung: `flexradio.ptt_on()` emittet `swr_alarm` auch bei Pre-TX-
Block (Z.957) wenn SWR > Limit und User PTT drückt. Dort ist
`_is_transmitting=False`. Ohne diesen Check würde unser Stop-Block
grundlos laufen — und zwar bei JEDEM PTT-Versuch mit hoher SWR. Bug.

### Hardware-Pflicht (CLAUDE.md)
- Stop-Block ruft **NIE** `radio.set_tx_antenna(...)`. ANT1 bleibt ANT1.
- `encoder.abort()` (setzt `_is_transmitting=False` + `_abort_event.set()`)
  und `radio.ptt_off()` (`xmit 0`) sind antennen-neutral.

### Pre-Init-Schutz für `_omni_cq` / `_auto_hunt`
Pattern wie `_on_rx_mode_changed:544-547`:
```python
if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
    self._omni_cq.stop("swr_block")
if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
    self._auto_hunt.stop_auto_hunt("swr_block")
```

### UI / UX
- **Reihenfolge:** Erst `qso_panel.add_info(...)` (sofort sichtbar,
  Panel-Update synchron), DANN `QMessageBox.warning(...)` (Modal
  blockiert Event-Loop).
- Modal: `QMessageBox.warning(self, "SWR-Schutz ausgelöst", text)` —
  User-Klick erforderlich.
- Kein Cooldown (Modal blockt eh; alter 10s-Cooldown entfällt).
- Alte Statusbar-Message aus `mw_tx.py:104` entfällt (Modal ersetzt).

### Settings-Propagation (AC9, AC10, AC11)
**Radio-Connect-Hook** (`mw_radio.py:_start_radio` ~Z.177):
```python
self.radio.meter_update.connect(self._on_meter_update)
self.radio.swr_alarm.connect(self._on_swr_alarm)
self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))  # NEU
```

**Settings-Save-Hook** (`settings_dialog.py:_save_and_close` ~Z.679):
```python
self.settings.set("swr_limit", self.swr_limit.value())
# NEU: Live an Radio propagieren wenn verbunden
parent = self.parent()
if parent is not None and hasattr(parent, "radio") and getattr(parent.radio, "ip", None):
    parent.radio.set_swr_limit(self.swr_limit.value())
```

**Clamp im Setter** (`flexradio.set_swr_limit`):
```python
def set_swr_limit(self, value: float) -> None:
    """SWR-Limit setzen — Clamp auf [1.5, 10.0] gegen kaputte Settings."""
    v = max(1.5, min(10.0, float(value)))
    self._swr_limit = v
    print(f"[FlexRadio] SWR-Limit auf {v:.1f} gesetzt")
```

**Base (`base_radio.py` ~Z.222):**
```python
def set_swr_limit(self, value: float) -> None:
    """SWR-Limit setzen — Default-Pass für Radios ohne SWR-Schutz."""
    pass
```

### Reaktivierung
**Kein Auto-Resume.** Watchdog ist immer aktiv solange Signal verdrahtet
ist. Nach Stop muss User CQ/OMNI bewusst neu klicken. Mike-Spec explizit.

## 5. Nicht im Scope

- **TUNE-Pfad:** `radio.tune_on()` setzt `_is_transmitting` nicht auf
  True → VITA-Meter-Alarm `self._is_transmitting and swr >= limit`
  greift dort nicht. P54 (Auto-Tune-Modal bei Bandwechsel) übernimmt
  diesen Bereich.
- **Eigener QTimer-200ms-Polling** (TODO-V0) — verworfen, KISS.
- **Cooldown-Logik** — durch Modal ersetzt.
- **Antennen-Diagnose / Frequenz-Tracking / Tuner-Auto-Start** — separat.
- **Settings-UI-Änderungen** — Setting existiert schon, Wert wird nur
  jetzt korrekt durchgereicht.

## 6. Testbarkeit

`tests/test_p53_swr_watchdog.py` NEU, +12 Tests:

| Test | AC | Pattern |
|---|---|---|
| T1 `test_alarm_2_in_a_row_triggers_stop` | AC1, AC4 | Echtes `Signal(float)` + Spy auf alle Stop-Calls; 2 emits, `time.monotonic` gestubbt (50 ms Abstand) |
| T2 `test_isolated_alarm_no_stop` | AC2 | 1 emit, `time.monotonic+0.6` simuliert, kein 2. Emit → keine Stop-Spies treffen |
| T3 `test_alarm_when_not_transmitting_returns` | AC3 | `encoder.is_transmitting=False`, 2 emits → spike_count=0, KEIN Stop |
| T4 `test_stop_block_order` | AC4 | Order-Verify via `mock_calls`-Liste, Reihenfolge (1)-(9) |
| T5 `test_no_set_tx_antenna_in_stop` | AC5 | `radio.set_tx_antenna`-Spy nie aufgerufen |
| T6 `test_modal_dialog_text` | AC6 | `QMessageBox.warning` Monkey-Patch, prüft Titel + Text-Substrings „SWR X.X" und „Limit Y.Y" |
| T7 `test_panel_info_before_modal` | AC7 | Reihenfolge add_info vor modal via combined mock_calls |
| T8 `test_no_auto_resume_after_stop` | AC8 | Nach Stop: `cq_mode=False`, spike_count=0 |
| T9 `test_swr_limit_set_at_connect` | AC9 | Mock-Radio mit `set_swr_limit`-Spy, `_start_radio` ruft mit Settings-Wert |
| T10 `test_swr_limit_set_on_settings_save` | AC10 | Settings-Dialog `_save_and_close` ruft `parent.radio.set_swr_limit(2.5)` |
| T11 `test_set_swr_limit_clamps` | AC11 | `set_swr_limit(0.5) → 1.5`, `set_swr_limit(99.0) → 10.0`, `set_swr_limit(2.5) → 2.5` |
| T12 `test_base_radio_has_set_swr_limit` | AC12 | `hasattr(RadioInterface, "set_swr_limit")` + Aufruf wirft kein Exception (Default-Pass) |
| T13 `test_main_window_inits_spike_state` | AC13 | Nach `MainWindow()`-Construction: `_swr_spike_count == 0`, `_swr_first_alarm_t == 0.0` |

### Anti-Mock-Pflicht (Memory `feedback_test_critical_path_not_mock.md`)
- T1-T3, T13 nutzen **echte `Signal(float)`-Verbindung** zwischen Fake-
  Radio (mit `Signal`-Attribut) und `_on_swr_alarm`-Handler. Keine
  Direkt-Aufrufe des Handlers — die VITA-Loop-Realität muss durch das
  Signal.
- Stop-Block-Spies sind auf den `encoder`/`radio`/`qso_sm`/`qso_panel`-
  Mocks — der Spike-Counter-Code im Handler bleibt echt.
- `QMessageBox.warning` ist Klassen-Methode → Monkey-Patch via
  `monkeypatch.setattr(QMessageBox, "warning", spy)`.
- `time.monotonic` als Test-Stub für deterministische Zeit-Sprünge —
  kein `time.sleep()` im Test (langsam + flaky).

---

## Field-Test-Punkte (Mike, nach Push-Freigabe)

| F# | Was prüfen |
|---|---|
| F1 | Settings-Dialog öffnen, SWR-Limit auf 2.5 setzen, Save → Konsole zeigt `[FlexRadio] SWR-Limit auf 2.5 gesetzt` |
| F2 | App neu starten mit verbundenem Radio → Konsole zeigt direkt nach Connect `[FlexRadio] SWR-Limit auf 2.5 gesetzt` |
| F3 | Normale TX mit guter Antenne (SWR < 2) → Watchdog feuert nicht |
| F4 | Pre-TX-Block-Test: Antenne abziehen (SWR > 10), CQ-Klick → FlexRadio blockt PTT (existierender Pre-Check), Watchdog macht KEIN Modal (`is_transmitting=False`) |
| F5 | Während TX Tuner manuell auf hohe SWR ziehen → nach ~500 ms (2 Alarms) Modal „SWR-Schutz ausgelöst" + QSO-Panel-Zeile |
| F6 | Bei OMNI-CQ + SWR-Block: OMNI stoppt sauber, keine weiteren TX-Slots |
| F7 | Nach Modal-Wegklicken: kein Auto-Resume, User muss CQ/OMNI manuell starten |

## Code-Skizze (vollständig — für Implementierungs-Referenz)

### `radio/flexradio.py` (neue Methode nach `check_swr_safe` ~Z.946)
```python
def set_swr_limit(self, value: float) -> None:
    """SWR-Limit setzen — Clamp auf [1.5, 10.0] gegen kaputte Settings."""
    v = max(1.5, min(10.0, float(value)))
    self._swr_limit = v
    print(f"[FlexRadio] SWR-Limit auf {v:.1f} gesetzt")
```

### `radio/base_radio.py` (~Z.222)
```python
def set_swr_limit(self, value: float) -> None:
    """SWR-Limit setzen — Default-Pass für Radios ohne SWR-Schutz."""
    pass
```

### `ui/main_window.py` __init__ (irgendwo bei den anderen Instanz-Vars)
```python
# P53 Spike-Schutz für SWR-Live-Watchdog
self._swr_spike_count = 0
self._swr_first_alarm_t = 0.0
```

### `ui/mw_tx.py` Komplett-Rewrite von `_on_swr_alarm`
```python
@Slot(float)
def _on_swr_alarm(self, swr: float) -> None:
    """P53: Live-SWR-Watchdog während TX.

    Feuert bei jedem VITA-49-Meter-Update wenn SWR ≥ Limit und
    `_is_transmitting=True`. Auch von `ptt_on()` Pre-Check (vor TX-Start).
    Stop-Block läuft nur bei 2 aufeinanderfolgenden Alarms (Spike-Schutz)
    UND laufendem TX.
    """
    import time as _time
    from PySide6.QtWidgets import QMessageBox

    # AC3: Pre-TX-Alarm aus ptt_on() ignorieren — kein laufender TX
    if not self.encoder.is_transmitting:
        self._swr_spike_count = 0
        return

    now = _time.monotonic()

    # 1. Alarm ODER alter Counter abgelaufen (> 500 ms) → neu starten
    if self._swr_spike_count == 0 or (now - self._swr_first_alarm_t) > 0.5:
        self._swr_spike_count = 1
        self._swr_first_alarm_t = now
        return

    # 2. Alarm innerhalb 500 ms — Stop auslösen
    # AC4(1): Reset SOFORT, gegen 3. Alarm in der Qt-Queue
    self._swr_spike_count = 0
    limit = self.settings.get("swr_limit", 3.0)

    # AC4(2)-(7): Stop-Block antennen-neutral
    self.encoder.abort()
    if self.radio.ip:
        self.radio.ptt_off()
    if self.qso_sm.cq_mode or self.qso_sm.state != QSOState.IDLE:
        self.qso_sm.stop_cq()
        self.qso_sm.cancel()
        self.control_panel.set_cq_active(False)
    if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
        self._omni_cq.stop("swr_block")
    if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
        self._auto_hunt.stop_auto_hunt("swr_block")

    # AC7: Panel-Eintrag VOR Modal (Modal blockiert Event-Loop)
    self.qso_panel.add_info(f"⚠ TX abgebrochen — SWR {swr:.1f}")

    # AC6: Modal
    QMessageBox.warning(
        self,
        "SWR-Schutz ausgelöst",
        f"TX abgebrochen — SWR {swr:.1f} (Limit {limit:.1f}).\n"
        "Antenne tunen oder SWR-Limit in Einstellungen prüfen."
    )

    print(f"[P53] SWR-Watchdog: TX gestoppt — SWR {swr:.1f} >= Limit {limit:.1f}")
```

### `ui/mw_radio.py` Z.177 (nach `swr_alarm.connect`)
```python
self.radio.swr_alarm.connect(self._on_swr_alarm)
self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))  # P53
```

### `ui/settings_dialog.py` `_save_and_close` ~Z.679
```python
self.settings.set("swr_limit", self.swr_limit.value())
# P53: Live an Radio propagieren wenn verbunden
parent = self.parent()
if parent is not None and hasattr(parent, "radio") and getattr(parent.radio, "ip", None):
    parent.radio.set_swr_limit(self.swr_limit.value())
```

## R1-Findings — Aufnahme

| # | Schwere | Finding | Status | Begründung |
|---|---|---|---|---|
| 1 | 🔴 Bug | `RadioInterface`-ABC braucht `set_swr_limit` | **Angenommen** | AC12 + Test T12 — als Default-Pass (Stil-Treue zur existierenden Stub-Architektur, keine echte ABC) |
| 2 | 🔴 Bug | `_swr_spike_count` nirgendwo initialisiert | **Angenommen** | AC13 + Test T13 — explizite Init in `MainWindow.__init__` |
| 3 | 🟠 Risiko | AC1 „≥ 100 ms" widerspricht Code-Skizze | **Angenommen** | Untere Schranke gestrichen — QueuedConnection-Serialisierung garantiert eh ≥ 1 Event-Tick. AC1 in V3 auf nur „≤ 500 ms" reduziert |
| 4 | 🟠 Risiko | AC10 fehlt in Code-Skizze | **Angenommen** | Anhang-Skizze um Settings-Save-Snippet erweitert |

Halluzinations-Rate V4-pro: **0/4** (alle 4 verifizierbar im Code).
