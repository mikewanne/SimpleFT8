# V1 — Auto-Hunt-Modus fuer SimpleFT8

## DeepSeek-Rolle (vor V2 voranstellen!)

Du bist Senior Python-Entwickler spezialisiert auf Amateurfunk-Software und PySide6-Applikationen (NICHT PyQt5 — wir nutzen PySide6, API-Unterschiede beachten: `Signal` statt `pyqtSignal`, `Slot` statt `pyqtSlot`). Deine einzige Aufgabe ist es, diesen Prompt zu kritisieren — NICHT das Problem zu loesen. Erstelle eine strukturierte Liste mit Luecken, fehlenden Informationen, Unklarheiten, Widerspruechen, Verbesserungsvorschlaegen und offenen Fragen. Bedenke: SimpleFT8 ist ein Hobby-Projekt, kein kommerzielles Produkt — Overengineering ist selbst ein Fehler den du benennen sollst.

---

## Ziel

Erweiterung der existierenden `core/auto_hunt.py` um einen zeitbeschraenkten Auto-Hunt-Modus, der CQ-Rufer auf dem aktiven Band automatisch identifiziert und anruft. Der Modus laeuft fest 10 Minuten, ist von Maus/Tastatur entkoppelt (Bot-Tarn-Schutz), nutzt Slot-Affinitaet (kein wildes Even/Odd-Springen) und bleibt strikt auf einem Band.

Aktivierung erfolgt verdeckt via Klick auf die Versionsnummer (Easter-Egg, gemeinsam mit OMNI CQ). Der Modus ist nicht in der oeffentlichen Doku erwaehnt.

## Akzeptanzkriterien

1. **3-Button-Layout im QSO-Bereich** wird nach Klick auf Versionsnummer eingeblendet:
   `[ CQ RUFEN ]  [ OMNI CQ ]  [ AUTO HUNT ]` — alle gleich breit, mutually exclusive (`QButtonGroup.setExclusive(True)`).
2. **Idle-State:** alle drei Buttons + TUNE-Button klickbar.
3. **Aktiver Modus:** gewaehlter Button rot/aktiv, andere zwei + TUNE disabled.
4. **AUTO HUNT-Button-State-Machine:**
   - Idle: Text `"AUTO HUNT"`, klickbar.
   - Aktiv: Text `"AUTO HUNT — 7:42"` (Live-Countdown), Klick = HALT.
   - Cooldown nach Auto-Stop: Text `"AUTO HUNT (5)"` `(4)` `(3)` ..., disabled.
   - Wieder Idle nach 5 Sekunden: Text `"AUTO HUNT"`, klickbar.
5. **10-Min-Hard-Stop:** Auto-Hunt-Timer laeuft fest 10 Minuten ab Start. Maus/Tastatur-Aktivitaet beeinflussen den Timer NICHT (entkoppelt vom Totmannschalter).
6. **Pflicht-Restart:** nach Auto-Stop muss User explizit erneut den Button klicken (kein Auto-Restart).
7. **5s Reflexions-Cooldown** nach Auto-Stop: Button disabled mit Countdown — verhindert Reflex-Klick.
8. **Slot-Affinitaet:** wenn `_last_tx_even` gesetzt, bevorzugt `select_next` Kandidaten mit gleichem `tx_even`. Fallback auf alle Kandidaten wenn keiner mit gleichem Slot vorhanden.
9. **Listen-Verwaltung (Hybrid):**
   - `_cooldown` (5 Min Fehlversuch-Sperre) wird bei Auto-Stop und Bandwechsel via `clear()` zurueckgesetzt.
   - `_qso_log.is_worked(call, band)` (24h-Block fuer erfolgreiche QSOs) bleibt unangetastet — verhindert Doppel-QSO.
10. **TX immer ueber ANT1:** zentraler `Encoder.transmit()`-Pfad ruft `radio.set_tx_antenna("ANT1")` defensiv vor jedem TX. **Auch fuer manuelle CQ-Anrufe + OMNI CQ + TUNE.**
11. **Multi-Band: NEIN** — Auto-Hunt arbeitet nur auf dem aktuell eingestellten Band.
12. **QSO mid-Stop:** wenn Timer mitten im laufenden QSO ablaeuft → QSO wird normal zu Ende gefuehrt (`F1`-Strategie). Aber: `select_next()` returnt strikt None nach Timer-Ablauf → kein neues QSO startet. Doppel-Active-Check vor Return.
13. **Race-Condition-Sicherung:** `select_next()` prueft `self.active` an zwei Stellen (Anfang + direkt vor Return).
14. **Anrufversuche pro Station:** 3 (existiert bereits via `_MAX_ATTEMPTS=3` in `core/auto_hunt.py:45`). Unveraendert.
15. **Wartezeit auf Antwort:** 2 Slots (= 30s FT8 / 15s FT4 / 7.6s FT2). Wird ueber bestehende QSO-State-Machine gesteuert (kein zusaetzlicher Code).
16. **`auto_hunt_stopped(reason)` Qt-Signal** — UI verbindet sich, schaltet Buttons in Cooldown-State. Reasons: `"timer_expired"`, `"manual_halt"`, `"band_change"`, `"totmann_expired"`.
17. **Easter-Egg pro Session, NICHT persistiert:** `MainWindow._easter_egg_active: bool = False`. Erster Versionsnummer-Klick → True (Buttons ein), zweiter Klick → False (Buttons aus, Auto-Hunt + OMNI CQ deaktiviert).
18. **Tests:** mind. 14 Unit-Tests (siehe Abschnitt Testbarkeit).

## Betroffene Module/Dateien

### Erweitern
- `core/auto_hunt.py` (255 Zeilen) — `AutoHunt`-Klasse: 6 neue Attribute, 4 neue Methoden, 1 neues Qt-Signal, `select_next()` minimal angepasst.
- `core/encoder.py:126` (`Encoder.transmit()`) — defensives `radio.set_tx_antenna("ANT1")` vor jedem TX.
- `ui/control_panel.py:760-773` — `_RadioCard` QSO-Bereich: 3-Button-Layout statt einzelnem `btn_cq`.
- `ui/control_panel.py:1053` — Versionsnummer-Klick: jetzt nicht mehr `omni_tx_clicked` sondern `easter_egg_toggle_clicked` (umbenannt fuer Klarheit).
- `ui/main_window.py:514` (`_on_omni_tx_easter_egg`) — wird zu `_on_easter_egg_toggle`, schaltet Buttons ein/aus.
- `ui/mw_qso.py` — Auto-Hunt-Trigger pro Decode-Cycle (existiert teilweise schon).

### Lesen / Referenzieren
- `radio/base_radio.py:156-163` — `set_tx_antenna` Interface.
- `radio/flexradio.py:867` — `set_tx_antenna` Implementierung.
- `ui/mw_cycle.py:120-122` — `_tx_even`-Setzung pro Message.
- `core/qso_state.py` — QSO-State-Machine (verbleibt unangetastet, AutoHunt nutzt nur `qso_idle`-Property).

### Neu
- `tests/test_auto_hunt_extended.py` — 14 neue Tests (siehe unten).

## Randbedingungen

### Threading
- AutoHunt-Klasse laeuft im GUI-Thread (kein eigener Thread).
- `QTimer` (10-Min-Stopper, 5s-Cooldown, 1s-Countdown-Polling) sind alle im GUI-Thread.
- Decode-Cycle-Trigger laeuft via `decoder.cycle_decoded`-Signal (`Qt.QueuedConnection` aus Decoder-Thread → GUI-Thread).

### Persistence
- **Keine.** Easter-Egg-Active-State, AutoHunt-Active-State, Cooldown-Listen sind alle session-lokal.
- Beim App-Restart: alle Buttons im Idle-State, Easter-Egg deaktiviert.

### UI-Regeln
- Alle 3 Mode-Buttons + TUNE haben dasselbe disabled-Verhalten: bei aktivem Modus disabled, bei Cooldown disabled, sonst klickbar.
- Countdown-Update via UI-seitigem 1s-`QTimer` der `auto_hunt.seconds_remaining()` + `is_in_cooldown()` polled.

### Hardware-Grenzen — HOECHSTE PRIORITAET
- **ANT1 = TX-Antenne IMMER. ANT2 = NUR RX.** (siehe `CLAUDE.md` Hardware-Warnung)
- Defensives `radio.set_tx_antenna("ANT1")` in `Encoder.transmit()` ist Pflicht-Akzeptanzkriterium.
- TUNE-Button muss disabled sein wenn ein Mode-Button aktiv ist (TUNE wuerde Carrier rauspusten und ein laufendes Auto-Hunt-QSO stoeren).

### Bot-Tarn-Schutz
- Auto-Hunt-Timer ist UNABHAENGIG vom Totmannschalter. Maus/Tastatur reset ihn NICHT.
- Totmannschalter laeuft parallel als separater 15-Min-Timer (resettet von Maus/Tastatur). Beide loesen `stop_auto_hunt()` aus.
- Sich ueberschneidende Abschalt-Mechanismen = ethische Belt-and-suspenders.

## Nicht im Scope

- ❌ Multi-Band-Hopping (Contest-Feature, gegen SimpleFT8-Hobby-Funker-Philosophie)
- ❌ Adaptive Anrufversuche (z.B. SNR-abhaengige Versuche-Anzahl) — KISS-Verstoss, 3 fest reicht
- ❌ Konfigurierbare 10-Min-Dauer (fest, ethische Belt-and-suspenders)
- ❌ DX-spezifische Wartezeit (3 Slots fuer DX) — 2 Slots fuer alle reicht
- ❌ Persistente Worked-Stations-Liste ueber App-Restarts (`_qso_log` ist session-only, ausreichend)
- ❌ Konfigurierbare Antenne fuer TX (immer ANT1 wegen Hardware-Pflicht)
- ❌ Cross-Mode (FT8↔FT4) Auto-Wechsel
- ❌ "Auto-Hunt + OMNI CQ kombiniert" Hybridmodus (fuer Phase 2 nach Feldtest, jetzt strikt mutually exclusive)
- ❌ Oeffentliche Dokumentation (Easter-Egg bleibt versteckt, nicht in README oder GitHub-Beschreibung)

## Testbarkeit

`tests/test_auto_hunt_extended.py` (neu) — mind. 14 Tests:

1. `test_start_sets_active_and_starts_timer` — `start_auto_hunt(600)` setzt `active=True`, `_auto_hunt_timer` laeuft.
2. `test_select_next_returns_none_when_inactive` — `select_next` returnt None wenn `active=False`.
3. `test_slot_affinity_prefers_same_tx_even` — nach erstem `select_next` mit `tx_even=True` wird im naechsten Zyklus Kandidat mit `tx_even=True` bevorzugt.
4. `test_slot_affinity_fallback_when_no_match` — wenn kein Kandidat mit gleichem `tx_even` verfuegbar, wird ein anderer genommen.
5. `test_cooldown_blocks_recent_failure` — `on_qso_timeout(call)` schreibt Cooldown-Timestamp; `select_next` ueberspringt diese Station 5 Min lang.
6. `test_hard_reset_clears_cooldown_keeps_qso_log` — `stop_auto_hunt("timer_expired")` ruft `_cooldown.clear()` aber NICHT `_qso_log` reset.
7. `test_band_change_clears_cooldown` — `on_band_change` ruft `_cooldown.clear()`.
8. `test_timer_expiry_mid_qso_no_new_hunt` — Timer-Ablauf waehrend laufendem QSO: `active=False`, QSO laeuft weiter via QSO-State-Machine, `select_next` gibt None.
9. `test_double_active_check_in_select_next` — wenn `active` zwischen Anfang und Return von `select_next` auf False gesetzt wird, returnt es None (Boss-Korrektur Race-Condition).
10. `test_encoder_transmit_sets_ant1` — Mock auf `radio.set_tx_antenna`, prueft dass `Encoder.transmit()` ANT1 setzt vor jedem TX.
11. `test_button_state_machine_idle_to_active_to_cooldown_to_idle` — UI-Test: Klick → Countdown → Auto-Stop nach 600s (gemockt) → Cooldown 5s → wieder Idle.
12. `test_manual_qso_start_blocks_select_next` — `on_manual_qso_start` setzt `_manual_override`, `select_next` returnt None.
13. `test_easter_egg_toggle_pro_session` — Klick auf Versionsnummer toggelt `_easter_egg_active`, NICHT in Settings persistiert.
14. `test_auto_hunt_stopped_signal_emits_with_reason` — bei jedem `stop_auto_hunt(reason)` feuert das Qt-Signal mit korrektem Reason-String.

Alle Tests laufen unter `QT_QPA_PLATFORM=offscreen` (siehe CLAUDE.md). Ziel: 446 → 460 Tests, alle gruen.

## Aufwandsschaetzung

- AutoHunt-Klassen-Erweiterung (6 Attr + 4 Methoden + Qt-Signal): 2-3 h
- UI-Integration (3 Buttons, Countdown-Timer, Easter-Egg-Toggle): 2-3 h
- Hardware-ANT1-Guard im Encoder: 30 min
- 14 Tests: 2-3 h
- HISTORY.md, CLAUDE.md, manuelle Verifikation: 1 h
- **Gesamt: ~1-1.5 Tage**

## Implementierungs-Reihenfolge (atomare Commits)

1. `feat(safety): ANT1-Guard in Encoder.transmit()` — defensives `set_tx_antenna("ANT1")` zentral
2. `feat(auto_hunt): start/stop_auto_hunt + Timer-Logik` — neue Methoden, Attribute, Qt-Signal
3. `feat(auto_hunt): Slot-Affinitaet + Race-Condition-Doppel-Check in select_next`
4. `feat(ui): 3-Button-Layout im QSO-Bereich (CQ/OMNI CQ/AUTO HUNT)` — mutually exclusive via QButtonGroup
5. `feat(ui): AUTO HUNT Countdown-Display + Cooldown-State-Machine`
6. `feat(ui): Easter-Egg-Toggle pro Session (umbenannt vom OMNI-TX-Spezial)`
7. `test: 14 neue Auto-Hunt-Tests`
8. `chore(release): v0.75 — Auto-Hunt-Modus`

Pro Commit: `pytest tests/ -q` muss gruen sein. Nach Commit 7: finaler DeepSeek-Codereview vor Commit 8.
