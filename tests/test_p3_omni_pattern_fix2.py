"""Tests fuer P3.OMNI-PATTERN-FIX-2 (v0.95.25).

Bug aus v0.95.24: Mike-Field-Test 09.05.2026 zeigte 4 Probleme:
1. GUI-Tick-Latency macht Pretrigger zu spaet (cycle_pos=14.89s
   statt 13.7s) → Encoder overshoot=1.19s > 0.3s → v0.80 Drift-
   Schutz verschiebt 2 Slots → Pattern verschoben.
2. Button-Label statisch — Mike sieht nicht ob OMNI aktiv.
3. (verworfen V2-L3) — User-Start hat KEIN Drift-Problem.
4. RX-Slots stumm im QSO-Panel.

Loesung (R1-bestaetigt):
1. QTimer.singleShot mit Qt.PreciseTimer in _on_cycle_start
   geplant — typisch 0-50ms Drift gegen 0-1500ms bei Signal-Queue.
2. Cycle-Tick-Pretrigger als Fallback bei dur - 0.5s.
3. Button-Label dynamisch via update_omni_tx (Commit 2).
4. add_listening in qso_panel (Commit 3).

Tests Commit 1 (T1, T2, T8, T10, T11, T12) decken QTimer + Fallback.
T3 in Commit 2, T6/T7/T9 in Commit 3.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.omni_tx import OmniTX
from core.qso_state import QSOStateMachine, QSOState


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def omni_fresh():
    """Frische OmniTX-Instanz pro Test."""
    from core import omni_tx as _omni
    _omni._instance = None
    yield
    _omni._instance = None


# ─────────────────────────────────────────────────────────────────────
# T1 — QTimer scheduled in _on_cycle_start
# ─────────────────────────────────────────────────────────────────────


def test_pretrigger_qtimer_scheduled_with_correct_delay(app, omni_fresh):
    """T1 (AC1): _on_cycle_start startet QTimer mit delay = (dur - 1.3) * 1000.

    FT8 (15s): 13700ms. FT4 (7.5s): 6200ms. FT2 (3.8s): 2500ms.
    Schwelle ist Encoder-Sleep-sichere Untergrenze (V2 L2).
    """
    from PySide6.QtCore import QTimer
    from ui.mw_cycle import _OMNI_PRETRIGGER_OFFSET_S

    # Mock Cycle-Mixin-Stub mit allem was _on_cycle_start braucht
    stub = MagicMock()
    stub._omni_tx = OmniTX()
    stub._omni_tx.start_with_parity_for_next_slot(next_is_even=True)
    stub._omni_pretrigger_timer = MagicMock(spec=QTimer)
    stub._omni_pretriggered = False
    stub.timer = MagicMock()
    stub.timer.cycle_duration = 15.0
    stub.encoder = MagicMock()
    stub.encoder.is_transmitting = False
    stub.control_panel = MagicMock()
    stub._fwdpwr_samples = []
    stub.qso_sm = MagicMock()
    stub.qso_sm.on_cycle_end = MagicMock()
    stub._rx_mode = "normal"
    stub.radio = MagicMock(ip=False)
    stub.rx_panel = MagicMock(_rx_active=False)

    # Methode binden
    from ui.mw_cycle import CycleMixin
    bound = CycleMixin._on_cycle_start.__get__(stub, type(stub))
    bound(cycle_num=1, is_even=True)

    expected_ms = int((15.0 - _OMNI_PRETRIGGER_OFFSET_S) * 1000)
    stub._omni_pretrigger_timer.start.assert_called_once_with(expected_ms)


def test_pretrigger_qtimer_delay_for_ft4(app, omni_fresh):
    """T1b: FT4 Slot 7.5s → 6200ms delay."""
    from PySide6.QtCore import QTimer
    from ui.mw_cycle import _OMNI_PRETRIGGER_OFFSET_S, CycleMixin

    stub = MagicMock()
    stub._omni_tx = OmniTX()
    stub._omni_tx.start_with_parity_for_next_slot(next_is_even=False)
    stub._omni_pretrigger_timer = MagicMock(spec=QTimer)
    stub._omni_pretriggered = False
    stub.timer = MagicMock()
    stub.timer.cycle_duration = 7.5  # FT4
    stub.encoder = MagicMock(is_transmitting=False)
    stub.control_panel = MagicMock()
    stub._fwdpwr_samples = []
    stub.qso_sm = MagicMock()
    stub._rx_mode = "normal"
    stub.radio = MagicMock(ip=False)
    stub.rx_panel = MagicMock(_rx_active=False)

    bound = CycleMixin._on_cycle_start.__get__(stub, type(stub))
    bound(cycle_num=1, is_even=False)

    expected_ms = int((7.5 - _OMNI_PRETRIGGER_OFFSET_S) * 1000)
    stub._omni_pretrigger_timer.start.assert_called_once_with(expected_ms)


# ─────────────────────────────────────────────────────────────────────
# T11 — Inactive OMNI startet keinen Timer
# ─────────────────────────────────────────────────────────────────────


def test_inactive_omni_does_not_start_timer(app, omni_fresh):
    """T11 (AC1): Wenn OMNI nicht aktiv, kein Timer-Start."""
    from PySide6.QtCore import QTimer
    from ui.mw_cycle import CycleMixin

    stub = MagicMock()
    stub._omni_tx = OmniTX()
    # NICHT start_with_parity → active=False
    stub._omni_pretrigger_timer = MagicMock(spec=QTimer)
    stub._omni_pretriggered = False
    stub.timer = MagicMock(cycle_duration=15.0)
    stub.encoder = MagicMock(is_transmitting=False)
    stub.control_panel = MagicMock()
    stub._fwdpwr_samples = []
    stub.qso_sm = MagicMock()
    stub._rx_mode = "normal"
    stub.radio = MagicMock(ip=False)
    stub.rx_panel = MagicMock(_rx_active=False)

    bound = CycleMixin._on_cycle_start.__get__(stub, type(stub))
    bound(cycle_num=1, is_even=True)

    stub._omni_pretrigger_timer.start.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# T12 — Paused OMNI startet keinen Timer
# ─────────────────────────────────────────────────────────────────────


def test_paused_omni_does_not_start_timer(app, omni_fresh):
    """T12 (AC1): OMNI aktiv aber paused → kein Timer-Start.

    QSO laeuft, OMNI pausiert via _pause_omni_if_active. Resume holt
    OMNI wieder via start_with_parity_for_next_slot — dann erst
    Pretrigger erlaubt.
    """
    from PySide6.QtCore import QTimer
    from ui.mw_cycle import CycleMixin

    stub = MagicMock()
    stub._omni_tx = OmniTX()
    stub._omni_tx.start_with_parity_for_next_slot(next_is_even=True)
    stub._omni_tx.pause()  # Pause aktiv
    stub._omni_pretrigger_timer = MagicMock(spec=QTimer)
    stub._omni_pretriggered = False
    stub.timer = MagicMock(cycle_duration=15.0)
    stub.encoder = MagicMock(is_transmitting=False)
    stub.control_panel = MagicMock()
    stub._fwdpwr_samples = []
    stub.qso_sm = MagicMock()
    stub._rx_mode = "normal"
    stub.radio = MagicMock(ip=False)
    stub.rx_panel = MagicMock(_rx_active=False)

    bound = CycleMixin._on_cycle_start.__get__(stub, type(stub))
    bound(cycle_num=1, is_even=True)

    stub._omni_pretrigger_timer.start.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# T10 — Restart-Semantik: 2x cycle_start → 2x start (alter ersetzt)
# ─────────────────────────────────────────────────────────────────────


def test_cycle_start_restarts_pending_timer(app, omni_fresh):
    """T10 (AC17): start() nach start() ersetzt alten Timeout —
    Qt-Eingebauter Mechanismus, kein expliziter stop() noetig."""
    from PySide6.QtCore import QTimer
    from ui.mw_cycle import CycleMixin, _OMNI_PRETRIGGER_OFFSET_S

    stub = MagicMock()
    stub._omni_tx = OmniTX()
    stub._omni_tx.start_with_parity_for_next_slot(next_is_even=True)
    stub._omni_pretrigger_timer = MagicMock(spec=QTimer)
    stub._omni_pretriggered = False
    stub.timer = MagicMock(cycle_duration=15.0)
    stub.encoder = MagicMock(is_transmitting=False)
    stub.control_panel = MagicMock()
    stub._fwdpwr_samples = []
    stub.qso_sm = MagicMock()
    stub._rx_mode = "normal"
    stub.radio = MagicMock(ip=False)
    stub.rx_panel = MagicMock(_rx_active=False)

    bound = CycleMixin._on_cycle_start.__get__(stub, type(stub))
    bound(cycle_num=1, is_even=True)
    bound(cycle_num=2, is_even=False)

    expected_ms = int((15.0 - _OMNI_PRETRIGGER_OFFSET_S) * 1000)
    assert stub._omni_pretrigger_timer.start.call_count == 2
    stub._omni_pretrigger_timer.start.assert_called_with(expected_ms)


# ─────────────────────────────────────────────────────────────────────
# T2 — Pretrigger-Fire ruft _send_cq mit korrekten Pre-Conds
# ─────────────────────────────────────────────────────────────────────


def test_pretrigger_fire_impl_calls_send_cq(app, omni_fresh):
    """T2 (AC2): _omni_pretrigger_fire_impl() bei Pre-Conds erfuellt
    setzt encoder.tx_even + qso_sm._was_pretriggered + ruft _send_cq.
    """
    from ui.mw_cycle import CycleMixin

    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)
    sm.qso.timeout_cycles = 0

    stub = MagicMock()
    stub._omni_tx = OmniTX()
    stub._omni_tx.start_with_parity_for_next_slot(next_is_even=True)  # Block 1
    stub._omni_pretriggered = False
    stub.qso_sm = sm
    stub.encoder = MagicMock()

    captured = []
    sm.send_message.connect(captured.append)

    bound = CycleMixin._omni_pretrigger_fire_impl.__get__(stub, type(stub))
    bound()

    assert stub._omni_pretriggered is True
    # Pos 0 → peek_next zeigt Pos 1 = TX Odd (Block 1)
    assert stub.encoder.tx_even is False
    assert sm._was_pretriggered is True
    assert len(captured) == 1
    assert captured[0].startswith("CQ ")


def test_pretrigger_fire_idempotent_via_flag(app, omni_fresh):
    """T2b: zweiter Aufruf mit Flag=True → return ohne weiteres _send_cq."""
    from ui.mw_cycle import CycleMixin

    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)
    stub = MagicMock()
    stub._omni_tx = OmniTX()
    stub._omni_tx.start_with_parity_for_next_slot(next_is_even=True)
    stub._omni_pretriggered = True  # Flag schon gesetzt
    stub.qso_sm = sm
    stub.encoder = MagicMock()

    captured = []
    sm.send_message.connect(captured.append)

    bound = CycleMixin._omni_pretrigger_fire_impl.__get__(stub, type(stub))
    bound()

    assert len(captured) == 0


def test_pretrigger_fire_skips_rx_slot(app, omni_fresh):
    """T2c: peek_next returnt RX-Slot → Flag wird gesetzt aber kein _send_cq."""
    from ui.mw_cycle import CycleMixin

    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.advance()  # Pos 1 → peek_next zeigt Pos 2 = RX
    stub = MagicMock()
    stub._omni_tx = omni
    stub._omni_pretriggered = False
    stub.qso_sm = sm
    stub.encoder = MagicMock()

    captured = []
    sm.send_message.connect(captured.append)

    bound = CycleMixin._omni_pretrigger_fire_impl.__get__(stub, type(stub))
    bound()

    assert stub._omni_pretriggered is True  # Flag fuer Reentrancy
    assert len(captured) == 0  # KEIN _send_cq bei RX


# ─────────────────────────────────────────────────────────────────────
# T8 — Cycle-Tick-Fallback bei dur-0.5s
# ─────────────────────────────────────────────────────────────────────


def test_pretrigger_fallback_via_cycle_tick(app, omni_fresh):
    """T8 (AC10/AC13): _omni_pretrigger_check ist Fallback.

    Wenn _omni_pretriggered=False (QTimer hat NICHT gefeuert) UND
    sic > dur - 0.5s → fallback feuert.
    """
    from ui.mw_cycle import CycleMixin

    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)

    stub = MagicMock()
    stub._omni_tx = OmniTX()
    stub._omni_tx.start_with_parity_for_next_slot(next_is_even=True)
    stub._omni_pretriggered = False  # QTimer hat NICHT gefeuert
    stub.qso_sm = sm
    stub.encoder = MagicMock()
    # fire_impl an stub binden — sonst MagicMock-Default greift nicht
    stub._omni_pretrigger_fire_impl = (
        CycleMixin._omni_pretrigger_fire_impl.__get__(stub, type(stub)))

    captured = []
    sm.send_message.connect(captured.append)

    bound = CycleMixin._omni_pretrigger_check.__get__(stub, type(stub))
    # sic = 14.7 > 14.5 (Fallback-Schwelle) → feuert
    bound(sic=14.7, dur=15.0)

    assert stub._omni_pretriggered is True
    assert len(captured) == 1


def test_pretrigger_fallback_does_not_fire_when_qtimer_was_first(
        app, omni_fresh):
    """T8b: _omni_pretriggered=True (QTimer hat schon gefeuert) →
    Fallback returnt sofort, kein Doppel-Trigger."""
    from ui.mw_cycle import CycleMixin

    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)

    stub = MagicMock()
    stub._omni_tx = OmniTX()
    stub._omni_tx.start_with_parity_for_next_slot(next_is_even=True)
    stub._omni_pretriggered = True  # QTimer hat schon gefeuert
    stub.qso_sm = sm
    stub.encoder = MagicMock()

    captured = []
    sm.send_message.connect(captured.append)

    bound = CycleMixin._omni_pretrigger_check.__get__(stub, type(stub))
    bound(sic=14.7, dur=15.0)

    # Flag bleibt True, kein _send_cq
    assert len(captured) == 0


def test_pretrigger_fallback_below_threshold_no_fire(app, omni_fresh):
    """T8c: sic < dur-0.5 → Fallback-Schwelle nicht erreicht."""
    from ui.mw_cycle import CycleMixin

    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._set_state(QSOState.CQ_WAIT)

    stub = MagicMock()
    stub._omni_tx = OmniTX()
    stub._omni_tx.start_with_parity_for_next_slot(next_is_even=True)
    stub._omni_pretriggered = False
    stub.qso_sm = sm
    stub.encoder = MagicMock()

    captured = []
    sm.send_message.connect(captured.append)

    bound = CycleMixin._omni_pretrigger_check.__get__(stub, type(stub))
    # sic = 14.0 < 14.5 (Fallback-Schwelle) → kein Fire
    bound(sic=14.0, dur=15.0)

    assert stub._omni_pretriggered is False
    assert len(captured) == 0


# ─────────────────────────────────────────────────────────────────────
# T9-Vorbereitung — wird in Commit 3 ergaenzt mit Mode-Stop-Reasons
# ─────────────────────────────────────────────────────────────────────


def test_omni_pretrigger_offset_constant(app):
    """Sanity: _OMNI_PRETRIGGER_OFFSET_S unveraendert von P2 (1.3s)."""
    from ui.mw_cycle import _OMNI_PRETRIGGER_OFFSET_S
    assert _OMNI_PRETRIGGER_OFFSET_S == 1.3


# ─────────────────────────────────────────────────────────────────────
# T3 — Button-Label Update via update_omni_tx (Commit 2)
# ─────────────────────────────────────────────────────────────────────


def test_update_omni_tx_sets_button_text_active(app):
    """T3 (AC3-AC5): update_omni_tx(True) setzt Button-Label
    'OMNI CQ (aktiv)'. Mike sieht damit eindeutig ob OMNI aktiv ist."""
    from ui.control_panel import ControlPanel
    panel = ControlPanel()
    panel.update_omni_tx(True)
    assert panel.btn_omni_cq.text() == "OMNI CQ (aktiv)"


def test_update_omni_tx_sets_button_text_inactive(app):
    """T3b: update_omni_tx(False) setzt Button-Label 'OMNI CQ'."""
    from ui.control_panel import ControlPanel
    panel = ControlPanel()
    panel.update_omni_tx(True)   # erst auf aktiv
    panel.update_omni_tx(False)  # dann zurueck
    assert panel.btn_omni_cq.text() == "OMNI CQ"


# ─────────────────────────────────────────────────────────────────────
# T7 — qso_panel.add_listening Format (Commit 3)
# ─────────────────────────────────────────────────────────────────────


def test_add_listening_format_even_slot(app):
    """T7 (AC9): add_listening schreibt 'HH:MM:SS [E] ← Horche …' bei
    Even-Slot. Format konsistent mit add_rx."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_listening(slot_start_ts=1778320500.0, tx_even=True)
    text = panel.log_view.toPlainText()
    assert "[E]" in text
    assert "Horche" in text


def test_add_listening_format_odd_slot(app):
    """T7b: Odd-Slot zeigt [O]."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_listening(slot_start_ts=1778320515.0, tx_even=False)
    text = panel.log_view.toPlainText()
    assert "[O]" in text
    assert "Horche" in text


def test_add_listening_uses_slot_start_ts_not_now(app):
    """T7c: UTC-Zeit kommt aus slot_start_ts, nicht aus time.time().
    Pattern-konsistent mit add_tx/add_rx."""
    import time as _t
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    # Definierter Timestamp: 1778320500 = 09:55:00 UTC (modulo 15)
    ts = 1778320500.0
    expected_utc = _t.strftime("%H:%M:%S", _t.gmtime(ts))
    panel.add_listening(slot_start_ts=ts, tx_even=True)
    text = panel.log_view.toPlainText()
    assert expected_utc in text


# ─────────────────────────────────────────────────────────────────────
# T6 — RX-Slot-Skip ruft add_listening (Commit 3)
# ─────────────────────────────────────────────────────────────────────


def test_rx_slot_skip_calls_add_listening(app, omni_fresh):
    """T6 (AC8): _on_send_message bei OMNI-RX-Slot-Skip ruft
    qso_panel.add_listening. Lebenszeichen in stillen Slots."""
    from ui.mw_qso import QSOMixin

    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._omni_skip_state_change = False

    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    omni.advance()  # Pos 1
    omni.advance()  # Pos 2 = RX → should_tx returnt (False, None)

    stub = MagicMock()
    stub.qso_sm = sm
    stub.encoder = MagicMock()
    stub._omni_tx = omni
    stub._has_sent_cq = False
    stub.timer = MagicMock(cycle_duration=15.0)
    stub.qso_panel = MagicMock()
    stub.presence_can_tx = MagicMock(return_value=True)

    bound = QSOMixin._on_send_message.__get__(stub, type(stub))
    bound("CQ DA1MHH JO31")

    # add_listening wurde gerufen mit (slot_start_ts, is_even)
    stub.qso_panel.add_listening.assert_called_once()
    args = stub.qso_panel.add_listening.call_args
    # Erstes Arg: float Slot-Start-Timestamp
    assert isinstance(args[0][0], float)
    # Zweites Arg: bool tx_even
    assert isinstance(args[0][1], bool)
    # qso_sm._omni_skip_state_change wurde gesetzt (RX-Skip-Flag)
    assert sm._omni_skip_state_change is True
    # Encoder NICHT gerufen (TX skipped)
    stub.encoder.transmit.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# T9 — _on_omni_stopped ruft timer.stop() (Commit 1+2 Integration)
# ─────────────────────────────────────────────────────────────────────


def test_omni_stop_calls_pretrigger_timer_stop(app, omni_fresh):
    """T9 (AC11/AC14-AC16): _on_omni_stopped cancelt pending QTimer
    fuer ALLE Stop-Reasons. Damit greift Mode/Band/RX-Mode-Wechsel
    automatisch (laufen alle ueber omni_stopped-Signal)."""
    from ui.main_window import MainWindow

    # Mock des MainWindow-_on_omni_stopped-Slots (zu tief verschachtelt
    # für direkten Stub) — wir testen ueber das Signal-Pattern statt-
    # dessen mit einem reduzierten Stub.
    from PySide6.QtCore import QTimer

    stub = MagicMock()
    stub._omni_pretrigger_timer = MagicMock(spec=QTimer)
    stub._omni_pretriggered = True  # vorher gesetzt
    stub._omni_was_active_pre_qso = True  # vorher
    stub.qso_sm = MagicMock(cq_mode=True)
    stub.control_panel = MagicMock()

    # MainWindow._on_omni_stopped binden
    bound = MainWindow._on_omni_stopped.__get__(stub, type(stub))
    bound("manual_halt")

    # Timer.stop wurde gerufen
    stub._omni_pretrigger_timer.stop.assert_called_once()
    # Pretriggered-Flag invalidiert
    assert stub._omni_pretriggered is False
    # Pre-QSO-Flag invalidiert
    assert stub._omni_was_active_pre_qso is False


def test_omni_stop_works_for_all_stop_reasons(app, omni_fresh):
    """T9b: Stop-Reason ist egal — alle laufen ueber den selben Slot.
    Verifiziert dass mode/band/rx_mode/totmann/easter_egg/superseded
    alle den Timer canceln."""
    from ui.main_window import MainWindow
    from PySide6.QtCore import QTimer

    reasons = ["manual_halt", "ft_mode_change", "band_change",
               "rx_mode_change", "totmann_expired", "easter_egg_off",
               "superseded"]

    for reason in reasons:
        stub = MagicMock()
        stub._omni_pretrigger_timer = MagicMock(spec=QTimer)
        stub._omni_pretriggered = True
        stub._omni_was_active_pre_qso = True
        stub.qso_sm = MagicMock(cq_mode=True)
        stub.control_panel = MagicMock()

        bound = MainWindow._on_omni_stopped.__get__(stub, type(stub))
        bound(reason)

        stub._omni_pretrigger_timer.stop.assert_called_once(), (
            f"Timer-Stop fehlt für Reason {reason}")


def test_update_omni_tx_button_text_synced_with_omega_symbol(app):
    """T3c: Button-Text + _omni_active-Flag werden synchron im selben
    update_omni_tx-Aufruf gesetzt — kein State-Drift.

    Note: isVisible() greift im offscreen-Modus nicht zuverlaessig
    (Parent nicht visible). Wir pruefen statt dessen das interne
    _omni_active-Flag das von update_omni_tx gesetzt wird.
    """
    from ui.control_panel import ControlPanel
    panel = ControlPanel()
    # Initial: inaktiv
    assert panel.btn_omni_cq.text() == "OMNI CQ"
    # Aktiv
    panel.update_omni_tx(True)
    assert panel.btn_omni_cq.text() == "OMNI CQ (aktiv)"
    assert panel._omni_active is True
    # Wieder inaktiv
    panel.update_omni_tx(False)
    assert panel.btn_omni_cq.text() == "OMNI CQ"
    assert panel._omni_active is False
