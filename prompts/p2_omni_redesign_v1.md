# P2.OMNI-REDESIGN — V1 Prompt

**Datum:** 2026-05-09
**Stand:** v0.95.22, Tests 1014 grün, Git-Tag `pre-omni-redesign` gesetzt
**Source of Truth:** `prompts/omni_redesign_notes.md` (Compact-fest)

---

## 1. Auftrag an DeepSeek (R1)

Du bist ein erfahrener Architektur-Reviewer für PySide6-State-Machines mit
Echtzeit-IO. Deine Aufgabe: **diesen Plan kritisieren und konkret verbessern**
(NICHT das Problem selbst lösen).

**Was Du prüfen sollst:**
1. Sind die Bug-Wurzeln korrekt diagnostiziert (Code-Pfade, Zeilen)?
2. Ist die geplante Architektur sauber, KISS-konform, Race-frei?
3. Gibt es Akzeptanzkriterien die fehlen oder mehrdeutig sind?
4. Sind die geplanten Test-Cases ausreichend (vor allem Block-Switch +
   Pause/Resume + State-Persistence)?
5. Welche Risiken / Folge-Bugs siehst Du, die der Plan nicht abdeckt?
6. Stimmt der „kein Slot verschwenden"-Algorithmus für Activate +
   post-QSO-Resume?

**Antwort-Format (analog letzter Reviews):**
- 🔴 BUG (Plan ist falsch / würde Bug einbauen)
- 🟠 SOLLTE (wichtige Verbesserung, vor V3 einarbeiten)
- 🟡 KÖNNTE (optional, KISS-Trade-off)
- ✅ ACK (Plan-Punkt explizit ok)

Pro Finding: Datei:Zeile, was zu ändern, warum, Risiko-Einschätzung.

---

## 2. Hintergrund / Bug-Kontext

**Symptom (Mike-Field-Test 09.05.2026):** Klick auf `btn_omni_cq` → CQ wird
auf Even gesendet → sofort kommt eine Antwort auf Odd. Hätte nicht passieren
dürfen, weil im OMNI-Pattern der Odd-Slot nach dem Even-CQ ein **zweiter
TX-CQ** sein soll (Pattern 1: `Even-TX, Odd-TX, Even-RX, Odd-RX, Even-RX`).

**Root Cause verifiziert** (`core/qso_state.py:164-178`):
```python
def _send_cq(self):
    if self._pending_reply is not None:
        self._process_cq_reply()
        return
    self._pending_reply = None
    msg = f"CQ {self.my_call} {self.my_grid}"
    self._dbg.log("TX", f"Sende: '{msg}'")
    self._set_state(QSOState.CQ_CALLING)   # Z.177 — State VOR emit
    self.send_message.emit(msg)             # Z.178
```

Wenn `_on_send_message` (mw_qso.py:299) den OMNI-Filter aktiviert hat und der
aktuelle Slot ein RX-Slot des Patterns ist (Z.312-317), returned der Listener
früh ohne `encoder.transmit()` aufzurufen → `tx_finished` feuert nie →
`on_message_sent()` wird nie aufgerufen → State bleibt in `CQ_CALLING` →
`on_cycle_end()` (Z.317-324) prüft `if self.state == QSOState.CQ_WAIT`
→ niemals true → `_send_cq()` wird nie wieder aufgerufen → **OMNI-Loop tot
nach 2 TX-Slots**.

**Mike-Beschluss:** Voller Refactor, kein Pflaster.

---

## 3. Mike's korrektes OMNI-Pattern

```
Block 1: Even-TX, Odd-TX, Even-RX, Odd-RX, Even-RX
Block 2: Odd-TX,  Even-TX, Odd-RX,  Even-RX, Odd-RX
```

**Block-Switch:** Automatisch wenn `_slot_index` von 4 → 0 rollt. Continuous:
Block 1 → Block 2 → Block 1 → Block 2 → ... — **OHNE 80-Zyklen-Zähler.**
Der `block_cycles=80`-Default in `core/omni_tx.py:108` war Überrest aus alter
Diversity-`OPERATE_CYCLES`-Logik (vor v0.93). Hat in OMNI nie hingehört. Raus.

**Vorteil 5+5:** symmetrische Verteilung der TX/RX-Even/Odd-Slots —
Block 1 sendet 1×Even+1×Odd, hört 2×Even+1×Odd; Block 2 spiegelt das.

---

## 4. „Kein Slot verschwenden"-Logik

### 4.1 Beim User-Klick (OMNI-Activate)
- Nächster Slot ist Even → start Block 1 (Pos 0=Even-TX) → erste TX direkt
- Nächster Slot ist Odd → start Block 2 (Pos 0=Odd-TX) → erste TX direkt

### 4.2 Nach QSO-Ende (während OMNI war aktiv vor QSO)
- Nächster freier Slot ist Even → start Block 1
- Nächster freier Slot ist Odd → start Block 2

→ Kein 15-s-Slot wird verschwendet — erste OMNI-TX läuft im allerersten
verfügbaren Slot.

---

## 5. 4-Sequencer-Architektur

| Sequencer | Trigger | Was tut er |
|---|---|---|
| **Plan A: Normal-CQ** | `btn_cq` aktiv | CQ + erste Antwort beantworten |
| **Plan B: OMNI-CQ** | `btn_omni_cq` aktiv | CQ alternierend Even/Odd nach 5er-Pattern |
| **Plan C: Auto-Hunt** | `btn_auto_hunt` aktiv | Stationen suchen + automatisch anrufen |
| **Plan D: Manual** | User klickt Station | Direkt anrufen |

**Gemeinsame Subroutine:** Report → RR73 → 73 (Courtesy) → Log.

**Wechsel zwischen Sequencern:**
- **Sofort** wenn KEIN QSO läuft
- **Pending** (nach QSO-Ende) wenn QSO läuft
- **Nur HALT** (mw_qso `_on_cancel`) unterbricht ein laufendes QSO

**Nach QSO-Ende kehrt Steuerung zum auslösenden Sequencer zurück:**
OMNI → wieder OMNI mit Block-Wahl per §4.2; Hunt → wieder Hunt; etc.

---

## 6. Code-Änderungen (geplant, kein Code geschrieben)

### 6.1 `core/qso_state.py` — Root Cause heilen (Option B, Mike-Entscheidung)

**Aktuell (`_send_cq()`, Z.164-178):**
```python
self._set_state(QSOState.CQ_CALLING)   # State VOR emit
self.send_message.emit(msg)
```

**Neu:**
```python
self.send_message.emit(msg)             # Listener entscheidet (OMNI-Filter)
# State erst NACH emit setzen — wenn Listener früh returned
# (RX-Slot), bleibt der bisherige State erhalten
self._set_state(QSOState.CQ_CALLING)
```

**Race-Check (verifiziert):** `_on_send_message` (mw_qso.py:299-336) greift
NICHT auf `qso_sm.state` zu — nur auf `_omni_tx.active`, `_omni_tx.should_tx()`,
`encoder.tx_even`, `encoder.transmit()`. Kein synchroner State-Listener →
Vertauschung sicher.

**Folge:** Wenn OMNI-RX-Slot → Listener returned früh → State bleibt
`CQ_WAIT` → `on_cycle_end()` triggert weiterhin → kein Loop-Tod mehr.

**KEIN `auto_cq_enabled`-Flag** (Option A verworfen) — eliminiert die
Folge-Komplexität in `_resume_cq_if_needed()`.

---

### 6.2 `core/omni_tx.py` — Vereinfachung

**Raus:**
- `block_cycles` Parameter + Default 80 (Konstruktor + Singleton)
- `_cycle_count` Attribut
- `_pending_switch` Mechanik (außer falls für QSO-Pause noch nötig — V2 prüfen)
- `qso_active`-Parameter aus `advance(...)` (Pause-Logik kommt von außen)

**Vereinfacht:**
```python
def advance(self):
    """Slot-Index inkrementieren, Block automatisch wechseln bei Rollover."""
    if not self._active:
        return
    new_idx = (self._slot_index + 1) % 5
    if new_idx == 0:  # Rollover → Block-Wechsel
        self._block = 2 if self._block == 1 else 1
        print(f"[OMNI-TX] Block-Wechsel → Block {self._block}")
    self._slot_index = new_idx
```

**Neue Methoden:**
```python
def pause(self):
    """QSO startet — slot_index + block einfrieren."""
    self._paused = True
    print(f"[OMNI-TX] paused @ slot={self._slot_index} block={self._block}")

def resume(self):
    """Nach QSO — Pause aufheben, Treiber rotiert weiter."""
    self._paused = False
    print(f"[OMNI-TX] resumed @ slot={self._slot_index} block={self._block}")

def start_with_parity_for_next_slot(self, next_is_even: bool):
    """„Kein Slot verschwenden"-Logik bei Activate ODER post-QSO-Resume.

    next_is_even=True  → Block 1 (Pos 0=Even-TX)
    next_is_even=False → Block 2 (Pos 0=Odd-TX)
    """
    self._block = 1 if next_is_even else 2
    self._slot_index = 0
    self._active = True
    self._paused = False
    print(f"[OMNI-TX] start Block {self._block} (next={'Even' if next_is_even else 'Odd'})")
```

`should_tx()` (Z.78-105) bleibt wie bisher — Mapping aus Pattern-Tabelle.

---

### 6.3 `ui/mw_cycle.py` — OMNI-Slot-Treiber **VOR** advance()

**R1-BUG-1 (1. Lauf, verifiziert):** `should_tx()` muss VOR `advance()`
aufgerufen werden, weil `advance()` `_slot_index` sofort inkrementiert →
nachgelagertes `should_tx()` würde nächsten Slot prüfen.

**Aktuell (`_on_cycle_start`, ~Z.575-592):**
```python
qso_sm.on_cycle_end()                           # Z.585
...
self._omni_tx.advance(qso_active=_in_qso)       # Z.592
```

**Neu:**
```python
qso_sm.on_cycle_end()
# OMNI-Treiber: NUR advance()-Aufruf; Pause/Resume kommt von außen
# (start_qso → _omni_tx.pause(); on_qso_complete → _omni_tx.resume())
if not self._omni_tx.is_paused():
    self._omni_tx.advance()
# Block-Switch passiert in advance() automatisch bei rollover (4→0)
```

**Wichtig:** Die `qso_active`-Bedingung wird durch `is_paused()` ersetzt.
Pause-Setzen passiert genau einmal beim QSO-Start (siehe §6.5).

---

### 6.4 `ui/main_window.py` — `_on_btn_omni_cq_toggled` (Z.680-712)

**Aktuell:** Pre-Block + `_omni_tx.enable()` + `qso_sm.start_cq()`.

**Neu:**
```python
@Slot(bool)
def _on_btn_omni_cq_toggled(self, checked: bool):
    if checked and not self._omni_tx.active:
        # Pre-Block bei aktivem QSO (unverändert)
        if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
            ...  # Statusbar + return (wie heute)
            return
        if self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("superseded")
        # „Kein Slot verschwenden": nächster Slot Even → Block 1, sonst Block 2
        next_is_even = not self.timer.is_even_cycle()  # next = Gegenteil von current
        self._omni_tx.start_with_parity_for_next_slot(next_is_even)
        self.qso_sm.start_cq()
        ...
```

**`_on_omni_stopped` (Z.714-738):** unverändert — stoppt CQ-Loop +
`_was_cq=False`, idempotent.

---

### 6.5 `ui/mw_qso.py` — QSO-Lifecycle-Hooks für OMNI-Pause

**`_on_station_clicked` + `_process_cq_reply` (alle Wege ins QSO):**
Wenn OMNI aktiv → `self._omni_tx.pause()` aufrufen, BEVOR `start_qso()`
aufgerufen wird. Damit friert OMNI seinen Slot-Index ein.

**`_on_qso_complete` + `_on_qso_confirmed` + `_on_qso_timeout`
(alle Wege aus QSO):**
Wenn OMNI vor QSO aktiv war (Flag `_omni_was_active_pre_qso` in MainWindow):
- Nach Cleanup: `next_is_even = not self.timer.is_even_cycle()`
- `self._omni_tx.start_with_parity_for_next_slot(next_is_even)` →
  resume mit korrekter Parität, kein Slot verschwendet
- `self.qso_sm.start_cq()` (CQ-Loop wieder anwerfen, falls `_resume_cq_if_needed`
  ihn nicht schon angeworfen hat — idempotent)

**Alternative (KISS):** statt eigenem Pre-QSO-Flag einfach `_omni_tx.active`
prüfen — wenn beim QSO-Start aktiv war, ist auch beim QSO-Ende noch aktiv
(stop nur durch HALT/Mode/Band-Wechsel, alle drei stoppen QSO auch).

**HALT-Pfad (`_on_cancel`):** unverändert — stoppt OMNI bereits (v0.95.22
P1.OMNI-START), kein Resume.

---

### 6.6 `ui/mw_qso.py` — `_on_send_message` OMNI-Filter

**Aktuell (Z.306-328):** OMNI-Filter ist drin, prüft `should_tx()` →
RX-Slot → return mit `calls_made -= 1`.

**Vereinfachung:** der `calls_made`-Decrement war Pflaster gegen Loop-Tod
(nun durch §6.1 Option-B-Fix obsolet). Trotzdem behalten als Defense-in-Depth
gegen `WAIT_REPORT`-Retry-Pfad. Logik bleibt — nur weniger relevant nach Fix.

**KEIN funktionaler Refactor hier** außer Doku-Kommentar.

---

## 7. Akzeptanzkriterien (10 ACs für Tests)

**AC1:** OMNI-Activate während Even-Slot läuft → Block 1 (Pos 0=Even-TX),
erster CQ geht im nächsten Even-Slot raus.

**AC2:** OMNI-Activate während Odd-Slot läuft → Block 2 (Pos 0=Odd-TX),
erster CQ geht im nächsten Odd-Slot raus.

**AC3:** Pattern-Verlauf 10 Slots (Block 1 → Block 2):
`E-TX, O-TX, E-RX, O-RX, E-RX, O-TX, E-TX, O-RX, E-RX, O-RX`.

**AC4:** Block-Switch automatisch nach jedem 5-Slot-Cycle (kein 80-Zähler).

**AC5:** QSO startet während OMNI Pos 2 → `_omni_tx.pause()` aufgerufen,
`_slot_index` und `_block` bleiben eingefroren bis QSO-Ende.

**AC6:** QSO endet auf Even-TX-Slot → next slot Odd → OMNI startet Block 2
(Odd-TX first), KEIN 15-s-Leerlauf.

**AC7:** QSO endet auf Odd-TX-Slot → next slot Even → OMNI startet Block 1
(Even-TX first).

**AC8:** HALT (mw_qso `_on_cancel`) während OMNI → OMNI gestoppt, CQ-Loop
gestoppt, `_was_cq=False`, btn_omni_cq off.

**AC9:** Mode-Wechsel (FT8→FT4) während OMNI → OMNI gestoppt
(`mode_change`-Reason).

**AC10:** Band-Wechsel während OMNI → OMNI gestoppt (`band_change`-Reason).

**AC11 (Root-Cause-Fix-Beweis):** OMNI aktiv, RX-Slot wird vom Filter
übersprungen → State bleibt CQ_WAIT (nicht CQ_CALLING) → nächster
`on_cycle_end()` triggert `_send_cq()` korrekt → Loop läuft endlos durch.

---

## 8. Test-Strategie

Neue Datei `tests/test_p2_omni_redesign.py` mit ~15 Tests:

**Block-Logik (5 Tests):**
- `test_block1_pattern_correct` — Pos 0..4 ergeben E-TX, O-TX, E-RX, O-RX, E-RX
- `test_block2_pattern_correct` — Pos 0..4 ergeben O-TX, E-TX, O-RX, E-RX, O-RX
- `test_block_switch_on_rollover` — slot_index 4→0 → Block-Toggle
- `test_no_block_cycles_counter` — kein `_cycle_count`, kein 80er-Trigger
- `test_advance_no_qso_active_param` — `advance()` ohne `qso_active` arg

**Activate / „Kein Slot verschwenden" (3 Tests):**
- `test_activate_next_even_starts_block1`
- `test_activate_next_odd_starts_block2`
- `test_activate_resets_slot_index_to_0`

**QSO-Pause/Resume (4 Tests):**
- `test_pause_freezes_slot_and_block`
- `test_resume_picks_block_by_next_slot_parity`
- `test_resume_after_even_tx_qso_starts_block2_for_odd_next`
- `test_resume_after_odd_tx_qso_starts_block1_for_even_next`

**Root-Cause-Fix (Option B) (3 Tests):**
- `test_send_cq_emits_before_state_change` — Listener kann State sehen,
  der noch CQ_WAIT/IDLE ist
- `test_omni_rx_slot_skips_state_stays_cq_wait` — kein CQ_CALLING-Hängen
- `test_omni_loop_runs_through_full_pattern` — 10+ Slots, State sauber

**Stop-Conditions (2 Tests):**
- `test_halt_stops_omni_and_cq`
- `test_mode_change_stops_omni`

---

## 9. Anti-Liste (was NICHT geschehen darf)

- ❌ Pflaster oder Quick-Fix
- ❌ Brüche im laufenden QSO (nur HALT darf unterbrechen)
- ❌ Mehrere Code-Pfade die das gleiche tun (KISS, klare Trennung der 4
  Sequencer mit shared subroutine)
- ❌ Slot-Verschwendung (15-s-Leerlauf bei Activate oder post-QSO)
- ❌ Beibehalten von `block_cycles=80` (alter Diversity-Überrest)
- ❌ `auto_cq_enabled`-Flag (Option A — Mike hat verworfen)
- ❌ Encoder/Decoder-Schnittstellen anfassen
- ❌ Hardware-Logik anfassen (ANT1/ANT2 unverändert, Diversity-Pattern
  unangetastet)

---

## 10. Was NICHT im Scope ist

- Auto-Hunt-Refactor (separates Plan-File falls nötig)
- Decoder-/Encoder-Änderungen
- UI-Layout (btn_omni_cq-Position, etc.)
- Hardware-Antenna-Logik
- Statistik-Logging-Pfade

---

## 11. Files-Anhang an DeepSeek (alle vollständig!)

Lesson aus früheren Reviews (`feedback_deepseek_partial_files_hallucination.md`):
R1 halluziniert Lücken bei selektiver File-Auswahl. **Alle Files vollständig
anhängen, nicht Auszüge.**

- `core/omni_tx.py` (~250 Zeilen, komplett)
- `core/qso_state.py` (~700 Zeilen, komplett)
- `ui/main_window.py` (~1500 Zeilen, komplett)
- `ui/mw_qso.py` (~800 Zeilen, komplett)
- `ui/mw_cycle.py` (~600 Zeilen, komplett)
- `core/timing.py` (~80 Zeilen, für `is_even_cycle`-Verifikation)

---

## 12. Erwartete R1-Findings-Klassen

Für jeden Punkt: erwartet R1 abzuhaken oder zu kritisieren?

| Plan-Punkt | Erwartet |
|---|---|
| §6.1 Race-Check Option B | ACK (Race-Check schon in V1 erfolgt) |
| §6.2 `block_cycles` raus | ACK |
| §6.3 should_tx vor advance | ACK (war R1-1.-Lauf-BUG-1, schon eingearbeitet) |
| §6.4 Activate-Parität | mögl. SOLLTE — Edge-Case wenn Klick GENAU am Slot-Boundary |
| §6.5 Pause/Resume in mw_qso | mögl. SOLLTE — alle QSO-Entry/Exit-Pfade vollständig? |
| §7 ACs | mögl. SOLLTE — fehlt AC für Caller-Queue + OMNI? |
| §8 Tests | mögl. SOLLTE — fehlen Race-Tests synchroner Listener? |

---

## 13. Mike's Designentscheidung (nicht verhandelbar)

- **Option B** statt Option A (Root Cause heilen, kein Flag)
- **Block-Switch automatisch** (kein 80-Zähler)
- **„Kein Slot verschwenden"** bei Activate + post-QSO
- **4 Sequencer + 1 Shared QSO Subroutine**
- **Nur HALT** unterbricht laufende QSOs
- **OMNI bleibt Diversity-only** (mode-gekoppelt, sichtbar nur in Diversity)

R1 darf zu diesen Punkten Hinweise geben (Race, Edge-Cases), aber keine
alternative Architektur vorschlagen.

---

## 14. Anhang: Code-Auszüge zur Verifikation

### `core/omni_tx.py:78-126` (should_tx + advance, IST-Stand)

```python
def should_tx(self) -> tuple[bool, bool | None]:
    """5-Slot Pattern; gibt (sende_jetzt, target_even) zurück."""
    if not self._active:
        return (False, None)
    pat = self._PATTERN[self._block]   # 1 oder 2
    cell = pat[self._slot_index]        # 0..4
    return cell  # (bool, bool|None)

def advance(self, qso_active: bool = False) -> None:
    if not self._active or qso_active:
        return
    new_idx = (self._slot_index + 1) % 5
    self._cycle_count += 1            # ← raus
    if self._cycle_count >= self.block_cycles:  # ← raus
        self._block = 2 if self._block == 1 else 1
        self._cycle_count = 0
        print(f"[OMNI-TX] Block-Wechsel nach {self.block_cycles} Zyklen")
    self._slot_index = new_idx
```

### `core/qso_state.py:164-178` (_send_cq, IST-Stand mit Bug)

```python
def _send_cq(self):
    if self._pending_reply is not None:
        self._process_cq_reply()
        return
    self._pending_reply = None
    msg = f"CQ {self.my_call} {self.my_grid}"
    self._dbg.log("TX", f"Sende: '{msg}'")
    self._set_state(QSOState.CQ_CALLING)   # ← Bug: VOR emit
    self.send_message.emit(msg)
```

### `ui/mw_qso.py:299-336` (_on_send_message, OMNI-Filter)

```python
@Slot(str)
def _on_send_message(self, message: str):
    if not self.presence_can_tx():
        return
    if message.startswith("CQ "):
        self._has_sent_cq = True
        if self._omni_tx.active:
            send_ok, target_even = self._omni_tx.should_tx()
            if not send_ok:
                # RX-Slot: CQ NICHT senden
                if hasattr(self.qso_sm, 'qso'):
                    self.qso_sm.qso.calls_made = max(0, ...)
                return  # ← Listener returned früh, transmit() läuft NICHT
            if target_even is not None:
                self.encoder.tx_even = target_even
    if self.encoder.is_transmitting:
        self.encoder.abort()
    self.encoder.transmit(message)  # ← nur hier wird wirklich gesendet
```

### `ui/main_window.py:680-712` (_on_btn_omni_cq_toggled, IST-Stand)

```python
@Slot(bool)
def _on_btn_omni_cq_toggled(self, checked: bool):
    if checked and not self._omni_tx.active:
        if self.qso_sm.state not in (QSOState.IDLE, QSOState.CQ_WAIT):
            ...  # Pre-Block + return
            return
        if self._auto_hunt.active:
            self._auto_hunt.stop_auto_hunt("superseded")
        self._omni_tx.enable()       # ← ersetzen durch start_with_parity_for_next_slot
        self.qso_sm.start_cq()
        self.control_panel.update_omni_tx(True)
        ...
```

---

## 15. Nächste Schritte

1. R1-Review mit `tools/deepseek_review.py` (Direkt-API, R1-Default)
2. R1-Findings einarbeiten → V2 oder direkt V3
3. V3 mit Mike abstimmen (Compact-fest)
4. Compact #2
5. Implementation:
   - Atomare Commits: omni_tx.py refactor / qso_state.py Option B / mw_cycle.py /
     main_window.py + mw_qso.py / Tests / Doku
   - Tests grün halten (1014 → erwartete +15 = 1029)
6. Field-Test mit Mike (Akzeptanzkriterien §7 + funktional am FlexRadio)
