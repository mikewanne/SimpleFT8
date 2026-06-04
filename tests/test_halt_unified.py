"""v0.99.6 — STOPP = ein zentraler Notstopp für alles.

„HALT heißt Notstopp" (Mike 04.06.2026): der Button „HALT" → „STOPP", und STOPP
(wie auch Auto-Hunt-Toggle-OFF und OMNI-Toggle-OFF) bricht SOFORT JEDE TX-Quelle
ab — kein Armieren/Vormerken mehr (v0.99.4-Deferred-Mechanik entfernt).

`_execute_full_halt` ist das Modul: Encoder-TX, CQ, QSO, OMNI, Auto-Hunt, TUNE-
Träger (🔴 Sicherheit), Einmess-Dialog und Diversity-Gain-Mess-Lock.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from core.qso_state import QSOState, QSOStateMachine
from ui.mw_qso import QSOMixin


# ── Armier-Mechanik ist KOMPLETT entfernt ────────────────────────────────
def test_armier_mechanik_entfernt():
    """Die v0.99.4-Deferred-Symbole existieren nicht mehr."""
    import core.qso_state as qs
    assert not hasattr(qs, "QSO_IN_EXCHANGE_STATES")
    assert not hasattr(QSOStateMachine, "disable_cq_resume")
    assert not hasattr(QSOMixin, "_arm_deferred_halt")


# ── _on_cancel ist nur noch ein dünner Wrapper auf _execute_full_halt ────
def test_on_cancel_delegates_to_execute_full_halt():
    """Kein Dispatcher mehr — _on_cancel ruft IMMER sofort _execute_full_halt."""
    obj = SimpleNamespace(_execute_full_halt=MagicMock())
    QSOMixin._on_cancel(obj)
    obj._execute_full_halt.assert_called_once()


# ── Helper: obj mit allen Attributen die _execute_full_halt anfasst ──────
def _halt_obj(tune_active=False, dx_dialog=None, gain_locked=False,
              auto_hunt_active=False, omni_active=False):
    return SimpleNamespace(
        _active_qso_targets=MagicMock(),
        rx_panel=MagicMock(),
        _abort_active_tx=MagicMock(),
        _qso_pending_insert="stub",
        _deferred_insert_msg="stub",
        qso_sm=MagicMock(),
        control_panel=MagicMock(),
        _auto_hunt=MagicMock(active=auto_hunt_active),
        _omni_cq=MagicMock(is_active=MagicMock(return_value=omni_active)),
        _tune_active=tune_active,
        _tune_stop=MagicMock(),
        _dx_tune_dialog=dx_dialog,
        _gain_measure_locked=gain_locked,
        _set_gain_measure_lock=MagicMock(),
        _last_qso_tx_even="stub",
        qso_panel=MagicMock(),
        _flush_auto_hunt_stop_msg=MagicMock(),
        statusBar=MagicMock(return_value=MagicMock()),
    )


# ── Die bekannten TX-Quellen ─────────────────────────────────────────────
def test_stops_encoder_cq_and_qso():
    obj = _halt_obj()
    QSOMixin._execute_full_halt(obj)
    obj._abort_active_tx.assert_called_once()
    obj.qso_sm.stop_cq.assert_called_once()
    obj.qso_sm.cancel.assert_called_once()
    # Einschub verworfen
    assert obj._qso_pending_insert is None
    assert obj._deferred_insert_msg is None


def test_stops_auto_hunt_when_active():
    obj = _halt_obj(auto_hunt_active=True)
    QSOMixin._execute_full_halt(obj)
    obj._auto_hunt.stop_auto_hunt.assert_called_with("manual_halt")


def test_stops_omni_when_active():
    obj = _halt_obj(omni_active=True)
    QSOMixin._execute_full_halt(obj)
    obj._omni_cq.stop.assert_called_with("manual_halt")


# ── NEU v0.99.6: die TX-Quellen außerhalb des Encoder-Pfads ──────────────
def test_stops_tune_carrier_when_active():
    """🔴 Sicherheit: aktiver TUNE-Träger MUSS abgeschaltet werden."""
    obj = _halt_obj(tune_active=True)
    QSOMixin._execute_full_halt(obj)
    obj._tune_stop.assert_called_once_with(None)


def test_skips_tune_when_inactive():
    """Kein TUNE aktiv → _tune_stop NICHT rufen (idempotent/no-op)."""
    obj = _halt_obj(tune_active=False)
    QSOMixin._execute_full_halt(obj)
    obj._tune_stop.assert_not_called()


def test_closes_dx_tune_dialog_when_open():
    dlg = MagicMock()
    obj = _halt_obj(dx_dialog=dlg)
    QSOMixin._execute_full_halt(obj)
    dlg.reject.assert_called_once()


def test_no_dialog_reject_when_none():
    obj = _halt_obj(dx_dialog=None)
    QSOMixin._execute_full_halt(obj)  # darf nicht crashen


def test_releases_gain_measure_lock_when_locked():
    obj = _halt_obj(gain_locked=True)
    QSOMixin._execute_full_halt(obj)
    obj._set_gain_measure_lock.assert_called_once_with(False)


def test_skips_gain_lock_release_when_not_locked():
    obj = _halt_obj(gain_locked=False)
    QSOMixin._execute_full_halt(obj)
    obj._set_gain_measure_lock.assert_not_called()


# ── Keine Armier-Optik mehr ──────────────────────────────────────────────
def test_no_armed_button_optic():
    """STOPP ruft kein set_halt_armed mehr (Armier-Optik entfernt)."""
    obj = _halt_obj()
    QSOMixin._execute_full_halt(obj)
    obj.control_panel.set_halt_armed.assert_not_called()


# ── cancel() löscht _was_cq (DeepSeek-🟡) ────────────────────────────────
def test_cancel_clears_was_cq():
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm._was_cq = True
    sm.cancel()
    assert sm._was_cq is False


# ── Bug A: STOPP-Button darf NIE ausgegraut werden ───────────────────────
def test_stopp_button_never_disabled():
    """Keine state-/lock-abhängige `btn_cancel.setEnabled` mehr — ein Notstopp
    muss immer drückbar sein. War der Wurzel-Bug: bei Auto-Hunt/OMNI im IDLE-
    Zwischenzustand und während der Diversity-Messung wurde der Knopf grau →
    kein Notaus (Catch-22 mit „erst STOPP drücken")."""
    import inspect
    from ui import mw_radio
    for fn in (QSOMixin._on_state_changed,
               mw_radio.RadioMixin._set_cq_locked,
               mw_radio.RadioMixin._set_gain_measure_lock):
        assert "btn_cancel.setEnabled" not in inspect.getsource(fn), (
            f"{fn.__qualname__} darf btn_cancel nicht (mehr) sperren — "
            "STOPP ist ein Notstopp und muss immer drückbar bleiben")
