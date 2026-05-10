"""Tests fuer P5.OMNI-PATTERN-FIX-3 Encoder-Pending-Queue (v0.96.2).

Bug: Pos 1 (TX nach TX) im OMNI-5-Slot-Pattern war IMMER encoder-busy
(3x reproduziert im Field-Test 10.05.2026). Wurzel: FT8 12.64s Audio
+ 1.3s FlexRadio-Buffer-Drain + PTT-Off + Jitter -> _is_transmitting=False
faellt :42.8-:44.5, Pos 1 cycle_start :45 hat oft <1s Race-Window.

Loesung Variante A (R1-Empfehlung): transmit() queut Pending statt
return False, Worker-Finally konsumiert Pending direkt. Verfall-Schwelle
1.5 * cycle_duration. _pending_tx + _pending_queued_at UNTER
_replace_lock (R1-KRITISCH).

F1-KRITISCH (Cold-Start-Test): abort-Check VOR Re-Trigger im
Pending-Loop. _run_one_tx_pass cleart _abort_event und setzt
_is_transmitting=True - wuerde abort() ueberschreiben.

Tests decken (V3 §7 T1, T9-T13):
- T1: transmit() returnt True + queut Pending bei busy
- T9: Pending wird konsumiert wenn Ziel-Slot erreichbar
- T10: Pending verfaellt wenn > 1.5 * cycle_duration
- T11: _pending_queued_at UNTER Lock (R1+F1-KRITISCH Race-Schutz)
- T12: Multiple Pendings hintereinander (Loop, kein Stack-Overflow)
- T13: Abort BEVOR Pending-Re-Trigger bricht Loop sauber ab (F1-KRITISCH)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import concurrent.futures
import inspect
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from core.encoder import Encoder


def _ensure_app():
    return QApplication.instance() or QApplication([])


# ── T1: Pending-Queue bei busy ─────────────────────────────────────


def test_transmit_returns_true_when_busy_and_queues_pending():
    """T1 (AC-B1, AC-E1, AC-E2): transmit() bei busy → Pending-Queue + True."""
    _ensure_app()
    enc = Encoder(audio_freq_hz=1000)
    enc._is_transmitting = True
    before = time.time()
    ok = enc.transmit("TEST DA1MHH JO31", tx_even=False, audio_freq_hz=475)
    after = time.time()
    # Returnt True (statt False)
    assert ok is True
    # Pending-Tupel korrekt gesetzt
    assert enc._pending_tx == ("TEST DA1MHH JO31", False, 475)
    # Timestamp aktuell
    assert before <= enc._pending_queued_at <= after


# ── T9: Pending konsumiert ─────────────────────────────────────────


def test_pending_consumed_after_finally_when_target_slot_reachable():
    """T9 (AC-E3): Worker konsumiert Pending im Loop wenn Ziel erreichbar."""
    _ensure_app()
    enc = Encoder(audio_freq_hz=1000)
    enc._mode = "FT8"

    call_args: list[str] = []

    def side_effect(msg):
        call_args.append(msg)
        # Beim ersten Call (pass-1): Pending fuer Slot-naechste-Boundary setzen.
        # _compute_target_slot mit tx_even=None gibt naechsten Slot — sicher
        # < 1.5*15s = 22.5s in der Zukunft.
        if len(call_args) == 1:
            with enc._replace_lock:
                enc._pending_tx = ("SECOND CQ", None, 1500)
                enc._pending_queued_at = time.time()

    enc._run_one_tx_pass = MagicMock(side_effect=side_effect)
    enc._tx_worker("FIRST CQ")

    # Loop hat Pending konsumiert → 2× gerufen
    assert call_args == ["FIRST CQ", "SECOND CQ"]
    # Pending wieder None (durch Loop-Pop konsumiert)
    assert enc._pending_tx is None
    assert enc._pending_queued_at == 0.0
    # tx_even unveraendert (None) + audio_freq_hz auf Pending-Wert gesetzt
    assert enc.audio_freq_hz == 1500


# ── T10: Pending-Verfall ────────────────────────────────────────────


def test_pending_dropped_if_target_slot_in_past_more_than_1_5_slots():
    """T10 (AC-E4): Pending verfaellt wenn target_slot - queued_at > 1.5*slot."""
    _ensure_app()
    enc = Encoder(audio_freq_hz=1000)
    enc._mode = "FT8"

    call_args: list[str] = []

    def side_effect(msg):
        call_args.append(msg)
        if len(call_args) == 1:
            # Pending mit Timestamp 30s in der Vergangenheit setzen.
            # _compute_target_slot gibt aktuellen Slot (≈ jetzt), Differenz
            # zu queued_at (jetzt-30s) ist > 22.5s → Verfall.
            with enc._replace_lock:
                enc._pending_tx = ("STALE CQ", False, 1500)
                enc._pending_queued_at = time.time() - 30.0

    enc._run_one_tx_pass = MagicMock(side_effect=side_effect)
    enc._tx_worker("FIRST CQ")

    # Nur Pass-1 gelaufen, Pending verfallen ohne Re-Trigger
    assert call_args == ["FIRST CQ"]
    # Pending geleert (durch Loop-Pop), kein zweites _run_one_tx_pass
    assert enc._pending_tx is None


# ── T11: Lock-Schutz fuer _pending_queued_at + _pending_tx ──────────


def test_pending_queued_at_set_under_lock_code_inspection():
    """T11a (AC-E5, R1+F1-KRITISCH): Code-Check dass beide Felder
    UNTER _replace_lock gesetzt werden (statisch verifiziert).
    """
    src = inspect.getsource(Encoder.transmit)
    # Suche den Lock-Block + beide Setter darin
    assert "with self._replace_lock:" in src
    lines = src.split("\n")
    in_lock = False
    indent_lock = None
    pending_tx_in_lock = False
    pending_queued_at_in_lock = False
    for line in lines:
        if not line.strip():
            continue
        if "with self._replace_lock:" in line and not in_lock:
            in_lock = True
            indent_lock = len(line) - len(line.lstrip())
            continue
        if in_lock:
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent_lock and line.strip():
                in_lock = False
                continue
            if "self._pending_tx = " in line:
                pending_tx_in_lock = True
            if "self._pending_queued_at = " in line:
                pending_queued_at_in_lock = True
    assert pending_tx_in_lock, "_pending_tx muss UNTER _replace_lock gesetzt werden"
    assert pending_queued_at_in_lock, "_pending_queued_at muss UNTER _replace_lock gesetzt werden"


def test_pending_consistency_under_concurrent_transmit():
    """T11b (AC-E5): Stress-Test mit 200 parallel transmit() bei busy.
    Pending darf NIEMALS Halb-State sein (z.B. _tx gesetzt + queued_at=0).
    """
    _ensure_app()
    enc = Encoder(audio_freq_hz=1000)
    enc._is_transmitting = True

    def caller(idx: int) -> bool:
        return enc.transmit(
            f"CQ MSG-{idx}", tx_even=(idx % 2 == 0), audio_freq_hz=1500 + idx
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(caller, range(200)))

    # Alle returnen True (busy → Pending)
    assert all(results)
    # End-State konsistent: beide gesetzt oder beide leer (kein Halb-State)
    if enc._pending_tx is not None:
        assert enc._pending_queued_at > 0.0, (
            "Halb-State verboten: _pending_tx gesetzt aber _pending_queued_at=0"
        )


# ── T12: Multi-Pending-Loop (kein Stack-Overflow) ──────────────────


def test_pending_loop_handles_multiple_consecutive_pendings():
    """T12 (AC-E6): Loop konsumiert mehrere konsekutive Pendings sicher."""
    _ensure_app()
    enc = Encoder(audio_freq_hz=1000)
    enc._mode = "FT8"

    call_args: list[str] = []
    pending_iter = [0]

    def side_effect(msg):
        call_args.append(msg)
        # Bei jedem der ersten 2 Calls: neues Pending setzen → Loop iteriert.
        # tx_even=None damit _compute_target_slot den naechsten Slot (egal
        # welche Paritaet) waehlt → diff < 1.5*15s = 22.5s → kein Verfall.
        if pending_iter[0] < 2:
            pending_iter[0] += 1
            with enc._replace_lock:
                enc._pending_tx = (f"PENDING-{pending_iter[0]}", None, 1500)
                enc._pending_queued_at = time.time()

    enc._run_one_tx_pass = MagicMock(side_effect=side_effect)
    enc._tx_worker("FIRST")

    # Loop hat 3 Iterationen ohne Rekursion abgearbeitet
    assert call_args == ["FIRST", "PENDING-1", "PENDING-2"]
    # Am Ende kein Pending mehr
    assert enc._pending_tx is None


def test_pending_overwrite_on_consecutive_transmit_last_wins():
    """T12b: 3 transmit-Aufrufe waehrend busy → letzter ueberschreibt vorherige."""
    _ensure_app()
    enc = Encoder(audio_freq_hz=1000)
    enc._is_transmitting = True

    enc.transmit("MSG1", tx_even=False, audio_freq_hz=1500)
    enc.transmit("MSG2", tx_even=True, audio_freq_hz=1600)
    enc.transmit("MSG3", tx_even=False, audio_freq_hz=1700)

    # Letzter gewinnt
    assert enc._pending_tx == ("MSG3", False, 1700)


# ── T13: F1-KRITISCH abort waehrend Pending-Loop ───────────────────


def test_abort_during_pending_breaks_loop():
    """T13 (AC-E7, F1-KRITISCH): abort() zwischen Pass-1 und Pending-Re-Trigger
    bricht Loop SOFORT ab. Ohne F1-Fix wuerde _run_one_tx_pass den abort
    (clear() + _is_transmitting=True) ueberschreiben.
    """
    _ensure_app()
    enc = Encoder(audio_freq_hz=1000)
    enc._mode = "FT8"

    call_args: list[str] = []

    def side_effect(msg):
        call_args.append(msg)
        if len(call_args) == 1:
            # Pass-1: Pending setzen UND abort() rufen.
            # tx_even=None → Pending wuerde sonst durchlaufen (kein Verfall) —
            # so testet der Test wirklich den Abort-Pfad, nicht den Verfall-Pfad.
            with enc._replace_lock:
                enc._pending_tx = ("SECOND CQ", None, 1500)
                enc._pending_queued_at = time.time()
            enc.abort()  # setzt _abort_event + _is_transmitting=False

    enc._run_one_tx_pass = MagicMock(side_effect=side_effect)
    enc._tx_worker("FIRST CQ")

    # Pass-1 gelaufen, Pass-2 verworfen wegen abort (NICHT Verfall)
    assert call_args == ["FIRST CQ"]
    # Pending geleert (durch Loop-Pop), aber _run_one_tx_pass nicht erneut gerufen
    assert enc._pending_tx is None
    # _abort_event ist immer noch gesetzt (Pass-2 wurde nicht gerufen, der
    # _run_one_tx_pass.clear() haette es geloescht). Beweist Abort-Pfad.
    assert enc._abort_event.is_set()
