Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software
und PySide6 (Signal statt pyqtSignal, Slot statt pyqtSlot). Das Projekt
ist ein Hobby-Funker-Tool für einen einzelnen Operator — NICHT Multi-Tenant.

Deine einzige Aufgabe: diesen Prompt kritisieren — NICHT das Problem lösen.
Strukturierte Liste: Lücken, Unklarheiten, Widersprüche, Verbesserungen.

KRITISCHE REGELN:
1. SCOPE-RESPEKT: Explizit als out-of-scope markiertes NICHT als Finding melden.
2. KISS VOR DEFENSIV: Komplexität nur wenn Wahrscheinlichkeit > 50%.
3. PROJEKT-BEZUG: Jedes Finding am konkreten Use-Case messen.
4. FORMAT: Tabelle Schwere | Finding | Datei:Zeile | Empfehlung.
   Severity: Bug (rot) / Risiko (orange) / Verbesserung (gelb) / Hinweis (grau).

Overengineering ist selbst ein Fehler den du benennen sollst.

---

# P53 — SWR-Live-Watchdog (Hardware-Sicherheit) — V2

## 1. Ziel

Live-SWR-Schutz während TX. Wenn SWR ≥ `settings.swr_limit` für **2
aufeinanderfolgende** Messungen im VITA-49-Meter-Loop (Abstand ≥ 100 ms,
≤ 500 ms) → TX sofort abbrechen (mid-slot), Komplett-Stop aller Power-
Modi, Modal-Warnung, QSO-Panel-Eintrag. **Kein Auto-Resume** — User muss
CQ/OMNI bewusst neu starten.

**Wurzel-Problem:** Mike-Field-Test 14.05.2026: nasse Antenne nach
Regen → SWR > 30 bei TX mit 70 W. `swr_limit` (3.0) aus Settings hat
NICHT gegriffen weil:

1. Der existierende SWR-Check läuft nur **vor der Gain-Messung**
   (`ui/mw_radio.py:1336+1352`), nicht im normalen TX-Pfad.
2. `swr_alarm`-Signal feuert zwar aus VITA-Loop
   (`radio/flexradio.py:1388-1390`), aber der Handler
   `ui/mw_tx.py:99-105` zeigt nur Statusbar-Message — **stoppt KEINEN TX**.
3. **Zweiter Bug:** `Settings.swr_limit` wird **NIRGENDS** an FlexRadio
   propagiert. `flexradio.py:68` hat `_swr_limit = 3.0` hardcoded. Wenn
   Mike Settings auf 2.0 stellt, sieht FlexRadio das nie.

FlexRadio-Hardware-Schutz + Tuner haben Mike's PA gerettet — Glück
gehabt.

**Architektur-Korrektur zur ursprünglichen TODO-Spec:** Statt eigenem
QTimer-200ms-Watchdog (Duplikat) reagieren wir auf das **bereits
existierende `swr_alarm`-Signal**. VITA-Meter-Loop liefert SWR
typisch alle ~50-100 ms, signal feuert wenn `_is_transmitting and
swr >= _swr_limit`. KISS.

## 2. Akzeptanzkriterien

| # | Kriterium | Verifikation |
|---|---|---|
| AC1 | Bei SWR ≥ Limit für 2 aufeinanderfolgende `swr_alarm`-Emits (Abstand ≥ 100 ms, ≤ 500 ms) **und `encoder.is_transmitting=True`** → TX abgebrochen | Test mit 2 echten Signal-Emits |
| AC2 | 1 isolierter Alarm (kein 2. innerhalb 500 ms) → kein Stop | Spike-Schutz-Test |
| AC3 | Alarm aus `ptt_on()`-Pre-Check (Z.957, `is_transmitting=False`) → Handler returnt sofort, KEIN Stop-Block | Bug-Schutz-Test |
| AC4 | Stop-Block ruft in dieser Reihenfolge: (1) Spike-Counter-Reset, (2) `encoder.abort()`, (3) `radio.ptt_off()`, (4) `qso_sm.stop_cq()` + `cancel()`, (5) `control_panel.set_cq_active(False)`, (6) `_omni_cq.stop("swr_block")` falls aktiv, (7) `_auto_hunt.stop_auto_hunt("swr_block")` falls aktiv, (8) `qso_panel.add_info(...)`, (9) Modal | Spy/Order-Verify |
| AC5 | `radio.set_tx_antenna()` wird im Stop-Pfad **NIE** aufgerufen (ANT1 bleibt ANT1) | Spy negativ |
| AC6 | Modal `QMessageBox.warning` mit Titel „SWR-Schutz ausgelöst", Text `"TX abgebrochen — SWR X.X (Limit Y.Y).\nAntenne tunen oder SWR-Limit in Einstellungen prüfen."` | UI-Test (Monkey-Patch) |
| AC7 | `qso_panel.add_info("⚠ TX abgebrochen — SWR X.X")` als Historie-Eintrag (vor Modal, sonst blockiert Modal Panel-Update) | Spy |
| AC8 | **Kein Auto-Resume.** Nach Stop ist Watchdog passiv bis User manuell CQ/OMNI startet. Spike-Counter ist 0. | Sequenz-Test |
| AC9 | `Settings.swr_limit` wird nach Radio-Connect (`_start_radio`) an `flexradio.set_swr_limit(value)` propagiert | Init-Test |
| AC10 | Settings-Dialog-Save (`_save_and_close`) ruft `parent.radio.set_swr_limit(value)` wenn `parent.radio.ip` gesetzt | Save-Hook-Test |
| AC11 | `set_swr_limit(value)` clampt Eingabe auf `[1.5, 10.0]` (Schutz gegen manuell editierte settings.json) | Clamp-Test |
| AC12 | `RadioInterface` ABC (`radio/base_radio.py`) hat `set_swr_limit(value)` als abstract definiert (IC-7300-Fork-fest) | grep + ABC-Test |
| AC13 | Tests grün 1245 → ≥ 1255 (+10) | pytest |

## 3. Betroffene Module/Dateien

| Datei | Funktion | Änderung |
|---|---|---|
| `radio/base_radio.py` | `RadioInterface` ABC | NEU abstract `set_swr_limit(value: float)` |
| `radio/flexradio.py:68` | `_swr_limit = 3.0` | unverändert (Default) |
| `radio/flexradio.py:~920` | NEU `set_swr_limit(value)` | Setter mit Clamp auf [1.5, 10.0] |
| `radio/flexradio.py:1388` | VITA-Meter Alarm-Emit | unverändert — Signal feuert schon korrekt |
| `ui/mw_tx.py:99-105` | `_on_swr_alarm` | Komplett-Rewrite: Pre-Check (is_transmitting) + Spike-Counter + Stop-Block + Modal + Panel-Eintrag |
| `ui/mw_radio.py:177` | Nach `swr_alarm.connect(...)` | NEU `self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))` |
| `ui/settings_dialog.py:679` | `_save_and_close` | Nach `settings.set("swr_limit", ...)` zusätzlich `parent.radio.set_swr_limit(...)` falls `parent.radio.ip` |
| `tests/test_p53_swr_watchdog.py` | NEU | T1-T13 |

## 4. Randbedingungen

### Threading
- `swr_alarm.emit()` läuft im VITA-49-Decoder-Thread (`radio/flexradio.py`-
  Meter-Loop).
- `_on_swr_alarm` ist `@Slot(float)` — Qt verbindet aus Worker-Thread
  automatisch via `Qt.QueuedConnection` → läuft im GUI-Thread.
  → **Kein eigenes Lock nötig** für Spike-Counter.
- Spike-Counter und Zeitstempel sind Instanz-Variablen in `MainWindow`/
  `mw_tx.py` (Mixin).

### Spike-Schutz (Bug-Schutz gegen PTT-on-Glitch)
- Instanz-Vars: `_swr_spike_count: int` (init 0), `_swr_first_alarm_t:
  float` (monotonic).
- 1. Alarm: `_swr_spike_count=1`, `_swr_first_alarm_t = time.monotonic()`,
  return.
- 2. Alarm:
  - Wenn `(now - _swr_first_alarm_t) <= 0.5` und `>= 0.1` (oder
    pragmatischer: `<= 0.5` reicht, untere Schranke kann entfallen weil
    QueuedConnection-Serialisierung schon ≥ 1 Event-Loop-Tick einschiebt)
    → Stop-Block läuft.
  - Wenn `> 0.5`: als neuer 1. Alarm werten (Counter=1, Zeitstempel
    aktualisieren).
- **Reset-Reihenfolge im Stop-Block:** SOFORT als 1. Aktion
  `_swr_spike_count = 0` setzen — damit ein 3. Alarm der noch in der
  Queue steckt nicht den Stop-Block ein 2. Mal triggert.

### Pre-Check (Bug-Schutz)
- **AC3:** `_on_swr_alarm` MUSS als **erste Aktion** prüfen:
  ```python
  if not self.encoder.is_transmitting:
      self._swr_spike_count = 0  # Reset für nächsten TX
      return
  ```
  Begründung: `flexradio.ptt_on()` emittet `swr_alarm` auch bei Pre-TX-
  Block (Z.957), wenn SWR > Limit und User PTT drückt. Dort ist
  `_is_transmitting=False`. Ohne diesen Check würde unser Stop-Block
  grundlos laufen — und zwar bei JEDEM PTT-Versuch mit hoher SWR. Bug.

### Hardware-Pflicht (CLAUDE.md)
- Stop-Block ruft **NIE** `radio.set_tx_antenna(...)`. ANT1 bleibt ANT1.
- `encoder.abort()` (setzt `_is_transmitting=False` + `_abort_event.set()`)
  und `radio.ptt_off()` (`xmit 0`) sind antennen-neutral.

### Pre-Init-Schutz für `_omni_cq` / `_auto_hunt`
- Beide werden in `_start_radio` initialisiert. Falls Alarm vor Radio-
  Connect feuert (theoretisch unmöglich, aber defensiv): Pattern wie
  `_on_rx_mode_changed:544-547`:
  ```python
  if hasattr(self, "_omni_cq") and self._omni_cq.is_active():
      self._omni_cq.stop("swr_block")
  if hasattr(self, "_auto_hunt") and self._auto_hunt.active:
      self._auto_hunt.stop_auto_hunt("swr_block")
  ```

### UI / UX
- **Reihenfolge:** Erst `qso_panel.add_info(...)` (sofort sichtbar,
  Panel-Update läuft synchron), DANN `QMessageBox.warning(...)` (Modal
  blockiert Event-Loop).
- Modal: `QMessageBox.warning(self, "SWR-Schutz ausgelöst", text)` —
  User-Klick erforderlich.
- Kein Cooldown (Modal blockt eh).
- Statusbar-Message aus altem Handler entfällt (Modal ersetzt).

### Settings-Propagation
- **Radio-Connect-Hook** (`mw_radio.py:_start_radio` ~Z.177): nach
  `self.radio.swr_alarm.connect(...)` ergänzen:
  ```python
  self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))
  ```
- **Settings-Save-Hook** (`settings_dialog.py:_save_and_close` ~Z.679):
  nach `self.settings.set("swr_limit", self.swr_limit.value())`
  zusätzlich:
  ```python
  parent = self.parent()
  if parent is not None and hasattr(parent, "radio") and getattr(parent.radio, "ip", None):
      parent.radio.set_swr_limit(self.swr_limit.value())
  ```
- **Clamp im Setter** (`flexradio.set_swr_limit`):
  ```python
  def set_swr_limit(self, value: float) -> None:
      v = max(1.5, min(10.0, float(value)))
      self._swr_limit = v
      print(f"[FlexRadio] SWR-Limit auf {v:.1f} gesetzt")
  ```

### Reaktivierung
- **Kein Auto-Resume.** Watchdog ist immer aktiv solange Signal
  verdrahtet. Nach Stop muss User CQ/OMNI bewusst neu klicken. Mike-Spec
  explizit.

## 5. Nicht im Scope

- **TUNE-Pfad:** `radio.tune_on()` setzt `_is_transmitting` nicht auf
  True. VITA-Meter-Alarm-Bedingung `self._is_transmitting and swr >=
  limit` greift dort nicht. → P54 (Auto-Tune-Modal bei Bandwechsel)
  übernimmt diesen Bereich. Hier nicht abgedeckt.
- **Eigener QTimer-200ms-Polling-Mechanismus** (ursprüngliche TODO-V0-
  Spec) — verworfen weil VITA-Loop schon liefert. KISS.
- **Cooldown-Logik** (10 s aus altem Handler) — nicht mehr nötig, Modal
  blockt.
- **Antennen-Diagnose / Frequenz-Tracking / Tuner-Auto-Start** —
  separat, kein P53.
- **Settings-UI-Änderungen** — Setting existiert schon, Wert wird nur
  jetzt korrekt durchgereicht.

## 6. Testbarkeit

`tests/test_p53_swr_watchdog.py` NEU:

| Test | AC | Pattern |
|---|---|---|
| T1 `test_alarm_2_in_a_row_triggers_stop` | AC1, AC4 | Echtes `Signal(float)` + Spy auf encoder.abort + ptt_off + qso_sm.stop_cq + cancel + cp.set_cq_active(False); 2 emits mit time.monotonic-Mock (50 ms Abstand) |
| T2 `test_isolated_alarm_no_stop` | AC2 | 1 emit, monotonic+600 ms simuliert, kein 2. Emit → keine Stop-Spies treffen |
| T3 `test_alarm_when_not_transmitting_returns` | AC3 | `encoder.is_transmitting=False`, 2 emits → spike_count zurück auf 0, KEIN Stop |
| T4 `test_stop_block_order` | AC4 | Order-Verify via MagicMock `mock_calls` Liste, Reihenfolge (1)-(9) |
| T5 `test_no_set_tx_antenna_in_stop` | AC5 | `radio.set_tx_antenna`-Spy nie aufgerufen |
| T6 `test_modal_dialog_text` | AC6 | `QMessageBox.warning` Monkey-Patch, prüft Titel + Text-Substring „SWR X.X (Limit Y.Y)" |
| T7 `test_panel_info_before_modal` | AC7 | `qso_panel.add_info`-Spy + `QMessageBox.warning`-Mock — Reihenfolge add_info vor modal |
| T8 `test_no_auto_resume_after_stop` | AC8 | Nach Stop: `cq_mode=False`, spike_count=0, kein hidden state |
| T9 `test_swr_limit_set_at_connect` | AC9 | Mock-Radio mit `set_swr_limit`-Spy, `_start_radio` ruft mit Settings-Wert (z.B. 2.5) |
| T10 `test_swr_limit_set_on_settings_save` | AC10 | Settings-Dialog `_save_and_close` ruft `parent.radio.set_swr_limit(2.5)` |
| T11 `test_set_swr_limit_clamps` | AC11 | `set_swr_limit(0.5) → 1.5`, `set_swr_limit(99.0) → 10.0`, `set_swr_limit(2.5) → 2.5` |
| T12 `test_radio_interface_has_set_swr_limit` | AC12 | `hasattr(RadioInterface, "set_swr_limit")` + abstract-Marker |
| T13 `test_spike_counter_reset_first_in_stop` | AC4(1) | 3 Emits in 50ms — nach 2. Emit läuft Stop einmal, 3. Emit (noch in Queue) findet spike_count=0 → kein zweiter Stop |

### Anti-Mock-Pflicht (Memory `feedback_test_critical_path_not_mock.md`)
- T1-T3, T13 nutzen **echte `Signal(float)`-Verbindung** zwischen Mock-
  Radio (mit `Signal`-Attribut) und `_on_swr_alarm`-Handler. Keine
  Direkt-Aufrufe des Handlers — die VITA-Loop-Realität muss durch das
  Signal.
- Stop-Block-Spies sind auf den `encoder`/`radio`/`qso_sm`/`qso_panel`-
  Mocks — der Spike-Counter-Code im Handler bleibt echt.
- `QMessageBox.warning` ist Klassen-Methode → Monkey-Patch via
  `monkeypatch.setattr(QMessageBox, "warning", spy)`.
- `time.monotonic` als Test-Stub um deterministische Zeit-Sprünge zu
  setzen — kein `time.sleep()` im Test (langsam + flaky).

---

## Anhang: Code-Skizze für `_on_swr_alarm` (Referenz, nicht final)

```python
@Slot(float)
def _on_swr_alarm(self, swr: float) -> None:
    # AC3: Pre-TX-Alarm aus ptt_on() ignorieren — kein laufender TX
    if not self.encoder.is_transmitting:
        self._swr_spike_count = 0
        return

    now = time.monotonic()
    first_t = getattr(self, "_swr_first_alarm_t", 0.0)

    if self._swr_spike_count == 0 or (now - first_t) > 0.5:
        # 1. Alarm ODER zu altes Fenster → neu starten
        self._swr_spike_count = 1
        self._swr_first_alarm_t = now
        return

    # 2. Alarm innerhalb 500 ms — Stop auslösen
    # AC4 Reset-Reihenfolge: SOFORT spike_count=0
    self._swr_spike_count = 0
    limit = self.settings.get("swr_limit", 3.0)

    # AC4 (2)-(7): Stop-Block antennen-neutral
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

    # AC7: Panel-Eintrag vor Modal
    self.qso_panel.add_info(f"⚠ TX abgebrochen — SWR {swr:.1f}")

    # AC6: Modal
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.warning(
        self,
        "SWR-Schutz ausgelöst",
        f"TX abgebrochen — SWR {swr:.1f} (Limit {limit:.1f}).\n"
        "Antenne tunen oder SWR-Limit in Einstellungen prüfen."
    )
```
