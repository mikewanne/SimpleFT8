# P3.OMNI-PATTERN-FIX-2 — V3 Compact-fest

**Datum:** 2026-05-09
**Vorgaenger:** V1 → V2 (15 Lessons) → R1 („V2 ist bereit für die
Umsetzung", 0 KP, alle Lessons bestätigt)
**Stand:** V3 — Mike-Freigabe ausstehend, dann Compact #5 → Code

---

## 0. Compact-Brief

Mike-Field-Test v0.95.24, 09.05.2026 11:55-12:00 UTC zeigt 4 Probleme:

1. **Pretrigger zu spät** — GUI-Tick-Latency (Decoder blockiert
   GUI-Thread) → Tick kommt erst bei `cycle_pos=14.89s` rein →
   `silence_secs < 0.1` → overshoot=1.19 → v0.80 Drift-Schutz schiebt
   2 Slots → Pattern verschoben.
2. **Button-Label statisch** — „OMNI CQ" zeigt nicht ob aktiv. Mike
   klickt mehrfach aus Unsicherheit → permanent `manual_halt`.
3. **(verworfen, V2 L3)** — User-Start hat KEIN Drift-Problem:
   Encoder wählt `next_boundary` mit `silence_secs > 14s`.
4. **RX-Slots stumm** — Mike sieht im QSO-Panel keine Lebenszeichen
   in 3/5 RX-Slots.

**Loesung (R1-bestaetigt):**
1. **QTimer.singleShot mit Qt.PreciseTimer** in `_on_cycle_start`
   geplant — unabhängig von Tick-Latency.
2. **Cycle-Tick-Pretrigger als Fallback** bei `dur - 0.5s` —
   Defense-in-Depth.
3. **Button-Label dynamisch** via `update_omni_tx`.
4. **`add_listening` in qso_panel** für RX-Slot-Anzeige.

**Atomare Commits:** 3 (Timer+Fallback / Label / Listening+Doku).

---

## 1. R1-Bewertung

| R1-Finding | Status | V3-Aktion |
|---|---|---|
| L1-L15 alle bestätigt | ✅ | unverändert übernehmen |
| L1-L2 Mathematik dokumentieren | ✅ ACK | Kommentar in `_on_cycle_start` |
| `Qt.PreciseTimer` Import explizit | ✅ ACK | `from PySide6.QtCore import Slot, QTimer, Qt` |
| Mock-Strategie Tests | ✅ ACK | übernehmen |
| closeEvent-Stop nicht kritisch | ✅ ACK | nicht implementieren (KISS) |
| Empfehlung Smoke-Tests pro Commit | ✅ ACK | nach jedem Commit `pytest -q` |

---

## 2. Code-Aenderungen (Final)

### 2.1 `ui/main_window.py` — QTimer Init + Stop-Connect (Commit 1)

**`__init__` ergaenzen** (in `_init_diversity_state` Block bei
`_omni_pretriggered`-Init):

```python
# P3.OMNI-PATTERN-FIX-2 (v0.95.25): QTimer für Mid-Cycle-Pretrigger.
# Statt cycle_tick (das durch Decoder-Blocking um >1s verzögert sein
# kann) nutzen wir QTimer.singleShot mit Qt.PreciseTimer im GUI-Thread —
# typisch 0-50ms Drift gegen 0-1500ms bei Signal-Queue.
# Restart-Semantik: start() nach start() ersetzt alten Timeout.
# Stop-Reason-zentral: omni_stopped → _on_omni_stopped → timer.stop().
from PySide6.QtCore import QTimer, Qt
self._omni_pretrigger_timer = QTimer(self)
self._omni_pretrigger_timer.setSingleShot(True)
self._omni_pretrigger_timer.setTimerType(Qt.PreciseTimer)
self._omni_pretrigger_timer.timeout.connect(
    self._on_omni_pretrigger_fire)
```

**`_on_omni_pretrigger_fire` NEU** als Methode auf MainWindow
(delegiert an `_omni_pretrigger_check_direct` in mw_cycle):

```python
@Slot()
def _on_omni_pretrigger_fire(self):
    """QTimer-getriggerter Pretrigger — exact zur Schwelle.

    Ruft die gleiche Logik wie der cycle_tick-Fallback, aber
    GARANTIERT zur Soll-Zeit (cycle_pos ≈ dur - 1.3s).
    """
    self._omni_pretrigger_fire_impl()
```

**`_on_omni_stopped` ergaenzen** (vor `update_omni_tx`):
```python
def _on_omni_stopped(self, reason: str):
    # ... bestehender Code (stop_cq, _was_cq=False, etc.)
    # P3.OMNI-PATTERN-FIX-2: pending QTimer cancelen
    self._omni_pretrigger_timer.stop()
    # bestehender Reset des _omni_pretriggered-Flags bleibt
    self._omni_pretriggered = False
    # ... update_omni_tx, _update_statusbar
```

### 2.2 `ui/mw_cycle.py` — QTimer-Start in `_on_cycle_start` (Commit 1)

```python
@Slot(int, bool)
def _on_cycle_start(self, cycle_num: int, is_even: bool):
    # P2.OMNI-PATTERN-FIX (v0.95.24): Pretrigger-Flag fuer naechsten
    # Cycle reset.
    self._omni_pretriggered = False

    # P3.OMNI-PATTERN-FIX-2 (v0.95.25): QTimer-basierter Pretrigger.
    # Mathematik (V2 L2): Pretrigger soll bei cycle_pos = dur - 1.3s
    # feuern. Encoder berechnet sleep_dur = next_boundary + (-0.8) -
    # 0.5 - now. Bei cycle_pos = dur - 1.3 ist sleep_dur = 0 — genau
    # an der Sicherheitsgrenze. Sicheres Fenster: [dur-1.3, dur-0.8].
    # QTimer mit Qt.PreciseTimer trifft das ~50ms genau.
    if self._omni_tx.active and not self._omni_tx.is_paused():
        delay_ms = int((self.timer.cycle_duration -
                        _OMNI_PRETRIGGER_OFFSET_S) * 1000)
        self._omni_pretrigger_timer.start(delay_ms)
    # else: Timer bleibt gestoppt (oder wurde durch _on_omni_stopped
    # bereits gestoppt — start() ohne aktiv ware harmlos aber
    # unnoetig)

    # ── Anzeige zurücksetzen wenn kein TX ──
    if not self.encoder.is_transmitting:
        self.control_panel.update_tx_peak(0.0)
    # ... (Rest unverändert)

def _omni_pretrigger_fire_impl(self):
    """Pretrigger-Logik — gemeinsam für QTimer-Pfad UND Cycle-Tick-
    Fallback. Idempotent über _omni_pretriggered-Flag.
    """
    if self._omni_pretriggered:
        return
    if not self._omni_tx.active or self._omni_tx.is_paused():
        return
    if not self.qso_sm.cq_mode:
        return
    if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT,
                                  QSOState.CQ_CALLING):
        return
    self._omni_pretriggered = True
    next_idx, next_block, target_even, is_tx = self._omni_tx.peek_next()
    if not is_tx:
        return  # RX-Slot
    self.encoder.tx_even = target_even
    self.qso_sm._was_pretriggered = True
    self.qso_sm._send_cq()
    print(f"[OMNI-Pretrigger] Pos {next_idx} Block {next_block} "
          f"target_even={target_even} (QTimer)")
```

**Cycle-Tick-Fallback** (`_omni_pretrigger_check`):
```python
def _omni_pretrigger_check(self, sic: float, dur: float) -> None:
    """Cycle-Tick-Fallback. PRIMAER laeuft Pretrigger via QTimer
    (siehe _on_cycle_start). Dieser Pfad greift NUR wenn QTimer aus
    irgendeinem Grund nicht gefeuert hat (z.B. extreme Eventloop-
    Verzoegerung). Schwelle ist deshalb spaet (dur - 0.5s) — wenn
    QTimer aktiv waere, hat er bei dur - 1.3s bereits gefeuert +
    _omni_pretriggered=True gesetzt → return.
    """
    if self._omni_pretriggered:
        return
    if not self._omni_tx.active or self._omni_tx.is_paused():
        return
    if not self.qso_sm.cq_mode:
        return
    if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT,
                                  QSOState.CQ_CALLING):
        return
    fallback_threshold = dur - 0.5  # Notfall-Schwelle (dur - 0.5)
    if sic < fallback_threshold:
        return
    print(f"[OMNI-Pretrigger-FALLBACK] cycle_pos={sic:.2f}s — "
          f"QTimer hat NICHT gefeuert!")
    self._omni_pretrigger_fire_impl()  # gleicher Code-Pfad
```

**`_on_cycle_tick` UNVERAENDERT** ruft `_omni_pretrigger_check` weiter
(jetzt nur noch Fallback). Die V2-`_omni_pretrigger_fire`-Naming wird
zu `_omni_pretrigger_fire_impl` (gemeinsam für beide Pfade).

### 2.3 `ui/control_panel.py` — Button-Label (Commit 2)

**`update_omni_tx` ergaenzen**:
```python
def update_omni_tx(self, active: bool) -> None:
    """Ω-Symbol ein-/ausblenden + Button-Text-Update."""
    self._omni_active = active
    self._omni_symbol.setVisible(active)
    color = "#222" if active else "#333"
    self._version_label.setStyleSheet(
        f"color: {color}; font-family: {_FONT}; font-size: 10px; "
        "border: none; background: transparent;"
    )
    # P3.OMNI-PATTERN-FIX-2 (v0.95.25): Button-Label mit Aktiv-Status
    # Mike-Wunsch 09.05.2026: ohne Status-Hinweis klickt er mehrfach
    # aus Unsicherheit → manual_halt-Spam.
    if hasattr(self, 'btn_omni_cq'):
        self.btn_omni_cq.setText(
            "OMNI CQ (aktiv)" if active else "OMNI CQ"
        )
```

`btn_omni_cq` Init bleibt mit Initial-Text „OMNI CQ" (inaktiv-Default).

### 2.4 `ui/qso_panel.py` — `add_listening` NEU (Commit 3)

**Neue Methode** nach `add_rx`:
```python
def add_listening(self, slot_start_ts: float, tx_even: bool):
    """OMNI RX-Slot-Anzeige (Mike-Wunsch v0.95.25).

    Lebenszeichen in stillen RX-Slots — Mike sieht dass App läuft
    auch wenn keine Stationen decodiert wurden. Aufgerufen aus
    mw_qso._on_send_message bei OMNI-RX-Slot-Skip.

    Format wie add_rx: 'HH:MM:SS [E/O] ←  Horche  …' in Grau (#666).
    """
    utc = time.strftime("%H:%M:%S", time.gmtime(slot_start_ts))
    tag = "[E]" if tx_even else "[O]"
    self._append_colored(f"{utc} {tag} ←  Horche  …", "#666666")
```

### 2.5 `ui/mw_qso.py` — `add_listening`-Aufruf (Commit 3)

**`_on_send_message` RX-Slot-Skip-Branch ergaenzen**:
```python
if message.startswith("CQ "):
    self._has_sent_cq = True
    if self._omni_tx.active:
        if getattr(self.qso_sm, '_was_pretriggered', False):
            # ... (bestehender Pretrigger-Bypass-Pfad)
        else:
            send_ok, target_even = self._omni_tx.should_tx()
            if not send_ok:
                self.qso_sm._omni_skip_state_change = True
                print(f"[OMNI-TX] RX-Slot → skip CQ "
                      f"({self._omni_tx.slot_label})")
                # P3.OMNI-PATTERN-FIX-2 (v0.95.25): RX-Slot-Anzeige
                now = time.time()
                slot_dur = self.timer.cycle_duration
                slot_start = now - (now % slot_dur)
                is_even = int(slot_start / slot_dur) % 2 == 0
                self.qso_panel.add_listening(slot_start, is_even)
                return
            # ... (Rest unverändert)
```

### 2.6 `main.py` — APP_VERSION (Commit 3)

```python
APP_VERSION = "0.95.25"
```

---

## 3. Akzeptanzkriterien (V3 — 15 ACs)

| AC | Beschreibung | Verifikation |
|---|---|---|
| AC1 | QTimer scheduled in `_on_cycle_start` mit `delay_ms = (dur - 1.3) * 1000` | T1 |
| AC2 | QTimer-Fire ruft `_omni_pretrigger_fire_impl` (peek_next + tx_even + _send_cq) | T2 |
| AC3 | Button-Text aktiv: „OMNI CQ (aktiv)" | T3 |
| AC4 | Button-Text inaktiv: „OMNI CQ" | T3 |
| AC5 | `update_omni_tx` setzt Text synchron mit Ω-Symbol | T3 |
| AC8 | RX-Slot-Skip ruft `qso_panel.add_listening(slot_start, tx_even)` | T6 |
| AC9 | `add_listening` Format: `HH:MM:SS [E/O] ←  Horche  …` Grau | T7 |
| AC10 | Cycle-Tick-Fallback bei `sic > dur - 0.5s` UND `_omni_pretriggered=False` | T8 |
| AC11 | `_on_omni_stopped` ruft `omni_pretrigger_timer.stop()` | T9 |
| AC12 | Field-Test: 10-Slot-Loop EXAKT wie erwartet | Mike |
| AC13 | Cycle-Tick-Pretrigger NICHT mehr beim normalen Ablauf (QTimer übernimmt) | T8 |
| AC14 | Mode-Wechsel cancelt QTimer (via `omni_stopped`) | T9 (mit reason) |
| AC15 | Band-Wechsel cancelt QTimer (via `omni_stopped`) | T9 (mit reason) |
| AC16 | RX-Mode-Wechsel cancelt QTimer | T9 (mit reason) |
| AC17 | Doppelter `_on_cycle_start` ersetzt pending QTimer (start() Restart-Semantik) | T10 |

**Verworfen aus V1:** AC6 (User-Start-Delay), AC7 (gleicher Grund) —
V2 L3.

---

## 4. Test-Strategie (V3 — 10 Tests in `test_p3_omni_pattern_fix2.py`)

| # | Test | AC | Strategie |
|---|---|---|---|
| T1 | `test_pretrigger_qtimer_scheduled_with_correct_delay` | AC1 | Mock `QTimer.start`, prüfe delay_ms |
| T2 | `test_pretrigger_fire_impl_calls_send_cq` | AC2 | Direkter Aufruf, `qso_sm.send_message`-Mock |
| T3 | `test_update_omni_tx_sets_button_text` | AC3-AC5 | `btn_omni_cq.text()` nach Aufruf prüfen |
| T6 | `test_rx_slot_skip_calls_add_listening` | AC8 | mw_qso `_on_send_message` mit OMNI active + RX-Slot, mock `qso_panel.add_listening` |
| T7 | `test_add_listening_format` | AC9 | qso_panel.add_listening + log_view.toPlainText() prüfen |
| T8 | `test_pretrigger_fallback_via_cycle_tick` | AC10/AC13 | `_omni_pretriggered=False`, sic=14.6, dur=15 → ruft fire_impl |
| T9 | `test_omni_stop_calls_timer_stop` | AC11/AC14-AC16 | Mock `timer.stop`, emit `omni_stopped("manual_halt"/"ft_mode_change"/"band_change")` → prüfe alle |
| T10 | `test_cycle_start_restarts_pending_timer` | AC17 | Mock `timer.start`, 2x `_on_cycle_start` → 2x start mit gleichem delay |
| T11 | `test_inactive_omni_does_not_start_timer` | AC1 | OMNI active=False → `timer.start` NICHT aufgerufen |
| T12 | `test_paused_omni_does_not_start_timer` | AC1 | OMNI paused → `timer.start` NICHT aufgerufen |

**Erwartet:** 1048 → 1058 (+10).

---

## 5. Risiken (V3)

| # | Risiko | Mitigation |
|---|---|---|
| R1 | QTimer-Drift > 50ms im worst case | Cycle-Tick-Fallback bei `dur - 0.5s` (T8) |
| R2 | QTimer.timeout-Connect-Leak bei Re-Connect | Single-Connect im `__init__` (NICHT in cycle_start) |
| R3 | Mode/Band/RX-Mode-Stop cancelt Timer NICHT | zentral via `omni_stopped`-Signal → `_on_omni_stopped` (T9) |
| R4 | App-Close mit pending Timer | Qt destroyed Timer auto, kein Risiko |
| R5 | `add_listening`-Spam bei langem OMNI | `_auto_trim_by_age(300)` greift |
| R6 | Field-Test deckt unbekannten Edge-Case auf | 10+ Slots OMNI-Loop Pflicht (V3 §6) |
| R7 | `add_listening` während QSO (paused OMNI) | mw_qso `_on_send_message` greift nur bei `CQ ` + RX-Slot — QSO-Pause sendet keine CQ-Messages |

---

## 6. Field-Test-Plan (V3, 7 Punkte)

Mike's Field-Test, vor Push:

1. **Activate Test:** OMNI-Toggle aktivieren bei Slot N.
   - Button-Text wechselt zu „OMNI CQ (aktiv)".
   - Erste TX im nächsten verfügbaren Slot.
   - QSO-Panel zeigt Sende-Zeile.
2. **5-Slot-Pattern Block 1:** Aktivieren so dass next_is_even=True.
   - Slot 0: Sende [E], Slot 1: Sende [O], Slot 2-4: 3x „Horche …".
3. **5-Slot-Pattern Block 2:** Aktivieren mit next_is_even=False.
   - Slot 0: Sende [O], Slot 1: Sende [E], Slot 2-4: 3x „Horche …".
4. **10-Slot-Loop (KRITISCH):** 2 volle Blocks, **EXAKTES Pattern
   ohne Drift** — Beweis dass Tick-Latency-Bug behoben ist.
5. **Toggle off:** Button-Text wechselt zu „OMNI CQ".
   QSO-Panel zeigt nichts mehr (kein Horche, kein Sende).
6. **HALT mid-OMNI:** alles gestoppt, Button → „OMNI CQ", kein
   Resume.
7. **Mode/Band-Wechsel:** OMNI stoppt automatisch, Button →
   „OMNI CQ", QTimer-pending wird gecancelt (Live-Log: kein
   späteres Pretrigger-Fire).

---

## 7. Atomare Commits (V3 — 3 Code + 1 Doku)

| # | Commit | Files | Tests | AC |
|---|---|---|---|---|
| 1 | QTimer-Pretrigger + Fallback | `ui/main_window.py` (Timer-Init+Stop+Fire-Slot), `ui/mw_cycle.py` (Timer-Start in cycle_start, Fire-Impl, Fallback-Schwelle), `tests/test_p3_omni_pattern_fix2.py` (T1, T2, T8, T10, T11, T12) | T1, T2, T8, T10-12 | AC1, AC2, AC10, AC11, AC13, AC17 |
| 2 | Button-Label dynamisch | `ui/control_panel.py` (update_omni_tx setText), Tests T3 | T3 | AC3-AC5 |
| 3 | RX-Slot Horche + Mode-Stop-Tests + APP_VERSION + Doku | `ui/qso_panel.py` (add_listening NEU), `ui/mw_qso.py` (Aufruf), `main.py` 0.95.24 → 0.95.25, Tests T6, T7, T9 | T6, T7, T9 | AC8, AC9, AC14-AC16 |
| 4 | Doku-Commit | HISTORY+HANDOFF+CLAUDE+Memory | — | — |

**Test-Count Erwartung:** 1048 → ~1058 (+10).

---

## 8. R1-Final-Befehl (nach Code)

```bash
cd "/Users/mikehammerer/Documents/KI N8N Projekte/FT8/SimpleFT8"
cat prompts/p3_omni_pattern_fix2_v3.md | ./venv/bin/python3 tools/deepseek_review.py \
  ui/main_window.py ui/mw_cycle.py ui/mw_qso.py \
  ui/qso_panel.py ui/control_panel.py \
  tests/test_p3_omni_pattern_fix2.py \
  > /tmp/r1_omni_pattern_fix2_final.txt
```

---

## 9. Naechste Schritte

1. **Mike-Freigabe V3** ⏳
2. **Compact #5** (vor Implementation, Kontext-Schoner)
3. **Implementation in 3 atomaren Commits:**
   - Commit 1: QTimer + Fallback (mw_cycle/main_window) + 6 Tests
   - Commit 2: Button-Label (control_panel) + 1 Test
   - Commit 3: RX-Slot Horche + Mode-Stop-Tests + APP_VERSION
4. **Doku-Commit** (HISTORY/HANDOFF/CLAUDE/Memory)
5. **Final-R1 Code-Review**
6. **Field-Test mit Mike** (10-Slot-Loop = Pattern-Beweis)
7. **Push pending** — v0.95.16-25 + P2-Tool + P3 zusammen wenn
   Field-Test positiv.

---

## 10. Compact-Schoner (für nach #5)

Bei Compact #5 sollte folgendes erhalten bleiben:
- V3 Plan (diese Datei) komplett
- V2 Lessons-Übersicht (`p3_omni_pattern_fix2_v2.md`)
- R1-Output (`/tmp/r1_omni_pattern_fix2.txt`) — Tokens 121197 too big,
  reicht ggf. als zusammengefasster Memory-Eintrag
- Code-Verifikations-Findings:
  - QTimer-Import: `from PySide6.QtCore import Slot, QTimer, Qt`
  - Encoder-Mathematik: `silence_secs = next_boundary - 1.3 - now`,
    sicheres Fenster `[dur-1.3, dur-0.8]`
  - Stop-Reasons via `omni_stopped`-Signal: manual_halt, ft_mode_change,
    band_change, rx_mode_change, totmann_expired, easter_egg_off, superseded
  - `_auto_trim_by_age(300)` in qso_panel begrenzt Spam
- Atomare-Commit-Reihenfolge (1 → 2 → 3 → Doku) + Smoke-Test pro Commit

---

## 11. Was der Final-R1 verifiziert (V3 §10)

R1-Pruefauftraege fuer Final-R1 nach Code:
- Q1: QTimer wird mit `Qt.PreciseTimer` initialisiert und timeout
  korrekt connected im `__init__`?
- Q2: `_on_cycle_start` startet Timer nur wenn OMNI aktiv + nicht
  paused?
- Q3: `_on_omni_stopped` cancelt Timer (für ALLE Stop-Reasons)?
- Q4: Cycle-Tick-Fallback feuert nur bei `_omni_pretriggered=False`?
- Q5: `update_omni_tx` setzt Button-Text korrekt für True/False?
- Q6: `add_listening`-Aufruf nur im OMNI-RX-Slot-Skip-Pfad
  (nicht bei klassischem CQ ohne OMNI)?
- Q7: Tests decken alle 15 ACs?
- Q8: Keine Regression bei P2.OMNI-PATTERN-FIX (1023→1048 Tests
  bleiben grün)?
