"""P94 (20.05.2026, v0.97.66) — Quick-73-Ignore für doppelte Anrufe.

Mike-Field-Test 20.05.2026 v0.97.65: 9A4AA ruft 4 min nach QSO-Ende
erneut mit Report → App startet komplettes neues QSO. Mike-Spec:
einmaliges 73 senden + 30 Min komplett ignorieren statt neues QSO.

Implementation: Pre-Filter `_p94_quick73_filter` in `ui/mw_cycle.py:
on_message_decoded` VOR OMNI-Block und `qso_sm.on_message_received`.
State-Machine bleibt unangetastet. Konstante `_QUICK73_WINDOW_S=1800`.

Test-Coverage:
- T1: Caller im Fenster + Report → Quick-73 + _quick73_sent + State NOT called
- T2: Caller NOCHMAL im Fenster → komplett ignoriert
- T3: Caller > 30 Min seit QSO → normaler Pfad, _quick73_sent leer
- T4: Caller nicht in _recent_logged_calls → normaler Pfad
- T5: Message NICHT an my_call → Filter passt durch
- T6: Message ohne Report/Grid (73/RR73) → Filter passt durch
- T7: State = WAIT_REPORT → Filter passt durch (kein Eingriff in QSO)
- T8: Auto-Hunt _RECENT_QSO_COOLDOWN_S ist 1800 (Konstanten-Test)
- T9: encoder.transmit returnt False → Set NICHT markiert
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_msg(*, caller="9A4AA", target="DA1MHH", is_report=True,
              is_grid=False, is_73=False, is_rr73=False, freq_hz=1500,
              tx_even=True):
    """Minimaler FT8Message-Mock."""
    msg = MagicMock()
    msg.caller = caller
    msg.target = target
    msg.is_report = is_report
    msg.is_grid = is_grid
    msg.is_73 = is_73
    msg.is_rr73 = is_rr73
    msg.freq_hz = freq_hz
    msg._tx_even = tx_even
    return msg


def _make_mixin(*, state=None, recent_qsos=None, quick73_sent=None,
                tx_returns=True):
    """Minimaler CycleMixin-Mock."""
    from ui.mw_cycle import CycleMixin
    from core.qso_state import QSOState
    obj = MagicMock(spec=CycleMixin)
    obj._p94_quick73_filter = CycleMixin._p94_quick73_filter.__get__(obj)
    obj.settings = MagicMock()
    obj.settings.callsign = "DA1MHH"
    obj.settings.band = "40m"
    obj.qso_sm = MagicMock()
    obj.qso_sm.state = state if state is not None else QSOState.IDLE
    obj._recent_logged_calls = recent_qsos if recent_qsos is not None else {}
    obj._quick73_sent = quick73_sent if quick73_sent is not None else set()
    obj.encoder = MagicMock()
    obj.encoder.audio_freq_hz = 1234
    obj.encoder.transmit = MagicMock(return_value=tx_returns)
    obj.encoder.tx_finished = MagicMock()
    obj.qso_panel = MagicMock()
    return obj


# ── T1: Caller im Fenster + Report → Quick-73 ────────────────────


def test_t1_caller_in_window_with_report_sends_quick73(app):
    now = time.time()
    recent = {("9A4AA", "40M"): now - 240.0}  # 4 min her
    obj = _make_mixin(recent_qsos=recent)
    msg = _make_msg(caller="9A4AA", target="DA1MHH", is_report=True)

    result = obj._p94_quick73_filter(msg)

    assert result is True, "Filter MUSS konsumieren"
    obj.encoder.transmit.assert_called_once()
    args, kwargs = obj.encoder.transmit.call_args
    assert args[0] == "9A4AA DA1MHH 73"
    assert kwargs["tx_even"] is False  # Gegenparität zu msg._tx_even=True
    assert kwargs["audio_freq_hz"] == 1500
    assert "9A4AA" in obj._quick73_sent
    obj.qso_panel.add_info.assert_called_once()
    info_text = obj.qso_panel.add_info.call_args[0][0]
    assert "9A4AA" in info_text
    assert "Sende 73" in info_text
    assert "4 min" in info_text


# ── T2: Caller NOCHMAL im Fenster → komplett ignoriert ──────────


def test_t2_caller_already_in_quick73_sent_full_ignore(app):
    now = time.time()
    recent = {("9A4AA", "40M"): now - 600.0}
    obj = _make_mixin(recent_qsos=recent, quick73_sent={"9A4AA"})
    msg = _make_msg(caller="9A4AA", target="DA1MHH", is_report=True)

    result = obj._p94_quick73_filter(msg)

    assert result is True, "Filter MUSS konsumieren"
    obj.encoder.transmit.assert_not_called()
    obj.qso_panel.add_info.assert_not_called()


# ── T3: Caller > 30 Min seit QSO → normaler Pfad ───────────────


def test_t3_caller_window_expired_normal_path(app):
    now = time.time()
    recent = {("9A4AA", "40M"): now - 2000.0}  # > 1800s
    obj = _make_mixin(recent_qsos=recent, quick73_sent={"9A4AA"})
    msg = _make_msg(caller="9A4AA", target="DA1MHH", is_report=True)

    result = obj._p94_quick73_filter(msg)

    assert result is False, "Filter MUSS durchpassen"
    obj.encoder.transmit.assert_not_called()
    assert "9A4AA" not in obj._quick73_sent, "Set MUSS aufgeräumt sein"


# ── T4: Caller nicht in recent_logged_calls → normaler Pfad ────


def test_t4_unknown_caller_normal_path(app):
    obj = _make_mixin(recent_qsos={})
    msg = _make_msg(caller="NEW1ABC", target="DA1MHH", is_report=True)

    result = obj._p94_quick73_filter(msg)

    assert result is False
    obj.encoder.transmit.assert_not_called()


# ── T5: Message NICHT an my_call → Filter passt durch ──────────


def test_t5_message_not_for_us_passes_through(app):
    now = time.time()
    recent = {("9A4AA", "40M"): now - 100.0}
    obj = _make_mixin(recent_qsos=recent)
    msg = _make_msg(caller="9A4AA", target="OTHER", is_report=True)

    result = obj._p94_quick73_filter(msg)

    assert result is False
    obj.encoder.transmit.assert_not_called()


# ── T6: Message ohne Report/Grid (73/RR73) → Filter passt durch ─


def test_t6_message_without_report_or_grid_passes(app):
    now = time.time()
    recent = {("9A4AA", "40M"): now - 100.0}
    obj = _make_mixin(recent_qsos=recent)
    msg = _make_msg(caller="9A4AA", target="DA1MHH",
                    is_report=False, is_grid=False, is_73=True)

    result = obj._p94_quick73_filter(msg)

    assert result is False
    obj.encoder.transmit.assert_not_called()


# ── T7: State = WAIT_REPORT → Filter passt durch ────────────────


def test_t7_state_in_active_qso_passes_through(app):
    from core.qso_state import QSOState
    now = time.time()
    recent = {("9A4AA", "40M"): now - 100.0}
    obj = _make_mixin(recent_qsos=recent, state=QSOState.WAIT_REPORT)
    msg = _make_msg(caller="9A4AA", target="DA1MHH", is_report=True)

    result = obj._p94_quick73_filter(msg)

    assert result is False, "Aktives QSO darf NICHT unterbrochen werden"
    obj.encoder.transmit.assert_not_called()


# ── T8: Auto-Hunt _RECENT_QSO_COOLDOWN_S = 1800 ─────────────────


def test_t8_auto_hunt_cooldown_is_1800(app):
    from core import auto_hunt
    assert auto_hunt._RECENT_QSO_COOLDOWN_S == 1800, (
        "P94: Auto-Hunt-Station-Cooldown muss 1800s (30 Min) sein")


# ── T9: encoder.transmit returnt False → Set NICHT markiert ────


def test_t9_encoder_busy_does_not_mark_set(app):
    now = time.time()
    recent = {("9A4AA", "40M"): now - 100.0}
    obj = _make_mixin(recent_qsos=recent, tx_returns=False)
    msg = _make_msg(caller="9A4AA", target="DA1MHH", is_report=True)

    result = obj._p94_quick73_filter(msg)

    assert result is True, "Anruf TROTZDEM konsumieren (kein QSO-Start)"
    obj.encoder.transmit.assert_called_once()
    assert "9A4AA" not in obj._quick73_sent, (
        "Bei Encoder-Busy NICHT markieren — nächster Slot darf nochmal versuchen")
    obj.qso_panel.add_info.assert_not_called()


# ── T10: CQ_WAIT State → Filter aktiv (Mike kann CQ rufen wenn 9A4AA antwortet) ─


def test_t10_cq_wait_state_filter_active(app):
    from core.qso_state import QSOState
    now = time.time()
    recent = {("9A4AA", "40M"): now - 100.0}
    obj = _make_mixin(recent_qsos=recent, state=QSOState.CQ_WAIT)
    msg = _make_msg(caller="9A4AA", target="DA1MHH", is_report=True)

    result = obj._p94_quick73_filter(msg)

    assert result is True
    obj.encoder.transmit.assert_called_once()


# ── T11: Constante _QUICK73_WINDOW_S = 1800 ─────────────────────


def test_t11_quick73_window_constant(app):
    from ui import mw_cycle
    assert mw_cycle._QUICK73_WINDOW_S == 1800, "P94: Fenster muss 30 Min sein"


# ── T12: Grid-Anruf (1. Anruf nach Aging) wird auch gefiltert ──


def test_t12_grid_message_also_filtered(app):
    now = time.time()
    recent = {("9A4AA", "40M"): now - 300.0}
    obj = _make_mixin(recent_qsos=recent)
    msg = _make_msg(caller="9A4AA", target="DA1MHH",
                    is_report=False, is_grid=True)

    result = obj._p94_quick73_filter(msg)

    assert result is True
    obj.encoder.transmit.assert_called_once()
    assert "9A4AA" in obj._quick73_sent
