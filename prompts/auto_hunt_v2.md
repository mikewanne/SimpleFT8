# V2 — Auto-Hunt-Modus fuer SimpleFT8

## DeepSeek-Rolle (Pflicht-Praeambel)

Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software und PySide6-Applikationen (NICHT PyQt5 — wir nutzen PySide6, API-Unterschiede beachten: `Signal` statt `pyqtSignal`, `Slot` statt `pyqtSlot`). Deine einzige Aufgabe ist es, diesen Prompt zu kritisieren — NICHT das Problem zu loesen. Erstelle eine strukturierte Liste mit Luecken, fehlenden Informationen, Unklarheiten, Widerspruechen, Verbesserungsvorschlaegen und offenen Fragen. Bedenke: SimpleFT8 ist ein Hobby-Projekt, kein kommerzielles Produkt — Overengineering ist selbst ein Fehler den du benennen sollst.

---

## Ziel

Erweiterung der existierenden `core/auto_hunt.py` (255 Zeilen, AutoHunt-Klasse mit `enable/disable/select_next/_cooldown/_score/on_qso_complete/on_qso_timeout/on_band_change`) um einen zeitbeschraenkten Auto-Hunt-Modus. Dieser scannt CQ-Rufer auf dem aktuell eingestellten Band, ruft sie automatisch an, laeuft fest 10 Minuten und ist von Maus/Tastatur entkoppelt (Bot-Tarn-Schutz).

Aktivierung erfolgt verdeckt via Klick auf die Versionsnummer (Easter-Egg) — gemeinsam mit dem bestehenden OMNI CQ-Modus. Das Feature ist nicht in der oeffentlichen Doku erwaehnt.

## Akzeptanzkriterien

### UI

1. **3-Button-Layout** im QSO-Bereich (`ui/control_panel.py:760-773` — heute nur `btn_cq`):
   `[ CQ RUFEN ]  [ OMNI CQ ]  [ AUTO HUNT ]` — gleich breit, mutually exclusive via `QButtonGroup.setExclusive(True)`. Layout wird nur eingeblendet wenn Easter-Egg-Active=True; ansonsten nur `[ CQ RUFEN ]` voll breit (Status quo).

2. **Easter-Egg-Toggle:** erster Klick auf Versionsnummer (`ui/control_panel.py:1053`, heute Signal `omni_tx_clicked` → `MainWindow._on_omni_tx_easter_egg`) → `_easter_egg_active = True`, OMNI CQ + AUTO HUNT Buttons erscheinen. Zweiter Klick → False, Buttons verschwinden. Persistiert NICHT (jede Session beginnt mit Easter-Egg=Off).

3. **Manueller CQ RUFEN-Button** bleibt von Easter-Egg-Toggle unangetastet — auch wenn er gerade aktiv ist, laeuft er weiter. Nur OMNI CQ + AUTO HUNT erscheinen/verschwinden.

4. **Wenn Easter-Egg deaktiviert wird waehrend OMNI CQ oder AUTO HUNT aktiv:** entsprechender Modus wird vorher mit Reason `"easter_egg_off"` gestoppt (laufendes QSO darf zu Ende laufen, kein neues startet).

5. **Idle-State (kein Modus aktiv):** alle drei Mode-Buttons + TUNE klickbar.

6. **Aktiver Modus:** gewaehlter Button rot/aktiv, andere zwei + TUNE disabled.

7. **AUTO HUNT-Button-State-Machine:**
   - Idle: Text `"AUTO HUNT"`, klickbar.
   - Aktiv: Text `"AUTO HUNT — 7:42"` (Live-Countdown, sekuendlich), Klick = HALT mit Reason `"manual_halt"`.
   - Cooldown nach Auto-Stop: Text `"AUTO HUNT (5)"` `(4)` `(3)` ..., disabled.
   - Wieder Idle nach 5 Sekunden: Text `"AUTO HUNT"`, klickbar.

### Timing & Bot-Schutz

8. **10-Min-Hard-Stop:** Auto-Hunt-Timer (`QTimer`, single-shot, `setInterval(600_000)`) laeuft fest 10 Minuten ab `start_auto_hunt`-Aufruf. Maus/Tastatur-Aktivitaet beeinflussen den Timer NICHT (bewusste Entkopplung vom Totmannschalter).

9. **Pflicht-Restart:** nach Auto-Stop muss User explizit erneut den Button klicken (kein Auto-Restart, kein Reaktiveren durch Maus-Bewegung).

10. **5s Reflexions-Cooldown** nach Auto-Stop: Button disabled mit sekuendlichem Countdown — verhindert Reflex-Klick. Realisiert via `QTimer.singleShot(5000, ...)` der `_cooldown_phase = False` setzt + UI-State updated.

11. **Totmannschalter-Integration:** der bestehende Totmannschalter (15 Min ab letzter Maus/Tastatur-Aktivitaet) wird in `MainWindow` gefuehrt. Wenn `presence_ok=False` an `select_next()` uebergeben wird, returnt es bereits None (existiert). **NEU:** wenn Totmannschalter ausloest, ruft `MainWindow.<existing_totmann_handler>` zusaetzlich `auto_hunt.stop_auto_hunt("totmann_expired")` auf. Konkrete Hook-Stelle wird in Plan-Mode verifiziert.

### State-Machine & Slot-Affinitaet

12. **Slot-Affinitaet:** in `select_next()` wird der Filter auf `tx_even == self._last_tx_even` angewendet wenn `_last_tx_even is not None`. Falls keine Kandidaten mit gleichem Slot vorhanden → Fallback auf alle Kandidaten (Slot-Wechsel akzeptiert). Nach Auswahl: `self._last_tx_even = best.tx_even`.

13. **`_last_tx_even` Reset:** wird auf `None` zurueckgesetzt in (a) `start_auto_hunt()` (neue Session = Slot offen), (b) `on_band_change()` (neue Stationen = Slot offen), (c) `enable()` und `disable()`.

14. **Race-Condition-Sicherung:** `select_next()` prueft `self.active` an zwei Stellen — am Anfang (existiert bereits Z.132-138) UND **direkt vor Return** (NEU). Verhindert dass beim Timer-Ablauf zwischen `active`-Check und Return ein finaler Candidate zurueckkommt.

15. **Anrufversuche pro Station:** unveraendert 3 (`_MAX_ATTEMPTS = 3` in `core/auto_hunt.py:45`).

16. **Wartezeit auf Antwort:** unveraendert 2 Slots (= 30s FT8 / 15s FT4 / 7.6s FT2) — gesteuert durch bestehende QSO-State-Machine (`core/qso_state.py`), kein zusaetzlicher Code.

### Listen-Verwaltung

17. **`_cooldown` (5 Min Fehlversuch-Sperre):** wird `clear()`-ed bei (a) `start_auto_hunt()`, (b) `stop_auto_hunt(reason)` mit reason in {`"timer_expired"`, `"manual_halt"`, `"easter_egg_off"`}, (c) `on_band_change()`. NICHT bei `"totmann_expired"` (Totmann-Stops sind unfreiwillig — User soll bei Restart wieder dort weitermachen wo er aufgehoert hat).

18. **`_qso_log.is_worked(call, band)` (24h-Block fuer erfolgreiche QSOs):** bleibt unangetastet. Verhindert Doppel-QSO mit Stationen die in dieser Session bereits abgeschlossen wurden.

### Hardware-Pflicht — HOECHSTE PRIORITAET

19. **TX immer ueber ANT1 — zentralisierte Pflicht:**
    - **`Encoder.transmit()` (`core/encoder.py:126`):** vor `self._radio.ptt_on()` (Z.235) wird `self._radio.set_tx_antenna("ANT1")` defensiv aufgerufen — bei JEDEM TX (manuelle CQ, OMNI CQ, AUTO HUNT, QSO-Antworten).
    - **TUNE-Pfad (`radio.tune_on()`):** das ist KEIN Encoder.transmit-Pfad. ANT1-Guard wird zusaetzlich vor jedem `tune_on()`-Aufruf in `mw_radio.py` und `dx_tune_dialog.py` verifiziert. Dort schon mehrfach gesetzt (`mw_radio.py:993, 1078, dx_tune_dialog.py:192, 320`) — wird auf alle Aufrufer geprueft.
    - **Diversity-Pattern (70:30 / 50:50 / 30:70):** gilt strikt nur fuer RX-Antennen-Wechsel. TX bleibt bei ANT1, niemals ANT2 als TX-Slot vergeben.

20. **TUNE-Button disabled wenn Modus aktiv:** in `_set_button_states_for_active_mode()` Helper, der bei jedem Mode-Wechsel alle 4 Button-States setzt.

### Multi-Band & Cross-Mode

21. **Multi-Band: NEIN** — Auto-Hunt arbeitet nur auf dem aktuell eingestellten Band. Bei `on_band_change`: `stop_auto_hunt("band_change")`.

22. **Cross-Mode (FT8↔FT4↔FT2): NEIN** — Auto-Hunt arbeitet nur im aktiven Modus. Modus-Wechsel waehrend Auto-Hunt → `stop_auto_hunt("mode_change")` (NEU als Reason).

### QSO-Lifecycle

23. **QSO mid-Stop:** wenn 10-Min-Timer mitten im laufenden QSO ablaeuft → `active=False`, aber QSO laeuft normal zu Ende ueber bestehende `core/qso_state.py`-State-Machine. `select_next()` returnt strikt None nach `active=False` → kein neues QSO startet.

24. **`auto_hunt_stopped(reason: str)` Qt-Signal:** Klassen-Signal auf AutoHunt. Reasons: `"timer_expired"`, `"manual_halt"`, `"band_change"`, `"mode_change"`, `"totmann_expired"`, `"easter_egg_off"`.

25. **Tests:** mind. 16 Unit-Tests (siehe Abschnitt Testbarkeit) — 446 → 462 Tests gruen.

## Betroffene Module/Dateien

### Erweitern (Code-aendernd)

- **`core/auto_hunt.py` (255 Zeilen):**
  - Neue Attribute: `_auto_hunt_timer: QTimer`, `_reflexion_timer: QTimer`, `_last_tx_even: bool | None`, `_hunt_session_start: float`, `_cooldown_phase: bool`, `_stop_reason: str`.
  - Neue Methoden: `start_auto_hunt(duration_sec=600)`, `stop_auto_hunt(reason: str)`, `is_in_cooldown() -> bool`, `seconds_remaining() -> int`.
  - Neues Qt-Signal: `auto_hunt_stopped(reason: str)`. Klasse muss von `QObject` erben (heute keine Qt-Klasse — Refactor noetig).
  - Geaenderte Methoden: `select_next()` (Slot-Affinitaet-Filter + Doppel-Active-Check), `enable()/disable()` (delegieren an start_auto_hunt/stop_auto_hunt), `on_band_change()` (zusaetzlich `stop_auto_hunt("band_change")`).

- **`core/encoder.py:126` `Encoder.transmit()`:** vor `self._radio.ptt_on()` (Z.235) defensives `self._radio.set_tx_antenna("ANT1")`.

- **`ui/control_panel.py:760-773` `_RadioCard` QSO-Bereich:** 3-Button-Layout statt einzelnem `btn_cq`. Neue Members `btn_omni_cq`, `btn_auto_hunt`. `QButtonGroup` mit `setExclusive(True)`.

- **`ui/control_panel.py:1047-1056` Versionsnummer-Klick:** Signal `omni_tx_clicked` umbenennen zu `easter_egg_toggle_clicked`. Aufrufer in `ui/main_window.py:233` und `ui/main_window.py:514` entsprechend anpassen.

- **`ui/main_window.py:514` `_on_omni_tx_easter_egg`:** umbenannt zu `_on_easter_egg_toggle`. Toggelt `_easter_egg_active` und steuert OMNI CQ + AUTO HUNT Button-Sichtbarkeit. Wenn Toggle bei aktivem Modus: erst `auto_hunt.stop_auto_hunt("easter_egg_off")` (analog OMNI CQ).

- **`ui/main_window.py` (NEU):** Slot fuer `auto_hunt_stopped`-Signal — schaltet UI in Cooldown-State, startet 5s-Cooldown-Timer, setzt nach 5s wieder Idle.

- **`ui/main_window.py` Totmann-Hook (Plan-Mode-Verifikation):** existing presence-Tracking muss zusaetzlich `auto_hunt.stop_auto_hunt("totmann_expired")` rufen.

- **`ui/mw_qso.py`:** Auto-Hunt-Trigger pro Decode-Cycle — **Existenz unverifiziert in Schritt 0**, wird im Plan-Mode geprueft. Falls fehlt: neuer Hook der `candidate = auto_hunt.select_next(...)` ruft und QSO startet.

### Lesen / Referenzieren (unveraendert)

- `core/auto_hunt.py:45` (`_MAX_ATTEMPTS = 3`)
- `radio/base_radio.py:156-163` (`set_tx_antenna` Interface)
- `radio/flexradio.py:867` (`set_tx_antenna` Implementierung)
- `ui/mw_cycle.py:120-122` (`_tx_even`-Setzung pro Message)
- `core/qso_state.py` (QSO-State-Machine, AutoHunt nutzt nur `qso_idle`)

### Neu

- `tests/test_auto_hunt_extended.py` — 16 Unit-Tests.

## Randbedingungen

### Threading
- AutoHunt-Klasse laeuft im GUI-Thread (gleicher Thread wie Qt-Event-Loop). Refactor zu `QObject`-Subclass noetig damit `Signal` funktioniert.
- `QTimer` (10-Min-Stopper, 5s-Cooldown, 1s-Countdown-Polling) sind alle im GUI-Thread.
- Decode-Cycle-Trigger laeuft via `decoder.cycle_decoded`-Signal — **Plan-Mode-Verifikation:** ist das `Qt.QueuedConnection` aus Decoder-Thread → GUI-Thread? Falls nein: Race-Condition-Risiko und Refactor noetig.

### Persistence
- **Keine.** Easter-Egg-Active, AutoHunt-Active, Cooldown-Listen, `_last_tx_even` sind alle session-lokal.
- Beim App-Restart: Buttons im Idle-State, Easter-Egg deaktiviert, kein Auto-Hunt-Restart.

### UI-Regeln
- Alle 3 Mode-Buttons + TUNE haben dasselbe disabled-Verhalten via zentralem Helper `_update_button_states_for_active_mode()`.
- Countdown-Update via UI-seitigem 1s-`QTimer` der `auto_hunt.seconds_remaining()` + `is_in_cooldown()` polled. Nicht via Signal — Polling ist KISS und ausreichend.

### Hardware-Grenzen — HOECHSTE PRIORITAET
- ANT1 = TX-Antenne IMMER. ANT2 = NUR RX (siehe `CLAUDE.md` Hardware-Warnung).
- ANT2 (Regenrinne ~15m) ist nicht fuer 100W TX ausgelegt → Hardware-Schaden moeglich.
- Defensiver `set_tx_antenna("ANT1")` in `Encoder.transmit()` UND vor jedem `radio.tune_on()` Pflicht.

### Bot-Tarn-Schutz
- Auto-Hunt-Timer ist UNABHAENGIG vom Totmannschalter (15 Min). Maus/Tastatur reset ihn NICHT.
- Sich ueberschneidende Abschalt-Mechanismen = ethische Belt-and-suspenders. Nach jedem Auto-Stop (egal welcher Reason) ist Pflicht-Restart durch User.

## Nicht im Scope

- ❌ Multi-Band-Hopping (Contest-Feature, gegen SimpleFT8-Hobby-Funker-Philosophie)
- ❌ Cross-Mode (FT8↔FT4↔FT2) Auto-Wechsel
- ❌ Adaptive Anrufversuche (z.B. SNR-abhaengige Versuche-Anzahl) — KISS-Verstoss
- ❌ Konfigurierbare 10-Min-Dauer (fest, ethische Belt-and-suspenders)
- ❌ DX-spezifische Wartezeit (3 Slots fuer DX) — 2 Slots fuer alle reicht
- ❌ Persistente Worked-Stations-Liste ueber App-Restarts (`_qso_log` ist session-only, ausreichend)
- ❌ Konfigurierbare Antenne fuer TX (immer ANT1 wegen Hardware-Pflicht)
- ❌ "Auto-Hunt + OMNI CQ kombiniert" Hybridmodus (Phase 2 nach Feldtest, jetzt strikt mutually exclusive)
- ❌ Oeffentliche Dokumentation (Easter-Egg bleibt versteckt, nicht in README oder GitHub-Beschreibung)
- ❌ Auto-Restart nach 10-Min-Stop (manueller Klick Pflicht — Bot-Tarn-Schutz)

## Testbarkeit

`tests/test_auto_hunt_extended.py` (NEU) — 16 Tests:

### Klassen-Verhalten

1. `test_start_sets_active_and_starts_timer` — `start_auto_hunt(600)` setzt `active=True`, `_auto_hunt_timer` is running, `_last_tx_even` is None.
2. `test_select_next_returns_none_when_inactive` — `select_next` returnt None wenn `active=False`.
3. `test_double_active_check_in_select_next` — Race-Condition-Test: `active` wird zwischen Anfang und Return von `select_next` auf False gesetzt → returnt None (Boss-Korrektur).
4. `test_slot_affinity_prefers_same_tx_even` — nach erstem `select_next` mit `tx_even=True` wird im naechsten Zyklus Kandidat mit `tx_even=True` bevorzugt.
5. `test_slot_affinity_fallback_when_no_match` — wenn kein Kandidat mit gleichem `tx_even` verfuegbar, wird ein anderer genommen.
6. `test_last_tx_even_resets_on_start` — `start_auto_hunt` setzt `_last_tx_even = None`.
7. `test_last_tx_even_resets_on_band_change` — `on_band_change` setzt `_last_tx_even = None`.

### Listen-Verwaltung

8. `test_cooldown_blocks_recent_failure` — `on_qso_timeout(call)` schreibt Cooldown-Timestamp; `select_next` ueberspringt diese Station 5 Min lang.
9. `test_hard_reset_clears_cooldown_keeps_qso_log_on_timer_expired` — `stop_auto_hunt("timer_expired")` ruft `_cooldown.clear()`, `_qso_log` bleibt unberuehrt.
10. `test_no_cooldown_clear_on_totmann_expired` — `stop_auto_hunt("totmann_expired")` clear NICHT die Cooldown-Liste (User soll fortsetzen koennen).
11. `test_band_change_clears_cooldown` — `on_band_change` ruft `_cooldown.clear()`.

### Stop-Reasons + Signal

12. `test_auto_hunt_stopped_signal_emits_with_reason_for_each_reason` — fuer jeden der 6 Reasons (`timer_expired/manual_halt/band_change/mode_change/totmann_expired/easter_egg_off`) feuert das Signal mit korrektem String.

### Hardware-Pflicht

13. `test_encoder_transmit_sets_ant1_before_ptt_on` — Mock auf `radio.set_tx_antenna` und `radio.ptt_on`, prueft Reihenfolge: ANT1-Setzung VOR `ptt_on`.

### UI-Integration (mit `QT_QPA_PLATFORM=offscreen`)

14. `test_three_button_layout_visible_when_easter_egg_active` — Klick auf Versionsnummer → 3 Buttons sichtbar; zweiter Klick → nur `btn_cq` sichtbar.
15. `test_button_state_machine_idle_to_active_to_cooldown_to_idle` — Test mit MonkeyPatch von `_auto_hunt_timer.timeout` (direkter Signal-Emit via `signal.emit()` statt 600s warten) + `QTest.qWait(5100)` fuer 5s-Cooldown-Verifikation.
16. `test_easter_egg_off_during_active_mode_stops_with_reason` — Klick auf Versionsnummer waehrend Auto-Hunt aktiv → Signal feuert mit `reason="easter_egg_off"`, Buttons verschwinden, `active=False`.

Test-Strategie fuer QTimer-Mocks: keine echten Timeouts abwarten. Stattdessen `_auto_hunt_timer.timeout.emit()` direkt aufrufen + UI-State pruefen. Fuer 5s-Cooldown ist `QTest.qWait(5100)` akzeptabel da kurz.

## Aufwandsschaetzung (realistisch)

- AutoHunt-Klasse → QObject-Refactor + 6 Attr + 4 Methoden + Signal: 3-4 h
- Slot-Affinitaet + Race-Condition-Doppel-Check: 1 h
- UI-Refactor 3-Button-Layout + Easter-Egg-Toggle + Countdown: 3-4 h
- Hardware-ANT1-Guard im Encoder + Verifikation TUNE-Pfade: 1 h
- Totmann-Integration (Hook in MainWindow): 1 h
- 16 Tests: 3-4 h
- HISTORY.md, CLAUDE.md, manuelle Verifikation, atomare Commits: 2 h
- **Gesamt: ~2 Tage** (V1 hatte 1-1.5 — zu optimistisch)

## Implementierungs-Reihenfolge (atomare Commits)

1. `feat(safety): ANT1-Guard in Encoder.transmit()` — defensives `set_tx_antenna("ANT1")` zentral, plus 1 Test.
2. `refactor(auto_hunt): AutoHunt erbt von QObject, Signal-Foundation` — Vorbereitung fuer Qt-Signal, alle bestehenden Tests gruen halten.
3. `feat(auto_hunt): start/stop_auto_hunt + Timer-Logik + auto_hunt_stopped-Signal` — neue Methoden, Attribute, 6 Tests.
4. `feat(auto_hunt): Slot-Affinitaet + Race-Condition-Doppel-Check in select_next` — 4 Tests.
5. `feat(safety): Totmann-Integration triggert stop_auto_hunt("totmann_expired")` — Hook in MainWindow, 1 Test.
6. `refactor(ui): omni_tx_clicked → easter_egg_toggle_clicked Signal-Rename` — Pure Refactor, alle Tests gruen halten.
7. `feat(ui): 3-Button-Layout im QSO-Bereich (CQ/OMNI CQ/AUTO HUNT)` — mutually exclusive via QButtonGroup, sichtbar nur bei Easter-Egg-Active.
8. `feat(ui): AUTO HUNT Countdown-Display + 5s Cooldown-State-Machine + Easter-Egg-Toggle-Stop` — 3 Tests.
9. `chore(release): v0.75 — Auto-Hunt-Modus` — Version, HISTORY, CLAUDE.md.

Pro Commit: `pytest tests/ -q` muss gruen sein. Vor Commit 9: finaler DeepSeek-Codereview der geaenderten Files (`tools/deepseek_review.py --reasoner` mit relevanten Files).

## Plan-Mode-Verifikationen (vor Commit 1)

- `ui/mw_qso.py` Auto-Hunt-Trigger-Hook — existiert er, wo, in welcher Form?
- `decoder.cycle_decoded`-Signal Connection-Type — `Qt.QueuedConnection`?
- Existing Totmann-Code — wo ist die Stelle die `stop_auto_hunt("totmann_expired")` triggern soll?
- `omni_tx_clicked` Signal — alle Aufrufer (heute nur 1: `MainWindow:233`)?

## Dokumentations-Pflichten nach Implementierung

- `HISTORY.md`: ausfuehrlicher v0.75-Eintrag mit Workflow-Reflexion.
- `CLAUDE.md`: Header (Version + Test-Count), Auto-Hunt-Sektion in Bekannte-Fallen.
- **NICHT** in README oder oeffentlicher GitHub-Doku — Easter-Egg bleibt versteckt.
