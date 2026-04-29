# V3 — Auto-Hunt-Modus fuer SimpleFT8

## DeepSeek-Rolle (Pflicht-Praeambel)

Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software und PySide6-Applikationen (NICHT PyQt5 — wir nutzen PySide6, API-Unterschiede beachten: `Signal` statt `pyqtSignal`, `Slot` statt `pyqtSlot`). Deine einzige Aufgabe ist es, diesen Prompt zu kritisieren — NICHT das Problem zu loesen. Erstelle eine strukturierte Liste mit Luecken, fehlenden Informationen, Unklarheiten, Widerspruechen, Verbesserungsvorschlaegen und offenen Fragen. Bedenke: SimpleFT8 ist ein Hobby-Projekt, kein kommerzielles Produkt — Overengineering ist selbst ein Fehler den du benennen sollst.

---

## Ziel

Erweiterung der existierenden `core/auto_hunt.py` (255 Zeilen, AutoHunt-Klasse) um einen zeitbeschraenkten Auto-Hunt-Modus. Dieser scannt CQ-Rufer auf dem aktuell eingestellten Band, ruft sie automatisch an, laeuft fest 10 Minuten und ist von Maus/Tastatur entkoppelt (Bot-Tarn-Schutz).

Aktivierung erfolgt verdeckt via Klick auf die Versionsnummer (Easter-Egg) — gemeinsam mit dem bestehenden OMNI CQ-Modus. Das Feature ist nicht in der oeffentlichen Doku erwaehnt.

## Akzeptanzkriterien

### A. UI

**A1.** 3-Button-Layout im QSO-Bereich (`ui/control_panel.py:760-773`, heute nur `btn_cq`):
`[ CQ RUFEN ]  [ OMNI CQ ]  [ AUTO HUNT ]` — gleich breit, mutually exclusive via `QButtonGroup.setExclusive(True)`. Layout nur sichtbar wenn `_easter_egg_active=True`. **TUNE-Button ist NICHT Teil der QButtonGroup** — er ist separat und wird nur via `setEnabled(False/True)` gesteuert.

**A2.** Easter-Egg-Toggle: erster Klick auf Versionsnummer (`ui/control_panel.py:1053`) → `_easter_egg_active=True`, OMNI CQ + AUTO HUNT Buttons erscheinen. Zweiter Klick → False, Buttons verschwinden. **Persistiert NICHT** (jede Session beginnt mit Easter-Egg=Off).

**A3.** Manueller `btn_cq` (CQ RUFEN) bleibt von Easter-Egg-Toggle unangetastet — auch wenn er gerade aktiv ist, laeuft er weiter. Nur OMNI CQ + AUTO HUNT erscheinen/verschwinden.

**A4.** Wenn Easter-Egg waehrend aktivem OMNI CQ oder AUTO HUNT deaktiviert wird:
- Buttons verschwinden **sofort** vom UI (User hat ja explizit ausgeschaltet).
- `auto_hunt.stop_auto_hunt("easter_egg_off")` wird gerufen (analog fuer OMNI CQ).
- `active=False` setzt fest, dass kein neues QSO startet.
- Falls QSO gerade laeuft: laeuft ueber bestehende QSO-State-Machine im Hintergrund zu Ende.

**A5.** Idle-State (kein Modus aktiv): alle drei Mode-Buttons + TUNE klickbar.

**A6.** Aktiver Modus: gewaehlter Button rot/aktiv, andere zwei + TUNE disabled.

**A7.** AUTO HUNT-Button-State-Machine (3 Zustaende):
- **Idle:** Text `"AUTO HUNT"`, klickbar.
- **Active:** Text `"AUTO HUNT — 7:42"` (Live-Countdown, sekuendlich), Klick = HALT mit Reason `"manual_halt"`.
- **Disabled-Countdown** (waehrend 5s UI-Reflexions-Cooldown): Text `"AUTO HUNT (5)"` `(4)` `(3)` ..., disabled.
- Nach 5 Sekunden Cooldown wieder Idle (Text `"AUTO HUNT"`, klickbar).

### B. Timing & Bot-Schutz

**B1.** **10-Min-Hard-Stop:** `_auto_hunt_timer` (`QTimer`, single-shot, `setInterval(600_000)`) laeuft fest 10 Minuten ab `start_auto_hunt`-Aufruf. Maus/Tastatur-Aktivitaet beeinflussen den Timer NICHT.

**B2.** **Doppelklick-Schutz:** wenn `start_auto_hunt` bei aktiver Session erneut gerufen wird → existierender Timer wird gestoppt + neuer Timer gestartet (clean state, Idempotenz).

**B3.** **Pflicht-Restart:** nach jedem Auto-Stop muss User explizit erneut den Button klicken (kein Auto-Restart, kein Reaktivieren durch Maus-Bewegung).

**B4.** **5s UI-Reflexions-Cooldown** nach Auto-Stop bei ALLEN Reasons (auch `"totmann_expired"`): Button disabled mit sekuendlichem Countdown — verhindert Reflex-Klick. Realisiert via UI-seitigem `QTimer.singleShot(5000, ...)` der nach Ablauf den Button wieder Idle setzt.

**B5.** **Totmannschalter-Integration:** der bestehende Totmannschalter (15 Min ab letzter Maus/Tastatur-Aktivitaet) wird in `MainWindow` gefuehrt. Defense-in-Depth:
- `presence_ok=False` an `select_next()` greift bereits (existing) — verhindert neue QSOs.
- **NEU:** wenn Totmannschalter ausloest, ruft der entsprechende `MainWindow`-Handler zusaetzlich `auto_hunt.stop_auto_hunt("totmann_expired")` auf — das stoppt zudem den `_auto_hunt_timer` und triggert das Signal fuer UI-Cooldown.
- Konkrete Hook-Stelle wird in **Plan-Mode** verifiziert.

### C. State-Machine & Slot-Affinitaet

**C1.** **Slot-Affinitaet** in `select_next()`: Filter auf `tx_even == self._last_tx_even` wenn `_last_tx_even is not None`. Falls keine Kandidaten mit gleichem Slot vorhanden → Fallback auf alle Kandidaten (Slot-Wechsel akzeptiert). Nach Auswahl: `self._last_tx_even = best.tx_even`.

**C2.** **`_last_tx_even` Reset:** wird auf `None` gesetzt in:
- (a) `start_auto_hunt()` — neue Session = Slot offen.
- (b) `stop_auto_hunt(reason="band_change")` — neue Stationen = Slot offen.
- (c) `stop_auto_hunt(reason="mode_change")` — analog.

Reset-Logik wird zentral in `stop_auto_hunt` reason-basiert gesteuert (siehe C5).

**C3.** **Race-Condition-Sicherung:** `select_next()` prueft `self.active` an zwei Stellen:
- Anfang (existiert bereits Z.132-138).
- **Direkt vor Return** (NEU). Verhindert dass beim Timer-Ablauf zwischen `active`-Check und Return ein finaler Candidate zurueckkommt. **Begruendung:** Mike's 10-Min-Hard-Cap ist ethisch gesetzt — kein "letztes QSO" nach Ablauf.

**C4.** **`_manual_override` bleibt:** existierender Mechanismus (manueller Stations-Klick pausiert Auto-Hunt fuer dieses QSO) wird NICHT veraendert. `select_next()` returnt None wenn `_manual_override=True`.

**C5.** **`stop_auto_hunt(reason)` zentralisiert ALL cleanup logic:**
- ALWAYS: `active=False`, Timer stoppen, `auto_hunt_stopped(reason)` Signal emittieren.
- Bei reason in {`"timer_expired"`, `"manual_halt"`, `"easter_egg_off"`}: `_cooldown.clear()`, `_last_tx_even=None`.
- Bei reason in {`"band_change"`, `"mode_change"`}: `_cooldown.clear()`, `_last_tx_even=None`.
- Bei reason `"totmann_expired"`: `_cooldown` und `_last_tx_even` bleiben (User soll bei Restart fortsetzen).
- `_qso_log` bleibt ALWAYS unangetastet.

**C6.** Anrufversuche pro Station: unveraendert 3 (`_MAX_ATTEMPTS=3` in `core/auto_hunt.py:45`).

**C7.** Wartezeit auf Antwort: unveraendert 2 Slots (= 30s FT8 / 15s FT4 / 7.6s FT2) — gesteuert durch bestehende `core/qso_state.py`, kein zusaetzlicher Code.

### D. Listen-Verwaltung (Naming-Klarstellung)

Zwei verschiedene "Cooldowns" — sauber trennen in Doku und Code-Kommentaren:

- **Anruf-Fehlversuch-Cooldown** (`_cooldown: dict[str, float]`): 5 Min Sperre nach `on_qso_timeout`. Existiert (`_COOLDOWN_SECS`).
- **UI-Reflexions-Cooldown**: 5 Sekunden disabled-State des AUTO HUNT Buttons nach Auto-Stop. Realisiert UI-seitig.

**D1.** **Anruf-Fehlversuch-Cooldown:** `_cooldown[call] = time.time()` bei `on_qso_timeout(call)`. `select_next` ueberspringt Stationen mit `now - last_fail < _COOLDOWN_SECS` (existing).

**D2.** **`_qso_log.is_worked_on_band(call, band)`:** existing-Check in `_score()` bleibt unveraendert. Verhindert Doppel-QSO mit Stationen die in dieser Session bereits abgeschlossen wurden.

### E. Hardware-Pflicht — HOECHSTE PRIORITAET

**E1.** **TX immer ueber ANT1 — zentralisiert:**
- `Encoder.transmit()` (`core/encoder.py:126`): vor `self._radio.ptt_on()` (Z.235) defensives `self._radio.set_tx_antenna("ANT1")`.
  **Plan-Mode-Verifikation:** exakte Zeilennummer Z.126 + Z.235 in aktueller Code-Version pruefen.
- TUNE-Pfad (`radio.tune_on()`): KEIN Encoder-Pfad. ANT1-Guard wird zusaetzlich verifiziert vor jedem `tune_on()` in `mw_radio.py:993, 1078` und `dx_tune_dialog.py:192, 320`. Plan-Mode: alle weiteren Aufrufer pruefen.
- Diversity-Pattern (70:30 / 50:50 / 30:70): gilt strikt nur fuer RX-Antennen-Wechsel. TX bleibt bei ANT1, niemals ANT2 als TX-Slot.

**E2.** TUNE-Button disabled wenn Mode-Button aktiv: zentraler Helper `_update_button_states_for_active_mode()` setzt bei jedem Mode-Wechsel alle 4 Button-States.

### F. Modus-Beschraenkung

**F1.** Multi-Band: NEIN — Auto-Hunt arbeitet nur auf dem aktuell eingestellten Band. Bei `on_band_change`: `stop_auto_hunt("band_change")`.

**F2.** Cross-Mode (FT8↔FT4↔FT2): NEIN — Auto-Hunt arbeitet nur im aktiven Modus. Modus-Wechsel waehrend Auto-Hunt → `stop_auto_hunt("mode_change")`.

### G. Signal & Klassen-Refactor

**G1.** **AutoHunt erbt von `QObject`** (heute keine Qt-Klasse). Voraussetzung fuer `Signal`. Alle bestehenden Tests muessen mit `QApplication`-Fixture laufen — Plan-Mode-TODO.

**G2.** **Neues Signal `auto_hunt_stopped(reason: str)`** auf der Klasse. Reasons (6 Stueck): `"timer_expired"`, `"manual_halt"`, `"band_change"`, `"mode_change"`, `"totmann_expired"`, `"easter_egg_off"`.

**G3.** Alte `enable()` / `disable()`-Methoden werden ENTFERNT. Aufrufer muessen auf `start_auto_hunt(duration_sec=600)` / `stop_auto_hunt(reason)` umgestellt werden. **Plan-Mode-TODO:** alle aktuellen Aufrufer von `enable()/disable()` finden und anpassen.

**G4.** **`_pause_remaining` wird ENTFERNT** — durch `active`-Check redundant. `select_next` returnt None wenn `active=False`, das reicht.

## Betroffene Module/Dateien

### Erweitern (Code-aendernd)

- **`core/auto_hunt.py`:** Refactor zu `QObject`-Subclass. 5 neue Attribute (`_auto_hunt_timer`, `_last_tx_even`, `_hunt_session_start`, `_stop_reason`, sowie `_easter_egg_active`-Spiegelung optional). 4 neue Methoden (`start_auto_hunt`, `stop_auto_hunt`, `is_in_cooldown`, `seconds_remaining`). Neues Signal `auto_hunt_stopped(str)`. Geaenderte Methoden: `select_next` (Slot-Affinitaet + Doppel-Active-Check), `on_band_change` (delegiert an `stop_auto_hunt("band_change")`). **Entfernt:** `enable()`, `disable()`, `_pause_remaining`.

- **`core/encoder.py`:** `Encoder.transmit()` (~Z.126) ergaenzt um defensives `self._radio.set_tx_antenna("ANT1")` vor `self._radio.ptt_on()` (~Z.235). **Plan-Mode-Verifikation:** exakte Zeilennummer.

- **`ui/control_panel.py:760-773`:** `_RadioCard` QSO-Bereich um 3-Button-Layout erweitert. Neue Members `btn_omni_cq`, `btn_auto_hunt`. `QButtonGroup` mit `setExclusive(True)`. TUNE bleibt SEPARAT.

- **`ui/control_panel.py:1047-1056`:** Versionsnummer-Klick: Signal `omni_tx_clicked` umbenannt zu `easter_egg_toggle_clicked`. Aufrufer in `ui/main_window.py:233` + `:514` anpassen.

- **`ui/main_window.py:514` `_on_omni_tx_easter_egg`:** umbenannt zu `_on_easter_egg_toggle`. Toggelt `_easter_egg_active`. Bei Toggle waehrend aktivem Modus: vorher `auto_hunt.stop_auto_hunt("easter_egg_off")` (analog OMNI CQ).

- **`ui/main_window.py` (NEU):** Slot fuer `auto_hunt_stopped`-Signal. Schaltet UI in Disabled-Countdown-State (5s), startet UI-Cooldown-Timer, setzt nach 5s Idle.

- **`ui/main_window.py` Totmann-Hook (Plan-Mode):** existing presence-Tracking ergaenzt um `auto_hunt.stop_auto_hunt("totmann_expired")` Aufruf.

- **`ui/mw_qso.py`:** Auto-Hunt-Trigger pro Decode-Cycle — **Existenz unverifiziert**, Plan-Mode-Pruefung. Falls fehlt: neuer Hook der `candidate = auto_hunt.select_next(...)` ruft und QSO startet.

### Lesen / Referenzieren (unveraendert)

- `core/auto_hunt.py:45` (`_MAX_ATTEMPTS=3`)
- `radio/base_radio.py:156-163` (`set_tx_antenna` Interface)
- `radio/flexradio.py:867` (`set_tx_antenna` Implementierung)
- `ui/mw_cycle.py:120-122` (`_tx_even`-Setzung)
- `core/qso_state.py` (QSO-State-Machine, AutoHunt nutzt nur `qso_idle`)

### Neu

- `tests/test_auto_hunt_extended.py` — 12 Unit-Tests.

## Randbedingungen

### Threading
- AutoHunt im GUI-Thread (gleicher Thread wie Qt-Event-Loop). `QObject`-Subclass-Refactor noetig.
- `QTimer`-Instanzen (10-Min-Stopper, UI-Cooldown-Singleshot, UI-Polling) alle im GUI-Thread.
- **Plan-Mode-Verifikation:** ist `decoder.cycle_decoded`-Signal mit `Qt.QueuedConnection` verbunden? Wenn nein: Race-Risiko und Refactor noetig.

### Persistence
- **Keine.** Easter-Egg-Active, Auto-Hunt-Active, Cooldowns, `_last_tx_even` sind alle session-lokal.
- App-Restart: alles im Idle-State.

### UI-Regeln
- 3 Mode-Buttons + TUNE: zentraler Helper `_update_button_states_for_active_mode()`.
- Countdown-Update via UI-seitigem 1s-`QTimer` der `auto_hunt.seconds_remaining()` + `auto_hunt.is_in_cooldown()` polled.
- UI-Reflexions-Cooldown via UI-seitigem `QTimer.singleShot(5000, idle_state)`.
- **Zwei separate Timer im UI** (1s-Polling + 5s-Singleshot) — bewusst KISS: ein einziger Timer mit State-Switch waere komplexer als zwei klar getrennte.

### Hardware-Grenzen — HOECHSTE PRIORITAET
- ANT1 = TX-Antenne IMMER. ANT2 = NUR RX (siehe `CLAUDE.md` Hardware-Warnung).
- ANT2 (Regenrinne ~15m) ist nicht fuer 100W TX ausgelegt → Hardware-Schaden moeglich.
- Defensiver `set_tx_antenna("ANT1")` in `Encoder.transmit()` UND vor jedem `radio.tune_on()` Pflicht.

### Bot-Tarn-Schutz
- Auto-Hunt-Timer ist UNABHAENGIG vom Totmannschalter (15 Min). Maus/Tastatur reset ihn NICHT.
- Sich ueberschneidende Abschalt-Mechanismen = ethische Belt-and-suspenders.
- Pflicht-Restart durch User nach jedem Auto-Stop.

## Nicht im Scope

- ❌ Multi-Band-Hopping (Contest-Feature, gegen Hobby-Funker-Philosophie)
- ❌ Cross-Mode (FT8↔FT4↔FT2) Auto-Wechsel
- ❌ Adaptive Anrufversuche (SNR-abhaengig) — KISS-Verstoss
- ❌ Konfigurierbare 10-Min-Dauer (fest, ethische Belt-and-suspenders)
- ❌ DX-spezifische Wartezeit (3 Slots fuer DX) — 2 Slots fuer alle reicht
- ❌ Persistente Worked-Stations-Liste ueber App-Restarts (`_qso_log` session-only ausreichend)
- ❌ Konfigurierbare Antenne fuer TX (immer ANT1 wegen Hardware-Pflicht)
- ❌ "Auto-Hunt + OMNI CQ kombiniert" Hybridmodus (Phase 2 nach Feldtest, jetzt strikt mutually exclusive)
- ❌ Oeffentliche Dokumentation (Easter-Egg bleibt versteckt)
- ❌ Auto-Restart nach 10-Min-Stop (manueller Klick Pflicht — Bot-Tarn-Schutz)
- ❌ `enable()/disable()` Backwards-Compat (entfernt — alle Aufrufer werden umgestellt)
- ❌ Rueckwaerts-Kompatible API (Hobby-Projekt ohne externe API-User)

## Testbarkeit

`tests/test_auto_hunt_extended.py` (NEU) — 12 Tests:

### Klassen-Verhalten

1. `test_start_sets_active_starts_timer_resets_state` — `start_auto_hunt(600)` setzt `active=True`, `_auto_hunt_timer` running, `_last_tx_even=None`.
2. `test_select_next_returns_none_when_inactive` — kein Hunt wenn `active=False`.
3. `test_double_active_check_in_select_next` — Race-Condition: `active` zwischen Anfang+Return auf False → returnt None.
4. `test_slot_affinity_prefers_same_tx_even` — bevorzugt Kandidat mit gleichem Slot.
5. `test_slot_affinity_fallback_when_no_match` — Fallback wenn kein Match.
6. `test_double_start_restarts_timer` — `start_auto_hunt` bei aktiver Session: alter Timer gestoppt, neuer gestartet.
7. `test_manual_override_blocks_select_next` — `_manual_override=True` → returnt None.

### Stop-Reasons + Listen-Logik

8. `test_stop_reasons_clear_cooldown_and_last_tx_even_correctly` — Parametrized: timer_expired/manual_halt/easter_egg_off/band_change/mode_change clearen, totmann_expired NICHT.
9. `test_auto_hunt_stopped_signal_emits_with_reason` — Parametrized fuer alle 6 Reasons.
10. `test_qso_log_unaffected_by_stop` — `_qso_log` bleibt nach `stop_auto_hunt(any_reason)` unveraendert.

### Hardware-Pflicht

11. `test_encoder_transmit_sets_ant1_before_ptt_on` — Mock auf `radio.set_tx_antenna` und `radio.ptt_on`, prueft Reihenfolge.

### UI-Integration (mit `QT_QPA_PLATFORM=offscreen`)

12. `test_ui_full_lifecycle` — kombiniert: Easter-Egg-Toggle zeigt 3 Buttons → Klick AUTO HUNT (active) → MonkeyPatch `_auto_hunt_timer.timeout.emit()` → Stop-Signal → 5s UI-Cooldown via `QTest.qWait(5100)` → Idle-State. Plus: zweiter Easter-Egg-Klick versteckt Buttons.

**Test-Strategie fuer QTimer:** keine echten Timeouts. Direkt `_auto_hunt_timer.timeout.emit()` rufen. Fuer UI-Cooldown ist `QTest.qWait(5100)` akzeptabel da kurz.

**Ziel:** 446 → 458 Tests gruen.

## Aufwandsschaetzung (realistisch)

- AutoHunt → QObject-Refactor + Attribute + Methoden + Signal + select_next-Anpassung: 4-5 h
- enable/disable entfernen + alle Aufrufer umstellen + bestehende Tests fixen: 2 h
- UI-Refactor 3-Button-Layout + Easter-Egg-Toggle + Countdown + Cooldown: 4-5 h
- Hardware-ANT1-Guard im Encoder + TUNE-Pfad-Verifikation: 1.5 h
- Totmann-Integration (Hook in MainWindow): 1 h
- 12 Tests: 3-4 h
- HISTORY.md, CLAUDE.md, manuelle Verifikation, atomare Commits: 2-3 h
- **Gesamt: ~3 Tage** (V2 hatte 2 — DeepSeek-Review hat 1 Tag mehr realistisch gemacht)

## Implementierungs-Reihenfolge (atomare Commits)

1. `feat(safety): ANT1-Guard in Encoder.transmit()` — defensives `set_tx_antenna("ANT1")` zentral, plus 1 Test.
2. `refactor(auto_hunt): AutoHunt erbt von QObject, Signal-Foundation` — Vorbereitung fuer Qt-Signal, alle bestehenden Tests gruen halten (mit QApplication-Fixture).
3. `refactor(auto_hunt): enable/disable entfernen + _pause_remaining entfernen` — alle Aufrufer auf start_auto_hunt/stop_auto_hunt umstellen.
4. `feat(auto_hunt): start_auto_hunt + stop_auto_hunt + auto_hunt_stopped-Signal` — Timer, Reason-basierte Cleanup-Logik, Doppelklick-Schutz, 5 Tests.
5. `feat(auto_hunt): Slot-Affinitaet + Race-Condition-Doppel-Check in select_next` — 3 Tests.
6. `feat(safety): Totmann-Integration triggert stop_auto_hunt("totmann_expired")` — Hook in MainWindow.
7. `refactor(ui): omni_tx_clicked → easter_egg_toggle_clicked Signal-Rename` — pure Refactor, alle Tests gruen.
8. `feat(ui): 3-Button-Layout im QSO-Bereich (CQ/OMNI CQ/AUTO HUNT)` — mutually exclusive via QButtonGroup.
9. `feat(ui): AUTO HUNT Countdown + 5s UI-Cooldown + Easter-Egg-Toggle-Stop` — 1 UI-Lifecycle-Test.
10. `chore(release): v0.75 — Auto-Hunt-Modus` — Version, HISTORY, CLAUDE.md.

Pro Commit: `pytest tests/ -q` muss gruen sein. Vor Commit 10: finaler DeepSeek-Codereview der geaenderten Files (`tools/deepseek_review.py --reasoner` mit relevanten Files).

## Plan-Mode-Verifikationen (vor Commit 1 abarbeiten)

- `core/encoder.py` exakte Zeilennummern fuer `transmit()` und `ptt_on()` (Z.126 + Z.235 aus V2 verifizieren).
- `ui/mw_qso.py` Auto-Hunt-Trigger-Hook — existiert er? Wo? In welcher Form?
- `decoder.cycle_decoded`-Signal Connection-Type — `Qt.QueuedConnection`?
- Existing Totmann-Code — wo ist die Stelle die `stop_auto_hunt("totmann_expired")` triggern soll?
- `omni_tx_clicked` Signal — alle Aufrufer (heute nur 1: `MainWindow:233`)?
- `radio.tune_on()` — alle Aufrufer und Antennen-Setzung davor?
- Existierende Aufrufer von `auto_hunt.enable()` und `auto_hunt.disable()` — wo, wie viele?
- `_pause_remaining` — wird das in der bestehenden `select_next`-Logik wirklich nicht mehr gebraucht?

## Dokumentations-Pflichten nach Implementierung

- `HISTORY.md`: ausfuehrlicher v0.75-Eintrag mit Workflow-Reflexion (V1→V2→V3-DeepSeek-Findings dokumentieren).
- `CLAUDE.md`: Header (Version + Test-Count: 446 → 458), Auto-Hunt-Sektion in Bekannte-Fallen.
- **NICHT** in README oder oeffentlicher GitHub-Doku — Easter-Egg bleibt versteckt.
