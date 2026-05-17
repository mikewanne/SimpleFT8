# P67 V3 — Auto-Hunt Mouse-Inactivity-Schicht (final, post-R1)

## R1-Entscheidungen
- **F1 ORANGE:** Konstante hartkodiert in `main_window.py` (AC1 unverändert).
- **F2 ORANGE:** Test-Namen-Korrektur — uebernommen in AC11 (siehe V2).
- **F3 GELB:** Konstante umbenennen auf `_AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S`
  — **angenommen** (selbsterklärend, KISS verletzt nicht).
- **F4 GELB:** Helper `_update_auto_hunt_mouse_t()` — **abgelehnt**, 1-Zeiler-
  Inline in `_poll_mouse_activity` ist sauberer (KISS).
- R1-Pflicht-Frage 5 (UI-Text): „AUTO HUNT-Taste druecken zum Fortsetzen"
  — **angenommen**, klarer.
- R1-Pflicht-Frage 7 (Test-Coverage): +3 Tests (T11 Mehrfach-Reset, T12
  Race timer+mouse, T13 Reihenfolge Anker→Polling) — **angenommen**.

## Akzeptanzkriterien V3

**AC1** — Konstante `_AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300` (5 Min)
in `ui/main_window.py`, direkt nach den Imports, vor der Klasse oder
oben in `MainWindow` als Klassenattribut nahe `_PRESENCE_TIMEOUT = 900`.

**AC2** — State `self._auto_hunt_last_mouse_t: float = 0.0` initialisiert
in `_init_presence_watchdog` (Z.449-469), nahe `_presence_last_mouse_pos`.

**AC3** — `_poll_mouse_activity` (Z.1336-1345) setzt bei jeder erkannten
Mausbewegung zusaetzlich `self._auto_hunt_last_mouse_t = time.monotonic()`
direkt nach `_reset_presence()`.

**AC4** — `_on_btn_auto_hunt_toggled` (Z.878 ff.):
- Vor `self._auto_hunt.start_auto_hunt(600)` (Z.897) den Anker setzen:
  `self._auto_hunt_last_mouse_t = time.monotonic()`.
- Reihenfolge: OMNI-Stop → **Anker-Set** → `start_auto_hunt(600)` →
  `polling_timer.start()` → initialer Polling-Tick → print.

**AC5** — `_on_auto_hunt_polling_tick` (Z.936-943) erweitern:
```python
def _on_auto_hunt_polling_tick(self):
    if not self._auto_hunt.active:
        self._auto_hunt_polling_timer.stop()
        return
    # P67 (v0.97.43): 5-Min-Maus-Inaktivitaet stoppt Auto-Hunt
    # (zweite, kuerzere Schicht ueber 10-Min-Hard-Cap).
    inactivity = time.monotonic() - self._auto_hunt_last_mouse_t
    if inactivity > self._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S:
        self.qso_panel.add_info(
            "⏸ Auto-Hunt gestoppt — 5 Minuten ohne Mausbewegung. "
            "Maus bewegen und AUTO HUNT-Taste druecken zum Fortsetzen."
        )
        print("[Auto-Hunt-UI] Stop — 5 Min Maus-Inaktivitaet")
        self._auto_hunt.stop_auto_hunt("mouse_inactive_5min")
        return
    sec = self._auto_hunt.seconds_remaining()
    m, s = divmod(sec, 60)
    self.control_panel.btn_auto_hunt.setText(f"AUTO HUNT — {m}:{s:02d}")
```

**AC6** — `core/auto_hunt.py:stop_auto_hunt` Docstring erweitern:
```
mouse_inactive_5min — 5 Min ohne Mausbewegung (P67)
```
Cleanup-Logik: `mouse_inactive_5min` faellt in DEFAULT-Branch (= NICHT
`totmann_expired`), also `_cooldown.clear()` + `_last_tx_even = None`.
Begruendung: Re-Start ist immer User-Klick (analog manual_halt).

**AC7** — Kein `_abort_active_tx()` bei mouse_inactive_5min (laufender
TX/QSO darf zu Ende, analog totmann_expired/band_change).

**AC8** — UI-Reflexion via `_on_auto_hunt_stopped(reason)` greift fuer
JEDEN Reason → keine Anpassung.

**AC9** — Tests `tests/test_p67_mouse_inactivity.py` (13 Tests):
- **T1**: Konstante `_AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S` == 300.
- **T2**: `_init_presence_watchdog` initialisiert `_auto_hunt_last_mouse_t = 0.0`.
- **T3**: `_poll_mouse_activity` setzt `_auto_hunt_last_mouse_t = monotonic()`
  wenn Cursor-Position sich aendert (per `QCursor.pos`-Mock).
- **T4**: `_on_btn_auto_hunt_toggled(checked=True)` setzt
  `_auto_hunt_last_mouse_t = monotonic()` VOR `start_auto_hunt(600)`.
- **T5**: `_on_auto_hunt_polling_tick` ruft `stop_auto_hunt("mouse_inactive_5min")`
  wenn `monotonic() - _auto_hunt_last_mouse_t > 300` und `active=True`.
- **T6**: `_on_auto_hunt_polling_tick` ruft NICHT stop wenn delta=299
  (Grenz-Test).
- **T7**: `_on_auto_hunt_polling_tick` ruft NICHT stop wenn `active=False`
  (Pre-Guard greift).
- **T8**: `stop_auto_hunt("mouse_inactive_5min")` clear()-t `_cooldown` und
  setzt `_last_tx_even = None` (DEFAULT-Branch, NICHT totmann-Branch).
- **T9**: `_on_auto_hunt_polling_tick` ruft NICHT `_abort_active_tx` bei
  Maus-Stop (kein TX-Abbruch).
- **T10**: `stop_auto_hunt` Docstring enthaelt `mouse_inactive_5min`.
- **T11** (NEU R1-S7): Mehrfach-Reset — Mausbewegung nach 4 Min, dann
  weitere 4 Min Ruhe → kein Stop, weil Anker aktualisiert wurde.
- **T12** (NEU R1-S7): Sim. Race timer_expired+mouse_inactive — beide
  Bedingungen gleichzeitig erfuellt: erster Tick gewinnt (mouse_inactive
  wird VOR Text-Update geprueft, also stop kommt mit mouse_inactive_5min).
- **T13** (NEU R1-S7): Reihenfolge im Toggle-Handler — Anker MUSS vor
  `start_auto_hunt(600)` gesetzt sein (via call_args_list-Inspection).

**AC10** — Hardware-Pflicht: Stop-Pfad ruft KEIN `set_tx_antenna`.
Verifiziert durch Code-Inspektion + T9 (kein TX-Anpacken).

## Dateien
- `ui/main_window.py` — Konstante + Init + Polling-Tick + Toggle-Anker +
  `_poll_mouse_activity`.
- `core/auto_hunt.py` — Docstring stop_auto_hunt.
- `tests/test_p67_mouse_inactivity.py` — neu, 13 Tests.

## Atomare Commits
- **C1**: Backup `Appsicherungen/2026-05-16_v0.97.42_vor_p67/`.
- **C2**: `core/auto_hunt.py` — Docstring stop_auto_hunt erweitert.
- **C3**: `ui/main_window.py` — Konstante + Init-State.
- **C4**: `ui/main_window.py` — `_poll_mouse_activity` Anker-Update.
- **C5**: `ui/main_window.py` — `_on_btn_auto_hunt_toggled` Anker-Set.
- **C6**: `ui/main_window.py` — `_on_auto_hunt_polling_tick` 5-Min-Check.
- **C7**: `tests/test_p67_mouse_inactivity.py` — 13 Tests neu.
- **C8**: `main.py` APP_VERSION 0.97.42 → 0.97.43.
- **C9**: HISTORY+HANDOFF+CLAUDE-Header + Memory.

## Field-Test (Mike, ohne Radio teilweise machbar)
- **F1**: Auto-Hunt starten, 5 Min Maus nicht bewegen → Button-Stop +
  Info-Zeile + 5-Sek-Reflexions-Cooldown.
- **F2**: Auto-Hunt starten, alle 4:30 Min kurz Maus bewegen → laeuft bis
  10-Min-Hard-Cap durch → Reason "timer_expired".
- **F3**: Auto-Hunt starten, 4 Min Maus still, dann bewegen, dann 4 Min Maus
  still → laeuft weiter (Reset funktioniert).
- **F4**: Bei aktivem QSO 5 Min Maus still → Auto-Hunt stoppt, laufendes
  QSO geht zu Ende (kein Abbruch). [Radio noetig]
- **F5**: Start, sofort 5+ Min Maus still → exakt 1 Stop bei 5:00–5:01,
  kein Race.

## R1-V4-pro Bilanz
- 4 Findings, 0 Halluzinationen, alle bearbeitet/begruendet.
- V4-pro 18-Cycle-Bilanz weiterhin 100% verifizierbar.
