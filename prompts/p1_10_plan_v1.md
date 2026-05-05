# P1.10 Plan-V1 — Code-Diffs für Courtesy-73-Implementation

**Stand:** 2026-05-05, basierend auf Diagnose-V3 + Mike-Freigabe.
**Workflow-Phase:** Plan-V1 → Plan-V2 (Self-Review) → Plan-R1 → Plan-V3.
**Zielversion:** v0.95.3 → **v0.95.4**.
**Atomare Commits:** 1× Code+Tests + 1× Doku.

---

## 1. Übersicht der Änderungen

| # | Datei | Stelle | Art | Größe |
|---|---|---|---|---|
| D1 | `core/qso_state.py` | Z.49-62 | Enum-Erweiterung | +1 Zeile |
| D2 | `core/qso_state.py` | Z.70-82 | Dataclass-Erweiterung | +1 Zeile |
| D3 | `core/qso_state.py` | Z.430-436 | on_message_sent neuer Branch | +6 Zeilen |
| D4 | `core/qso_state.py` | Z.582-586 | WAIT_73-Hauptlogik | -3 / +18 Zeilen |
| D5 | `ui/mw_qso.py` | Z.200-204 | is_tx-Set | +1 Eintrag |
| D6 | `main.py` | APP_VERSION | Version-Bump | -1 / +1 Zeile |
| D7 | `tests/test_p1_10_courtesy_73.py` | NEU | 11 Tests | +200 Zeilen |
| **Gesamt** | | | | **~225 Zeilen, 4 Files modifiziert + 1 neu** |

## 2. Code-Diffs

### D1 — `core/qso_state.py:49-62` Enum-Erweiterung

**Vorher:**
```python
class QSOState(Enum):
    IDLE = auto()
    # --- CQ-Modus ---
    CQ_CALLING = auto()     # Sende "CQ DA1MHH JO31"
    CQ_WAIT = auto()        # Warte auf Anrufer
    # --- QSO-Sequenz (Hunt + CQ) ---
    TX_CALL = auto()        # Sende "DA1MHH DX5ABC JO31" (Hunt)
    WAIT_REPORT = auto()    # Warte auf Rapport
    TX_REPORT = auto()      # Sende Rapport
    WAIT_RR73 = auto()      # Warte auf RR73
    TX_RR73 = auto()        # Sende RR73
    WAIT_73 = auto()        # Warte auf 73 (QSO schon geloggt)
    LOGGING = auto()        # QSO abgeschlossen (legacy, nicht mehr genutzt)
    TIMEOUT = auto()        # Keine Antwort
```

**Nachher:**
```python
class QSOState(Enum):
    IDLE = auto()
    # --- CQ-Modus ---
    CQ_CALLING = auto()     # Sende "CQ DA1MHH JO31"
    CQ_WAIT = auto()        # Warte auf Anrufer
    # --- QSO-Sequenz (Hunt + CQ) ---
    TX_CALL = auto()        # Sende "DA1MHH DX5ABC JO31" (Hunt)
    WAIT_REPORT = auto()    # Warte auf Rapport
    TX_REPORT = auto()      # Sende Rapport
    WAIT_RR73 = auto()      # Warte auf RR73
    TX_RR73 = auto()        # Sende RR73
    WAIT_73 = auto()        # Warte auf 73 (QSO schon geloggt)
    TX_73_COURTESY = auto() # P1.10 Fix (v0.95.4): Hoeflichkeits-73 nach 73-Empfang
    LOGGING = auto()        # QSO abgeschlossen (legacy, nicht mehr genutzt)
    TIMEOUT = auto()        # Keine Antwort
```

### D2 — `core/qso_state.py:70-82` Dataclass-Erweiterung

**Vorher:**
```python
@dataclass
class QSOData:
    their_call: str = ""
    their_grid: str = ""
    their_snr: str = ""
    our_snr: str = ""
    freq_hz: int = 0
    start_time: float = 0.0
    timeout_cycles: int = 0
    max_timeout: int = 5
    calls_made: int = 0
    max_calls: int = 3
    rr73_retries: int = 0
```

**Nachher:**
```python
@dataclass
class QSOData:
    their_call: str = ""
    their_grid: str = ""
    their_snr: str = ""
    our_snr: str = ""
    freq_hz: int = 0
    start_time: float = 0.0
    timeout_cycles: int = 0
    max_timeout: int = 5
    calls_made: int = 0
    max_calls: int = 3
    rr73_retries: int = 0
    courtesy_73_sent: bool = False  # P1.10 Fix (v0.95.4): max 1× pro QSO
```

### D3 — `core/qso_state.py:430-436` on_message_sent neuer Branch

**Vorher (Z.416-436):**
```python
elif self.state == QSOState.TX_REPORT:
    # ... (unverändert)
elif self.state == QSOState.TX_RR73:
    # ADIF sofort loggen (RR73 oder 73 gesendet = QSO von unserer Seite bestaetigt)
    self.qso_complete.emit(self.qso)
    self.cq_qso_count += 1
    # Warte noch auf 73 von Gegenstation (max 2 Zyklen)
    self._set_state(QSOState.WAIT_73)
    self.qso.timeout_cycles = 0
```

**Nachher:**
```python
elif self.state == QSOState.TX_REPORT:
    # ... (unverändert)
elif self.state == QSOState.TX_RR73:
    # ADIF sofort loggen (RR73 oder 73 gesendet = QSO von unserer Seite bestaetigt)
    self.qso_complete.emit(self.qso)
    self.cq_qso_count += 1
    # Warte noch auf 73 von Gegenstation (max 2 Zyklen)
    self._set_state(QSOState.WAIT_73)
    self.qso.timeout_cycles = 0
elif self.state == QSOState.TX_73_COURTESY:
    # P1.10 Fix (v0.95.4): Courtesy-73 fertig gesendet.
    # qso_complete wurde bereits in TX_RR73 (Z.432) gefeuert — hier nur
    # qso_confirmed (UI „QSO ✓") + CQ resumen.
    self._dbg.log("TX", "Courtesy-73 fertig → qso_confirmed + resume_cq")
    self.qso_confirmed.emit(self.qso)
    self._resume_cq_if_needed()
```

### D4 — `core/qso_state.py:582-586` WAIT_73 + 73-Hauptlogik

**Vorher (Z.582-597):**
```python
if self.state == QSOState.WAIT_73:
    if msg.is_73 or msg.is_rr73:
        print(f"[QSO] 73 von {msg.caller} empfangen — QSO bestätigt!")
        self.qso_confirmed.emit(self.qso)
        self._resume_cq_if_needed()
    elif msg.is_r_report and msg.caller == self.qso.their_call:
        # Hoeflichkeit: Station hat unser RR73 nicht empfangen → nochmal senden (max 2x)
        if self.qso.rr73_retries < 2:
            self.qso.rr73_retries += 1
            tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
            print(f"[QSO] Hoeflichkeit: {msg.caller} wiederholt R-Report → sende RR73 erneut "
                  f"({self.qso.rr73_retries}/2)")
            self.send_message.emit(tx_msg)
        else:
            print(f"[QSO] {msg.caller} wiederholt R-Report — max Retries erreicht, ignoriert")
    return
```

**Nachher:**
```python
if self.state == QSOState.WAIT_73:
    if msg.is_73 or msg.is_rr73:
        print(f"[QSO] 73 von {msg.caller} empfangen — QSO bestätigt!")
        if not self.qso.courtesy_73_sent:
            # P1.10 Fix (v0.95.4): einmaliges Hoeflichkeits-73 zurueck.
            # IC-7300 wartet auf abschliessendes 73 in seiner Auto-Sequence
            # (sonst sendet er 5x weiter 73). Andere FT8-Apps (WSJT-X, JTDX)
            # senden es als Standard.
            self.qso.courtesy_73_sent = True
            tx_msg = f"{self.qso.their_call} {self.my_call} 73"
            self._dbg.log("TX", f"Courtesy-73 für {msg.caller}: '{tx_msg}'")
            # Slot-Paritaet defensiv auf Gegentakt setzen (R1 KP1).
            # Macht intern encoder.tx_even = not msg._tx_even via mw_qso.
            self.tx_slot_for_partner.emit(msg)
            self._set_state(QSOState.TX_73_COURTESY)
            self.send_message.emit(tx_msg)
            # qso_confirmed.emit + _resume_cq_if_needed in on_message_sent
            # fuer TX_73_COURTESY (Z.430+, Diff D3).
        else:
            # Hypothetischer Doppelschutz — wir verlassen WAIT_73 normalerweise
            # nach erstem 73 sofort (_set_state TX_73_COURTESY). Falls trotzdem
            # ein zweites 73 ankommt: nur confirmed + resume.
            self.qso_confirmed.emit(self.qso)
            self._resume_cq_if_needed()
    elif msg.is_r_report and msg.caller == self.qso.their_call:
        # Hoeflichkeit: Station hat unser RR73 nicht empfangen → nochmal senden (max 2x)
        if self.qso.rr73_retries < 2:
            self.qso.rr73_retries += 1
            tx_msg = f"{self.qso.their_call} {self.my_call} RR73"
            print(f"[QSO] Hoeflichkeit: {msg.caller} wiederholt R-Report → sende RR73 erneut "
                  f"({self.qso.rr73_retries}/2)")
            self.send_message.emit(tx_msg)
        else:
            print(f"[QSO] {msg.caller} wiederholt R-Report — max Retries erreicht, ignoriert")
    return
```

### D5 — `ui/mw_qso.py:200-204` is_tx-Set erweitern

**Vorher:**
```python
is_tx = state in (
    QSOState.TX_CALL, QSOState.TX_REPORT,
    QSOState.TX_RR73, QSOState.CQ_CALLING,
)
self.control_panel.set_tx_active(is_tx)
```

**Nachher:**
```python
is_tx = state in (
    QSOState.TX_CALL, QSOState.TX_REPORT,
    QSOState.TX_RR73, QSOState.TX_73_COURTESY,
    QSOState.CQ_CALLING,
)
self.control_panel.set_tx_active(is_tx)
```

### D6 — `main.py` Version-Bump

**Vorher:**
```python
APP_VERSION = "0.95.3"
```

**Nachher:**
```python
APP_VERSION = "0.95.4"
```

## 3. Test-Datei (NEU)

### `tests/test_p1_10_courtesy_73.py`

```python
"""Tests fuer P1.10 End-of-QSO Icom-73-Loop-Fix (v0.95.4).

Bug: IC-7300 (DA1TST) sendet nach Empfang unseres RR73 + Senden seines 73
weiter 5× 73 in den Folgeslots, weil seine Auto-Sequence auf abschliessendes
Hoeflichkeits-73 von uns wartet. SimpleFT8 sendet bisher kein Courtesy-73.

Fix: in WAIT_73 + 73/RR73-Empfang → einmaliges Courtesy-73 senden, neuer
State TX_73_COURTESY, Counter qso.courtesy_73_sent, on_message_sent-Branch
ruft qso_confirmed.emit + _resume_cq_if_needed.

Tests decken:
1-2: Courtesy-73 senden bei 73 oder RR73 in WAIT_73
3:   Counter-Schutz gegen Doppel-Senden
4-5: on_message_sent in TX_73_COURTESY (cq_mode=True/False)
6-7: Doppel-ADIF-Schutz (qso_complete genau 1×)
8:   WAIT_73-Timeout 3 Slots ohne 73 unverändert
9:   Slot-Paritaet (R1 KP1)
10:  Doppel-73 in TX_73_COURTESY-State faellt durch
11:  Vorwärtssprung WAIT_REPORT+RR73 → kein Doppel-ADIF (defensiv)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.qso_state import QSOStateMachine, QSOState, QSOData
from core.message import FT8Message


def _ensure_app():
    return QApplication.instance() or QApplication([])


def _make_73_msg(caller="DA1TST", target="DA1MHH", tx_even=False, freq=1500):
    """FT8Message mit '73' (z.B. 'DA1MHH DA1TST 73')."""
    msg = FT8Message(
        raw=f"{target} {caller} 73",
        field1=target,
        field2=caller,
        field3="73",
        snr=-15,
        freq_hz=freq,
    )
    msg._tx_even = tx_even
    return msg


def _make_rr73_msg(caller="DA1TST", target="DA1MHH", tx_even=False, freq=1500):
    """FT8Message mit 'RR73'."""
    msg = FT8Message(
        raw=f"{target} {caller} RR73",
        field1=target,
        field2=caller,
        field3="RR73",
        snr=-15,
        freq_hz=freq,
    )
    msg._tx_even = tx_even
    return msg


def _setup_wait_73_state(sm: QSOStateMachine, their_call="DA1TST",
                         their_grid="JN66"):
    """SM in WAIT_73 versetzen mit aktivem QSO."""
    sm.cq_mode = True
    sm.qso = QSOData(
        their_call=their_call,
        their_grid=their_grid,
        freq_hz=1500,
        start_time=1700000000.0,
        timeout_cycles=0,
    )
    sm._set_state(QSOState.WAIT_73)


# ── Test 1+2: Courtesy-73 senden bei 73 oder RR73 ────────────────────


def test_wait_73_with_73_sends_courtesy_73():
    """P1.10: WAIT_73 + 73 → Courtesy-73 gesendet, State=TX_73_COURTESY."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sent = []
    sm.send_message.connect(sent.append)

    msg = _make_73_msg()
    sm.on_message_received(msg)

    assert len(sent) == 1
    assert sent[0] == "DA1TST DA1MHH 73"
    assert sm.qso.courtesy_73_sent is True
    assert sm.state == QSOState.TX_73_COURTESY


def test_wait_73_with_rr73_sends_courtesy_73():
    """P1.10: WAIT_73 + RR73 → ebenfalls Courtesy-73."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sent = []
    sm.send_message.connect(sent.append)

    msg = _make_rr73_msg()
    sm.on_message_received(msg)

    assert len(sent) == 1
    assert sent[0] == "DA1TST DA1MHH 73"
    assert sm.qso.courtesy_73_sent is True
    assert sm.state == QSOState.TX_73_COURTESY


# ── Test 3: Counter-Schutz ────────────────────────────────────────────


def test_courtesy_73_only_once_per_qso():
    """P1.10: Doppel-73 in WAIT_73 → nur 1× Courtesy-73 (Counter-Schutz)."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sent = []
    sm.send_message.connect(sent.append)

    # Erstes 73 → Courtesy-73 + State-Wechsel zu TX_73_COURTESY
    sm.on_message_received(_make_73_msg())
    assert len(sent) == 1
    assert sm.state == QSOState.TX_73_COURTESY

    # Hypothetisch: zurueck nach WAIT_73 (sollte nicht passieren, aber
    # courtesy_73_sent muss schuetzen)
    sm._set_state(QSOState.WAIT_73)
    sm.on_message_received(_make_73_msg())
    # Kein zweites Courtesy-73
    assert len(sent) == 1


# ── Test 4-5: on_message_sent in TX_73_COURTESY ──────────────────────


def test_tx_73_courtesy_finished_with_cq_mode_resumes_cq():
    """P1.10: on_message_sent in TX_73_COURTESY + cq_mode=True →
    qso_confirmed + _send_cq → State=CQ_CALLING."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sm.qso.courtesy_73_sent = True  # simulate Courtesy-73 wurde gesendet
    sm._set_state(QSOState.TX_73_COURTESY)

    confirmed = []
    sent = []
    sm.qso_confirmed.connect(confirmed.append)
    sm.send_message.connect(sent.append)

    sm.on_message_sent()

    assert len(confirmed) == 1
    assert sm.state == QSOState.CQ_CALLING
    # _send_cq wurde aufgerufen
    assert any(s.startswith("CQ ") for s in sent)


def test_tx_73_courtesy_finished_without_cq_mode_goes_idle():
    """P1.10: on_message_sent in TX_73_COURTESY + cq_mode=False →
    qso_confirmed + State=IDLE."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)
    sm.cq_mode = False  # KEIN CQ-Modus
    sm._was_cq = False
    sm.qso.courtesy_73_sent = True
    sm._set_state(QSOState.TX_73_COURTESY)

    confirmed = []
    sm.qso_confirmed.connect(confirmed.append)

    sm.on_message_sent()

    assert len(confirmed) == 1
    assert sm.state == QSOState.IDLE


# ── Test 6-7: Doppel-ADIF-Schutz ─────────────────────────────────────


def test_qso_complete_fires_once_during_full_cq_qso_cycle():
    """P1.10: qso_complete.emit feuert genau 1× pro QSO (TX_RR73 only,
    NICHT in TX_73_COURTESY)."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    completes = []
    sm.qso_complete.connect(completes.append)

    # Simuliere Phase 1: TX_RR73 → on_message_sent
    sm._set_state(QSOState.TX_RR73)
    sm.on_message_sent()
    assert len(completes) == 1
    assert sm.state == QSOState.WAIT_73

    # Phase 2: 73-Empfang → Courtesy-73-Sequenz
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY
    sm.on_message_sent()  # Courtesy-73 fertig

    # qso_complete sollte NICHT erneut feuern
    assert len(completes) == 1


def test_qso_confirmed_fires_once_after_courtesy_73():
    """P1.10: qso_confirmed.emit feuert genau 1× — nach Courtesy-73-Senden."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    confirmed = []
    sm.qso_confirmed.connect(confirmed.append)

    # 73-Empfang → Courtesy-73 (qso_confirmed darf NICHT direkt feuern)
    sm.on_message_received(_make_73_msg())
    assert len(confirmed) == 0  # noch nicht — erst nach Send

    # Courtesy-73-TX fertig → qso_confirmed feuert
    sm.on_message_sent()
    assert len(confirmed) == 1


# ── Test 8: WAIT_73-Timeout unverändert ──────────────────────────────


def test_wait_73_timeout_without_73_unchanged():
    """P1.10: WAIT_73-Timeout 3 Slots ohne 73 → bisheriges Verhalten."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    confirmed = []
    sent = []
    sm.qso_confirmed.connect(confirmed.append)
    sm.send_message.connect(sent.append)

    # 3× on_cycle_end ohne 73-Empfang → Timeout-Pfad
    for _ in range(3):
        sm.on_cycle_end()

    # Bisheriges Verhalten: qso_confirmed + _resume_cq, kein Courtesy-73
    assert len(confirmed) == 1
    assert sm.qso.courtesy_73_sent is False  # nicht gesetzt
    # _send_cq wurde aufgerufen (cq_mode=True)
    assert any(s.startswith("CQ ") for s in sent)


# ── Test 9: Slot-Paritaet (R1 KP1) ───────────────────────────────────


def test_courtesy_73_slot_parity_via_signal():
    """P1.10: tx_slot_for_partner.emit(msg) wird mit dem 73-msg gefeuert,
    damit mw_qso encoder.tx_even = not msg._tx_even setzt."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    slot_msgs = []
    sm.tx_slot_for_partner.connect(slot_msgs.append)

    # DA1TST 73 in ODD-Slot (_tx_even=False)
    msg = _make_73_msg(tx_even=False)
    sm.on_message_received(msg)

    # Signal wurde mit dem msg gefeuert
    assert len(slot_msgs) == 1
    assert slot_msgs[0] is msg
    assert getattr(slot_msgs[0], "_tx_even", None) is False


# ── Test 10: Doppel-73 in TX_73_COURTESY ─────────────────────────────


def test_second_73_in_tx_73_courtesy_state_falls_through():
    """P1.10: 73 waehrend TX_73_COURTESY → kein Trigger, State unveraendert."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    _setup_wait_73_state(sm)

    sent = []
    sm.send_message.connect(sent.append)

    # Erstes 73 → Courtesy-73 + TX_73_COURTESY
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY
    initial_sent = len(sent)

    # Zweites 73 waehrend TX_73_COURTESY
    sm.on_message_received(_make_73_msg())

    # Kein zusaetzlicher Send, State bleibt TX_73_COURTESY
    assert len(sent) == initial_sent
    assert sm.state == QSOState.TX_73_COURTESY


# ── Test 11: Vorwaertssprung ohne Doppel-ADIF (defensiv) ─────────────


def test_forward_jump_wait_report_rr73_no_double_adif():
    """P1.10: Vorwaertssprung WAIT_REPORT + RR73 → TX_RR73 sendet '73' + ADIF.
    Spaetere 73-Empfang in WAIT_73 → Courtesy-73 (ADIF NICHT erneut).
    Sicherheit gegen Doppel-ADIF auch bei Sprung-Pfad."""
    _ensure_app()
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = False  # Hunt-Modus
    sm.qso = QSOData(
        their_call="DA1TST",
        their_grid="JN66",
        freq_hz=1500,
        start_time=1700000000.0,
    )
    sm._set_state(QSOState.WAIT_REPORT)

    completes = []
    sm.qso_complete.connect(completes.append)

    # Vorwaertssprung: RR73 in WAIT_REPORT → TX_RR73 + sende '73'
    rr73 = _make_rr73_msg()
    sm.on_message_received(rr73)
    assert sm.state == QSOState.TX_RR73

    # TX_RR73 fertig → qso_complete (= ADIF)
    sm.on_message_sent()
    assert len(completes) == 1
    assert sm.state == QSOState.WAIT_73

    # Jetzt in WAIT_73 — kommt 73 → Courtesy-73-Pfad
    sm.on_message_received(_make_73_msg())
    assert sm.state == QSOState.TX_73_COURTESY

    # Courtesy-73 fertig → qso_confirmed, KEIN zweites qso_complete
    sm.on_message_sent()
    assert len(completes) == 1
```

## 4. Implementierungs-Reihenfolge

1. **App stoppen** — laufende v0.95.3 PID 80961 (verhindert Stats-Verfälschung)
2. **D1 + D2** in `core/qso_state.py` (Enum + Dataclass)
3. **D3** in `core/qso_state.py` (on_message_sent neuer Branch)
4. **D4** in `core/qso_state.py` (WAIT_73-Hauptlogik)
5. **D5** in `ui/mw_qso.py` (is_tx-Set)
6. **D6** in `main.py` (Version-Bump)
7. **D7** Test-Datei `tests/test_p1_10_courtesy_73.py` erstellen
8. **Tests laufen lassen:** `./venv/bin/python3 -m pytest tests/ -q` → erwartet 775 passed
9. **App neu starten** v0.95.4
10. **Atomarer Commit** Code+Tests (5 modifizierte + 1 neue Datei)
11. **Doku-Commit:** HISTORY.md + HANDOFF.md (beide Pfade) + CLAUDE.md (beide Pfade) + TODO.md
12. **Memory:** ggf. Lesson-Datei

## 5. Verifikations-Checks vor Commit

- [ ] `./venv/bin/python3 -m pytest tests/ -q` → 775 passed (764 + 11)
- [ ] `./venv/bin/python3 -m pytest tests/test_p1_10_courtesy_73.py -v` → 11 passed
- [ ] `./venv/bin/python3 -m pytest tests/test_qso_state.py -q` → unverändert grün
- [ ] `git diff` zeigt nur 5 modifizierte + 1 neue Datei
- [ ] App startet ohne Fehler (python3 main.py kurz)
- [ ] APP_VERSION zeigt "0.95.4"

## 6. Commit-Plan

### Commit 1: Code + Tests (atomar)
```
feat(qso): P1.10 Courtesy-73 nach 73-Empfang in WAIT_73 (v0.95.4)

Wurzel: IC-7300 (DA1TST) Auto-Sequence wartet auf abschliessendes
Hoeflichkeits-73 von uns. SimpleFT8 sendet bisher kein Courtesy-73 →
IC-7300 retried 5× in Folgeslots bevor er aufgibt. Andere FT8-Apps
(WSJT-X, JTDX, MSHV) senden es als Standard.

Fix:
- core/qso_state.py: neuer State TX_73_COURTESY, neues Feld
  qso.courtesy_73_sent (max 1× pro QSO), neuer Branch in on_message_sent
  fuer TX_73_COURTESY (qso_confirmed + _resume_cq_if_needed),
  WAIT_73-Hauptlogik geaendert: bei 73/RR73-Empfang einmaliges
  Courtesy-73 senden + Slot-Paritaet via tx_slot_for_partner.emit (R1 KP1)
- ui/mw_qso.py: is_tx-Set erweitert um TX_73_COURTESY
- main.py: APP_VERSION 0.95.3 → 0.95.4
- tests/test_p1_10_courtesy_73.py: 11 neue Tests

Voller V1→V2(8 V1-Luecken)→R1(4 KP + 3 Findings)→V3 Diagnose-Workflow
+ Plan-V1→V2→R1→V3-Workflow. Tests 764 → 775 gruen (+11).

Field-Test bei Mike ausstehend (DA1TST IC-7300, 30m FT8).
```

### Commit 2: Doku
```
docs: v0.95.4 P1.10 Courtesy-73 Stand
- HISTORY.md neuer Eintrag
- HANDOFF.md beide Pfade Stand v0.95.4
- CLAUDE.md beide Pfade Aktueller Stand
- TODO.md P1.10 als ✅
```

## 7. Risiken & Mitigation

| Risiko | Mitigation |
|---|---|
| Test fehlschlägt weil FT8Message-Properties anders | P1.9-Test-Pattern als Vorbild — nutzt field1/field2/field3 direkt |
| Slot-Paritaet via Signal funktioniert nur in echtem QApplication-Loop | Test 9 prueft Signal-Emission, nicht Encoder.tx_even direkt |
| `on_message_sent`-Reihenfolge gegenueber `cycle_finished` | unveraendert (P1.9 hat das gefixt — wir fuegen nur neuen Branch hinzu) |
| Doppel-ADIF wegen Reuse | D3 emittet KEIN qso_complete in TX_73_COURTESY-Branch |

## 8. Workflow-Status

| Phase | Status |
|---|---|
| Diagnose-V1→V2→R1→V3 | ✅ |
| **Plan-V1** | ✅ **DIESE DATEI** |
| Plan-V2 Self-Review | 🔴 nächster Schritt |
| Plan-R1 DeepSeek | 🔴 |
| Plan-V3 | 🔴 |
| Mike-Freigabe Plan | (Mike hat „lass uns loslegen" gesagt — autonom durchziehen) |
| Code-Implementation | 🔴 |
| Tests + Verifikation | 🔴 |
| Atomare Commits | 🔴 |
| Field-Test Mike | 🔴 |

---

**Plan-V1 Ende.**
