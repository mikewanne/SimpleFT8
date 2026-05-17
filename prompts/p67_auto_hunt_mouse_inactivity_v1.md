# P67 V1 — Auto-Hunt Mouse-Inactivity-Schicht (Variante C)

## Ziel
Auto-Hunt-Session zusaetzlich an eine kurze Maus-Inaktivitaet binden.
Aktuell wird Auto-Hunt nur durch zwei Mechanismen gestoppt:
1. 10-Min-Hard-Cap (`_auto_hunt_timer`, FEST, Maus-unabhaengig).
2. 15-Min-Operator-Presence-Timer (Maus reset) → `totmann_expired`.

Mike will **Variante C**: 10-Min-Hard-Cap bleibt unveraendert + eine
zweite, kuerzere Schicht „5 Min ohne Mausbewegung → Auto-Hunt stoppen".
Was zuerst greift, beendet die Session.

## Begruendung (Mike)
„Autohunt 10 timer fest UND maus bewegung (5 minuten nicht bewegt)".
Hintergrund: Operator-Presence (15 Min) ist die gesetzliche Mindest-
Pflicht fuer alle TX (CQ, QSO, Auto-Hunt). Auto-Hunt ist ein autonomer
TX-Modus — ein striktes 5-Min-Maus-Limit ist ein zusaetzlicher Schutz
gegen „Funker schlaeft ein", **ohne** den globalen 15-Min-Counter
anzufassen (CQ/QSO bleibt 15 Min). Belt-and-Suspenders ueber den
10-Min-Hard-Cap.

## Spec (Akzeptanzkriterien)

**AC1** — Konstante `_AUTO_HUNT_MOUSE_TIMEOUT_S = 300` (5 Min). Hartkodiert,
nicht in Settings (Mike-Spec: festes Limit, kein Konfigurations-Knopf).

**AC2** — `MainWindow` hat neuen Zustand `_auto_hunt_last_mouse_t: float`
(Default 0.0).
- Initialisierung in `_init_presence_timer()` (analog `_presence_last_mouse_pos`).

**AC3** — Mausbewegung aktualisiert `_auto_hunt_last_mouse_t`:
- In `_poll_mouse_activity` (500 ms-Polling) wird `_auto_hunt_last_mouse_t =
  time.monotonic()` gesetzt, sobald die Cursor-Position sich aendert.
- Genau dort wo `_reset_presence()` heute gerufen wird (eine Stelle,
  kein Drift).

**AC4** — Bei jedem User-Start von Auto-Hunt wird `_auto_hunt_last_mouse_t =
time.monotonic()` als Anker gesetzt (verhindert Sofort-Stop wenn der
Polling-Tick zufaellig vor der ersten Maus-Bewegung kam).
- Im Toggle-Handler `_on_auto_hunt_toggled(checked=True)` direkt vor
  `_auto_hunt.start_auto_hunt(600)`.

**AC5** — Stop-Trigger:
- In `_on_auto_hunt_polling_tick()` (laeuft sekuendlich solange Session
  aktiv, existiert bereits): wenn `_auto_hunt.active` und
  `time.monotonic() - _auto_hunt_last_mouse_t > _AUTO_HUNT_MOUSE_TIMEOUT_S`
  → `self._auto_hunt.stop_auto_hunt("mouse_inactive_5min")`.
- Reihenfolge: Check VOR dem Text-Update (`setText(f"AUTO HUNT — ...")`),
  sonst flickert die Restzeit-Anzeige eine Sekunde nach Ablauf.

**AC6** — `core/auto_hunt.py:stop_auto_hunt` Docstring erweitern:
- Reasons-Liste: neuer Eintrag `mouse_inactive_5min — 5 Min ohne
  Mausbewegung`.
- Cleanup-Logik: `mouse_inactive_5min` faellt unter den DEFAULT-Branch
  (`_cooldown.clear()` + `_last_tx_even = None`). Begruendung: anders als
  `totmann_expired` (User kommt zurueck und Presence wird re-aktiviert) ist
  ein Re-Start aus mouse_inactive immer User-Klick (Pflicht-Restart wie
  bei `manual_halt`). Cooldowns sollen sauber zuruecksetzen.

**AC7** — Kein `_abort_active_tx()` bei `mouse_inactive_5min`:
- Analog `totmann_expired`/`band_change`: laufender TX-Slot darf zu Ende
  gefuehrt werden. 5-Min-Maus-Inaktivitaet ist „Funker weg", nicht
  „Notfall-HALT".
- Damit kein zusaetzlicher Aufruf von `self._abort_active_tx()` im
  Polling-Tick.

**AC8** — UI-Reflexion:
- Bestehender Slot `_on_auto_hunt_stopped(reason)` (5-Sek-Reflexions-
  Cooldown auf Button + Text-Reset) greift fuer JEDEN Reason inkl.
  `mouse_inactive_5min`. Keine Anpassung noetig.

**AC9** — Statusbar/Info-Pfad:
- `QsoPanel.add_info(...)` einen Eintrag „⏸ Auto-Hunt gestoppt — 5 Min
  ohne Mausbewegung. Maus bewegen + AUTO HUNT klicken zum Fortsetzen."
- In `_on_auto_hunt_stopped` bereits NICHT existent — daher in
  `_on_auto_hunt_polling_tick` direkt vor `stop_auto_hunt` einfuegen.

**AC10** — Print-Logging:
- Vor `stop_auto_hunt`: `print("[Auto-Hunt-UI] Stop — 5 Min Maus-
  Inaktivitaet")`.

**AC11** — Tests `tests/test_p67_mouse_inactivity.py`:
- T1: `_AUTO_HUNT_MOUSE_TIMEOUT_S` Konstante existiert und = 300.
- T2: `_init_presence_timer` initialisiert `_auto_hunt_last_mouse_t = 0.0`.
- T3: `_poll_mouse_activity` setzt `_auto_hunt_last_mouse_t` bei Mausbewegung.
- T4: `_on_auto_hunt_toggled(True)` setzt `_auto_hunt_last_mouse_t` auf monotonic().
- T5: `_on_auto_hunt_polling_tick` ruft `stop_auto_hunt("mouse_inactive_5min")`
  wenn delta > 300 und active=True.
- T6: `_on_auto_hunt_polling_tick` ruft NICHT stop wenn delta = 299 (Grenz-Test).
- T7: `_on_auto_hunt_polling_tick` ruft NICHT stop wenn `active=False`.
- T8: `stop_auto_hunt("mouse_inactive_5min")` clear()-t `_cooldown` und
  setzt `_last_tx_even = None` (DEFAULT-Branch).
- T9: `_on_auto_hunt_polling_tick` ruft NICHT `_abort_active_tx` bei
  Maus-Stop.
- T10: Reason-Liste in Docstring enthaelt `mouse_inactive_5min`.

**AC12** — Hardware-Pflicht (CLAUDE.md): Vor `stop_auto_hunt` darf NIE
`set_tx_antenna` aufgerufen werden, kein TX-Pfad neu gestartet werden.
Code-Pfad ist nur Lese-Logik + Signal-Emit → automatisch erfuellt, aber
T9 verifiziert explizit dass `_abort_active_tx` NICHT gerufen wird (kein
versehentliches Anpacken der Antennen-Logik).

## Aus Scope
- Settings-Toggle fuer Maus-Timeout (Mike: festes Limit).
- OMNI-CQ Maus-Inaktivitaet (separate Diskussion, OMNI ist passiv und
  weniger autonom als Auto-Hunt).
- Presence-Timer (15 Min) bleibt unveraendert — nur die zusaetzliche
  5-Min-Auto-Hunt-spezifische Schicht.
- Aktive QSOs werden NICHT abgebrochen — sie laufen bei Maus-Inaktivitaet
  zu Ende (analog `totmann_expired`).

## Dateien
- `ui/main_window.py` — Konstante + Init + Polling-Tick + Toggle-Anker +
  `_poll_mouse_activity`.
- `core/auto_hunt.py` — Docstring stop_auto_hunt.
- `tests/test_p67_mouse_inactivity.py` — neu, 10 Tests.

## Field-Test (Mike, ohne Radio teilweise machbar)
- F1: Auto-Hunt starten, 5 Min Maus nicht bewegen → Button-Stop +
  Info-Zeile + 5-Sek-Reflexions-Cooldown.
- F2: Auto-Hunt starten, alle 4:30 Min kurz Maus bewegen → laeuft bis
  10-Min-Hard-Cap durch → Reason "timer_expired".
- F3: Auto-Hunt starten, 4 Min Maus still, dann bewegen, dann 4 Min Maus
  still → laeuft weiter (Reset funktioniert).
- F4: Bei aktivem QSO 5 Min Maus still → Auto-Hunt stoppt, laufendes
  QSO geht zu Ende (kein Abbruch). (mit Radio)
- F5: Start, sofort 5+ Min Maus still → exakt 1 Stop bei 5:00, kein Race.
