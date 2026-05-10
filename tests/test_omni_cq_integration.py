"""Integration-Tests fuer P4.OMNI-NEUBAU C6 — Anschluss main_window/mw_qso/mw_cycle.

Deckt V3 §5 I1-I14 ab. Ohne komplettes MainWindow-Init: wir bauen einen
Fake-MainWindow mit den OMNI-relevanten Attributen und rufen die
ungebundenen Mixin/MainWindow-Methoden direkt auf.

V5 (10.05.2026): OmniCQ ist signal-basiert (kein Worker-Thread mehr) —
kein Boundary-Mock noetig. Tests rufen die Public-API direkt auf.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.omni_cq import OmniCQ  # noqa: E402
from core.qso_state import QSOStateMachine, QSOState  # noqa: E402
from core.message import FT8Message  # noqa: E402
from ui.mw_qso import QSOMixin  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.mw_cycle import CycleMixin  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# Fake-MainWindow Helper
# ---------------------------------------------------------------------------
class _FakeMW(QSOMixin, CycleMixin):
    """Schlankes MW-Stub mit allen Attributen die die OMNI-Pfade lesen.

    Erbt QSOMixin + CycleMixin sodass _pause_omni_if_active /
    _maybe_resume_omni / on_message_decoded direkt verfuegbar sind.
    """
    pass


def _make_fake_mw(app, callsign: str = "DA1MHH",
                  locator: str = "JN58") -> _FakeMW:
    mw = _FakeMW()

    # Encoder Mock — transmit returnt True (Slot akzeptiert).
    mw.encoder = MagicMock()
    mw.encoder.transmit = MagicMock(return_value=True)
    mw.encoder.tx_even = None
    mw.encoder.audio_freq_hz = 1500
    mw.encoder.is_transmitting = False
    mw.encoder.abort = MagicMock()

    # Diversity-Controller Mock — get_free_cq_freq=1500 (Default).
    mw._diversity_ctrl = MagicMock()
    mw._diversity_ctrl.get_free_cq_freq = MagicMock(return_value=1500)

    # Timer Mock — FT8 Cycle 15s, aktuell odd.
    mw.timer = MagicMock()
    mw.timer.cycle_duration = 15.0
    mw.timer.is_even_cycle = MagicMock(return_value=False)

    # Settings Mock.
    mw.settings = MagicMock()
    mw.settings.callsign = callsign
    mw.settings.locator = locator
    mw.settings.band = "20m"

    # Qso-State-Machine — echte Instanz.
    mw.qso_sm = QSOStateMachine(callsign, locator)

    # Auto-Hunt Mock.
    mw._auto_hunt = MagicMock()
    mw._auto_hunt.active = False
    mw._auto_hunt.stop_auto_hunt = MagicMock()
    mw._auto_hunt.start_auto_hunt = MagicMock()
    mw._auto_hunt.on_manual_qso_end = MagicMock()
    # _on_btn_auto_hunt_toggled ruft self._on_auto_hunt_polling_tick().
    mw._on_auto_hunt_polling_tick = MagicMock()

    # Control-Panel Mock.
    mw.control_panel = MagicMock()
    mw.control_panel.btn_omni_cq = MagicMock()
    mw.control_panel.btn_omni_cq.blockSignals = MagicMock()
    mw.control_panel.btn_omni_cq.setChecked = MagicMock()
    mw.control_panel.btn_omni_cq.isChecked = MagicMock(return_value=False)
    mw.control_panel.btn_auto_hunt = MagicMock()
    mw.control_panel.update_omni_tx = MagicMock()
    mw.control_panel.set_cq_active = MagicMock()

    # Statusbar Mock — _on_btn_omni_cq_toggled / _update_statusbar nutzen das.
    mw.statusBar = MagicMock(return_value=MagicMock())
    mw._update_statusbar = MagicMock()

    # QSO-Panel Mock — _on_omni_slot_action nutzt add_listening.
    mw.qso_panel = MagicMock()
    mw.qso_panel.add_listening = MagicMock()
    mw.qso_panel.add_info = MagicMock()

    # RX-Panel Mock.
    mw.rx_panel = MagicMock()
    mw.rx_panel._rx_active = True
    mw.rx_panel.set_active_call = MagicMock()

    # OMNI-CQ — echte Instanz (V5 signal-basiert, kein Worker-Mock noetig).
    mw._omni_cq = OmniCQ(
        encoder=mw.encoder,
        diversity_ctrl=mw._diversity_ctrl,
        timer=mw.timer,
        my_call=callsign,
        my_grid=locator,
    )
    # MainWindow connectet im Init omni_stopped → _on_omni_stopped. Wir
    # bilden das nach (HALT-Test braucht das, sonst wird Pre-QSO-Flag
    # nicht via _on_omni_stopped resettet).
    mw._omni_cq.omni_stopped.connect(
        lambda r: MainWindow._on_omni_stopped(mw, r)
    )
    # Lifecycle-Flags & Felder die OMNI-Pfade lesen.
    mw._omni_was_active_pre_qso = False
    mw._last_qso_tx_even = None
    mw._pending_station_click = None
    mw._has_sent_cq = False
    mw._auto_hunt_polling_timer = MagicMock()
    mw._radio = MagicMock()
    mw._auto_hunt_cooldown_timer = MagicMock()
    mw._auto_hunt_cooldown_seconds = 0
    mw._easter_egg_active = False
    mw._active_qso_targets = set()
    mw.radio = MagicMock()
    mw.radio.ip = ""
    mw._rx_mode = "diversity"
    mw.decoder = MagicMock()
    mw.decoder.priority_call = ""

    return mw


def _make_msg(caller: str = "DK5ON",
              target: str = "DA1MHH",
              raw: str | None = None,
              tx_even: bool = True,
              snr: int = -10) -> FT8Message:
    """Minimaler FT8Message-Mock fuer Listener-Tests."""
    msg = MagicMock(spec=FT8Message)
    msg.caller = caller
    msg.target = target
    msg.raw = raw or f"{target} {caller} JN58"
    msg.snr = snr
    msg.freq_hz = 1500
    msg.is_grid = True
    msg.is_73 = False
    msg.is_rr73 = False
    msg.grid_or_report = "JN58"
    msg._tx_even = tx_even
    msg._slot_start_ts = time.time()
    return msg


# ===========================================================================
# I1 — Toggle-Button startet OMNI
# ===========================================================================
def test_toggle_button_starts_omni(app):
    mw = _make_fake_mw(app)
    assert mw._omni_cq.is_active() is False
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    try:
        assert mw._omni_cq.is_active() is True
        mw.control_panel.update_omni_tx.assert_called_with(True)
    finally:
        mw._omni_cq.stop("test_cleanup")


# ===========================================================================
# I2 — Toggle-Button stoppt OMNI mit reason="manual_halt"
# ===========================================================================
def test_toggle_button_stops_omni_manual_halt(app):
    mw = _make_fake_mw(app)
    captured: list[str] = []
    mw._omni_cq.omni_stopped.connect(lambda r: captured.append(r))
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    MainWindow._on_btn_omni_cq_toggled(mw, False)
    assert captured == ["manual_halt"]
    assert mw._omni_cq.is_active() is False


# ===========================================================================
# I3, I4, I5 — Stop-Trigger aus mw_radio kommen in C7. Hier bestaetigen
# wir nur dass omni_cq.stop() mit dem richtigen reason die UI-Slots korrekt
# triggert.
# ===========================================================================
@pytest.mark.parametrize(
    "reason",
    ["band_change", "mode_change", "rx_mode_change"],
)
def test_external_stop_clears_omni(app, reason):
    mw = _make_fake_mw(app)
    captured: list[str] = []
    mw._omni_cq.omni_stopped.connect(lambda r: captured.append(r))
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    mw._omni_cq.stop(reason)
    assert captured == [reason]
    assert mw._omni_cq.is_active() is False


# ===========================================================================
# I6 — Listener-Pfad pausiert OMNI + setzt encoder.tx_even (R1 R2!)
# ===========================================================================
def test_listener_pauses_omni_and_sets_tx_even(app):
    mw = _make_fake_mw(app)
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    try:
        # Antwort an uns mit tx_even=True (= sie senden Even, wir muessen Odd)
        msg = _make_msg(tx_even=True)
        CycleMixin.on_message_decoded(mw, msg)
        # OMNI ist pausiert
        assert mw._omni_cq.is_paused() is True
        # encoder.tx_even = not their_even = not True = False (Odd)
        assert mw.encoder.tx_even is False
        # qso_state ist im Hunt-State (TX_CALL)
        assert mw.qso_sm.state == QSOState.TX_CALL
        # _omni_was_active_pre_qso wurde im _pause_omni_if_active-Helper gesetzt
        assert mw._omni_was_active_pre_qso is True
    finally:
        mw._omni_cq.stop("test_cleanup")


# ===========================================================================
# I7 — _maybe_resume_omni nach QSO-Ende waehlt Block nach last_qso_tx_even
# ===========================================================================
def test_qso_complete_resumes_omni_keeps_parity(app):
    """P7.OMNI-SIMPLIFY: Resume nach QSO bewahrt _cq_tx_even (kein Block-Wechsel mehr).

    last_was_even-Argument wird ignoriert. Sync via Re-Mess (Such-Counter),
    nicht via Resume.
    """
    mw = _make_fake_mw(app)
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    try:
        mw._omni_cq._cq_tx_even = True   # OMNI war auf Even
        mw._omni_cq.pause()
        mw._omni_was_active_pre_qso = True
        mw._last_qso_tx_even = True
        QSOMixin._maybe_resume_omni(mw)
        # OMNI aktiv + Paritaet bleibt Even (nicht durch Block-Logik getoggelt)
        assert mw._omni_cq.is_active() is True
        assert mw._omni_cq.is_paused() is False
        assert mw._omni_cq._cq_tx_even is True   # bleibt Even
        # Flag zurueckgesetzt
        assert mw._omni_was_active_pre_qso is False
    finally:
        mw._omni_cq.stop("test_cleanup")


# ===========================================================================
# I8 — Nicht-leere Caller-Queue: nimm naechsten Anrufer, OMNI bleibt pausiert
# ===========================================================================
def test_caller_queue_pops_via_mw_qso_keeps_omni_paused(app):
    mw = _make_fake_mw(app)
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    try:
        mw._omni_cq.pause()
        mw._omni_was_active_pre_qso = True
        # Caller-Queue mit einem wartenden Anrufer fuellen
        next_caller = _make_msg(caller="EA8XX", tx_even=False)
        mw.qso_sm._caller_queue = [next_caller]
        QSOMixin._maybe_resume_omni(mw)
        # OMNI bleibt pausiert (nicht active=True kommt erst nach QSO-Ende)
        assert mw._omni_cq.is_paused() is True
        assert mw._omni_was_active_pre_qso is True   # bleibt — naechstes QSO
        # Queue ist leer (popped)
        assert mw.qso_sm._caller_queue == []
        # qso_state hat das naechste QSO gestartet
        assert mw.qso_sm.state == QSOState.TX_CALL
        assert mw.qso_sm.qso.their_call == "EA8XX"
        # Slot-Paritaet: their_even=False -> wir senden Even
        assert mw.encoder.tx_even is True
    finally:
        mw._omni_cq.stop("test_cleanup")


# ===========================================================================
# I9 — qso_state.cq_mode wird waehrend OMNI NICHT gesetzt (AC12)
# ===========================================================================
def test_no_cq_mode_during_omni(app):
    mw = _make_fake_mw(app)
    assert mw.qso_sm.cq_mode is False
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    try:
        # OMNI ist aktiv, aber qso_state.cq_mode bleibt False
        assert mw._omni_cq.is_active() is True
        assert mw.qso_sm.cq_mode is False
    finally:
        mw._omni_cq.stop("test_cleanup")


# ===========================================================================
# I10 — HALT (_on_cancel) stoppt OMNI + reset _omni_was_active_pre_qso (R4)
# ===========================================================================
def test_halt_stops_omni_and_clears_pre_qso_flag(app):
    mw = _make_fake_mw(app)
    captured: list[str] = []
    mw._omni_cq.omni_stopped.connect(lambda r: captured.append(r))
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    mw._omni_was_active_pre_qso = True   # simuliere mid-QSO
    QSOMixin._on_cancel(mw)
    assert captured == ["manual_halt"]
    assert mw._omni_cq.is_active() is False
    assert mw._omni_was_active_pre_qso is False
    assert mw._last_qso_tx_even is None


# ===========================================================================
# I11 — Auto-Hunt-Toggle stoppt OMNI mit reason "superseded" (AC11c)
# ===========================================================================
def test_auto_hunt_toggle_stops_omni_superseded(app):
    mw = _make_fake_mw(app)
    captured: list[str] = []
    mw._omni_cq.omni_stopped.connect(lambda r: captured.append(r))
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    # Auto-Hunt-Toggle (checked=True) — Coupling stoppt OMNI
    MainWindow._on_btn_auto_hunt_toggled(mw, True)
    assert captured == ["superseded"]
    assert mw._omni_cq.is_active() is False
    mw._auto_hunt.start_auto_hunt.assert_called_once()


# ===========================================================================
# I12 — OMNI-Toggle stoppt Auto-Hunt (gegenseitige Exklusivitaet, AC11c)
# ===========================================================================
def test_omni_toggle_stops_auto_hunt(app):
    mw = _make_fake_mw(app)
    mw._auto_hunt.active = True
    MainWindow._on_btn_omni_cq_toggled(mw, True)
    try:
        mw._auto_hunt.stop_auto_hunt.assert_called_once_with("superseded")
        assert mw._omni_cq.is_active() is True
    finally:
        mw._omni_cq.stop("test_cleanup")


# ===========================================================================
# I13 — RX-Slot emittet 'Horche...' (V2-L8)
# ===========================================================================
def test_omni_slot_action_no_listening_in_p7(app):
    """P7.OMNI-SIMPLIFY: _on_omni_slot_action ist no-op (kein RX-Branch mehr).

    OMNI emittet slot_action NUR bei TX-Slot in P7. RX-Anzeige (Horche)
    entfaellt — OMNI ist passiver CQ-Modus. add_listening wird NICHT mehr
    von OMNI gerufen.
    """
    mw = _make_fake_mw(app)
    # RX-Slot: kein add_listening
    MainWindow._on_omni_slot_action(mw, "RX-E", False, True)
    mw.qso_panel.add_listening.assert_not_called()
    # TX-Slot: auch kein add_listening (TX laeuft ueber tx_started -> add_tx)
    MainWindow._on_omni_slot_action(mw, "TX-E", True, True)
    mw.qso_panel.add_listening.assert_not_called()


# ===========================================================================
# I14 — _on_omni_stopped resettet _omni_was_active_pre_qso (R4)
# ===========================================================================
def test_omni_stopped_resets_was_active_pre_qso_flag(app):
    mw = _make_fake_mw(app)
    mw._omni_was_active_pre_qso = True
    mw._last_qso_tx_even = True
    MainWindow._on_omni_stopped(mw, "test_reason")
    assert mw._omni_was_active_pre_qso is False
    assert mw._last_qso_tx_even is None
    mw.control_panel.update_omni_tx.assert_called_with(False)
