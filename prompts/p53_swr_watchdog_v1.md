# P53 — SWR-Live-Watchdog (Hardware-Sicherheit) — V1

## 1. Ziel

Live-SWR-Watchdog während TX. Wenn SWR ≥ `settings.swr_limit` für 2
aufeinanderfolgende Messungen → TX sofort abbrechen (mid-slot), Komplett-
Stop aller Power-Modi, Modal-Warnung, QSO-Panel-Eintrag.

**Wurzel-Problem:** Mike-Field-Test 14.05.: nasse Antenne nach Regen →
SWR > 30 bei TX mit 70 W. `swr_limit` (3.0) in Settings hat NICHT
gegriffen weil der Check nur vor der Gain-Messung läuft
(`ui/mw_radio.py:1336+1352`), nicht im normalen TX-Pfad. FlexRadio-
Hardware-Schutz + Tuner haben gerettet — Lücke im App-Code.

**Architektur-Korrektur zum TODO (V0):** Statt eigenem QTimer-Watchdog
(200ms-Polling) reagieren wir auf das **bereits existierende
`swr_alarm`-Signal** (`radio/flexradio.py:45`), das im VITA-49-Meter-
Loop (`flexradio.py:1388-1390`) während TX feuert wenn SWR ≥ `_swr_limit`.
Kein neues Polling-Modul nötig. KISS.

## 2. Akzeptanzkriterien

| # | Kriterium | Verifikation |
|---|---|---|
| AC1 | Bei SWR ≥ Limit für 2 aufeinanderfolgende `swr_alarm`-Emits (Abstand ≥ 100 ms) → TX abgebrochen | Test mit 2 schnellen Signal-Emits |
| AC2 | Bei 1 isoliertem Alarm + danach keine weiteren Alarms in 500 ms → kein Stop | Spike-Schutz-Test |
| AC3 | Stop-Block ruft: `qso_sm.stop_cq()` + `cancel()` + `set_cq_active(False)` + `encoder.abort()` + `radio.ptt_off()` + `_omni_cq.stop("swr_block")` + `_auto_hunt.stop_auto_hunt("swr_block")` | Spy auf alle 7 Calls |
| AC4 | `radio.set_tx_antenna()` wird im Stop-Pfad **NIE** aufgerufen (ANT1 bleibt ANT1) | Spy negativ |
| AC5 | Modal `QMessageBox.warning` zeigt `SWR X.X (Limit Y.Y)` + Hinweis Antenne/Limit | UI-Smoke-Test |
| AC6 | `qso_panel.add_info("⚠ TX abgebrochen — SWR X.X")` als Historie-Eintrag | Spy/Capture |
| AC7 | **Kein Auto-Resume** — keine erneute Watchdog-Aktivierung, User muss bewusst CQ/OMNI klicken | Sequenz-Test |
| AC8 | `Settings.swr_limit` wird beim Radio-Connect an `flexradio.set_swr_limit(value)` propagiert (heute hardcoded 3.0) | grep + Init-Test |
| AC9 | Bei wiederholtem Setting-Change (Settings-Dialog Save) wird auch live-FlexRadio aktualisiert | Save-Hook-Test |
| AC10 | Tests grün 1245 → ≥ 1255 (+10) | pytest |

## 3. Betroffene Module/Dateien

| Datei | Funktion | Änderung |
|---|---|---|
| `radio/flexradio.py:68` | `_swr_limit` Init | NEU `set_swr_limit(value)`-Methode |
| `radio/flexradio.py:1388` | VITA-Meter Alarm-Emit | unverändert — Signal feuert schon richtig |
| `ui/mw_tx.py:99-105` | `_on_swr_alarm` | Komplett-Rewrite: Spike-Counter + Stop-Block + Modal + Panel-Eintrag |
| `ui/mw_radio.py:160-180` | Radio-Init nach Connect | NEU: `radio.set_swr_limit(settings.swr_limit)` |
| `ui/settings_dialog.py:679` | `_save_and_close` | NEU: nach `settings.set("swr_limit", ...)` auch `radio.set_swr_limit(...)` falls `radio.ip` |
| `tests/test_p53_swr_watchdog.py` | NEU | T1-T10 (AC1-AC10) |

## 4. Randbedingungen

### Threading
- `swr_alarm.emit()` läuft im VITA-49-Decoder-Thread.
- `_on_swr_alarm` ist `@Slot(float)` — Qt verbindet aus Worker-Thread mit
  `Qt.AutoConnection` → automatisch `QueuedConnection` → läuft im GUI-
  Thread. ✓ Kein eigenes Lock nötig.
- Spike-Counter ist Instanz-Var — GUI-Thread atomar.

### Spike-Schutz
- `_swr_spike_count`-Counter und `_swr_first_alarm_t`-Zeitstempel.
- 1. Alarm → Counter=1, Zeitstempel speichern, return.
- 2. Alarm INNERHALB 500 ms: Counter=2 → **Stop auslösen**.
- 2. Alarm NACH 500 ms: als neuer 1. Alarm werten (Counter zurück auf 1).
- Nach Stop: Counter sofort auf 0 zurücksetzen.
- **Begründung 500 ms:** VITA-Meter-Loop liefert SWR typisch alle ~50-100 ms.
  500 ms = 5-10 Reads → robust gegen 1-Sample-Glitch, schnell genug gegen
  echte Last-Probleme (PA-Schutz greift bei FlexRadio nach ~1 s).

### Hardware-Pflicht (CLAUDE.md)
- Stop-Block darf **NICHT** `radio.set_tx_antenna(...)` aufrufen. ANT1
  bleibt ANT1. `encoder.abort()` + `radio.ptt_off()` sind antennen-neutral.

### UI / UX
- Modal: `QMessageBox.warning(self, "SWR-Schutz ausgelöst", "TX
  abgebrochen — SWR X.X (Limit Y.Y).\nAntenne tunen oder SWR-Limit in
  Einstellungen prüfen.")` — User-Klick erforderlich (kein non-modal).
- Kein Cooldown mehr nötig (Modal blockt eh).
- `qso_panel.add_info("⚠ TX abgebrochen — SWR X.X")` — vor Modal aufrufen
  (Modal blockt sonst Panel-Update).

### Settings-Propagation
- Radio-Connect-Pfad (`mw_radio.py:_start_radio` ~Z.170): nach
  `self.radio.swr_alarm.connect(...)` auch
  `self.radio.set_swr_limit(self.settings.get("swr_limit", 3.0))`.
- Settings-Dialog-Save (`settings_dialog.py:_save_and_close` ~Z.679):
  zusätzlich `parent.radio.set_swr_limit(...)` wenn `parent.radio.ip`.
- Default 3.0 bleibt erhalten.

### Reaktivierung
- **Kein Auto-Resume.** Watchdog ist immer aktiv solange `swr_alarm`-
  Signal verdrahtet ist. Nach Stop muss User CQ/OMNI bewusst neu klicken.

## 5. Nicht im Scope

- Eigener QTimer-200ms-Polling-Mechanismus (TODO-Spec V0) — verworfen,
  weil VITA-Loop schon liefert. KISS.
- Cooldown-Logik (10 s) — nicht mehr nötig, Modal blockt.
- Frequency-Tracking / Antennen-Diagnose / Tuner-Auto-Start — separat
  (siehe P54 Auto-Tune bei Bandwechsel).
- Settings-UI-Änderungen — Setting existiert schon, Wert wird nur jetzt
  korrekt durchgereicht.

## 6. Testbarkeit

| Test | AC | Pattern |
|---|---|---|
| T1 `test_alarm_2_in_a_row_triggers_stop` | AC1 | Echtes Signal, 2 emits mit 50 ms Abstand, alle 7 Spies treffen |
| T2 `test_isolated_alarm_no_stop` | AC2 | 1 emit, 600 ms Wartezeit, kein 2. → Spies NICHT getroffen |
| T3 `test_stop_block_full_calls` | AC3 | qso_sm.stop_cq + cancel + set_cq_active + abort + ptt_off + omni.stop + auto_hunt.stop alle 1× |
| T4 `test_no_set_tx_antenna_in_stop` | AC4 | radio.set_tx_antenna-Spy: nie aufgerufen |
| T5 `test_modal_dialog_shown` | AC5 | QMessageBox.warning mit korrektem Text (Monkey-Patch) |
| T6 `test_panel_info_entry` | AC6 | qso_panel.add_info-Spy: "⚠ TX abgebrochen — SWR X.X" |
| T7 `test_no_auto_resume` | AC7 | Nach Stop: kein cq_mode/Watchdog-Reaktivierung |
| T8 `test_swr_limit_propagated_at_connect` | AC8 | Mock-Radio mit set_swr_limit-Spy, Init-Pfad ruft mit settings-Wert |
| T9 `test_swr_limit_propagated_on_settings_save` | AC9 | Settings-Save-Hook ruft radio.set_swr_limit mit neuem Wert |
| T10 `test_spike_counter_reset_after_stop` | AC1+AC2 | Nach Stop ist Counter=0 (kein Memory-State) |

### Anti-Mock-Pflicht (Memory `feedback_test_critical_path_not_mock.md`)
- T1/T2 nutzen **echtes `Signal(float)`** und echte `emit()`-Calls — kein
  Mock-Override des Handlers selbst. Nur `radio.ptt_off`, `encoder.abort`,
  `qso_sm.stop_cq` etc. werden gespy't.
- Spike-Counter-Logik im echten `_on_swr_alarm`-Code, nicht im Mock.

---

## Hinweise zur Self-Review (V2-Vorbereitung)

- ✓ Hardware-Pflicht ANT1 explizit in §4 dokumentiert
- ✓ Threading-Pfad expliziert (VITA-Thread → Queued → GUI-Thread)
- ✓ KISS-Begründung gegen V0-QTimer-Pfad
- ✓ Spike-Schutz mit Zahlenbegründung (500 ms = 5-10 VITA-Reads)
- ✓ Auto-Resume bewusst NICHT (Mike-Spec)
- ✓ Zweiter Bug (Settings → FlexRadio nicht propagiert) als AC8+AC9
- ✓ Tests mit Anti-Mock-Klausel
- ? Encoder-Race: Was wenn Alarm zwischen `encoder.abort()` und Worker-
  finally feuert? Verifiziert: `abort()` setzt `_is_transmitting=False`,
  zweiter Alarm-Check `_is_transmitting` läuft im VITA-Loop weiter aber
  `if self._is_transmitting and swr >= limit` greift nicht mehr → kein
  doppel-emit. ✓
- ? Connect-Modal-Race (P26): Wenn `set_swr_limit` vor Radio-connect
  aufgerufen wird (z.B. Settings-Save ohne Radio) → `parent.radio.ip`
  None → skip. ✓
- ? Reentrance: 2 Alarms in 50 ms aus VITA-Thread → durch QueuedConnection
  serialisiert im GUI-Thread → kein Race im Spike-Counter. ✓
