"""v0.99.4 — Einheitliche Bedienung über HALT + smartes HALT (Ruf/QSO).

- Modus-Wechsel immer über HALT (Buttons starten nur aus Ruhe).
- HALT smart: Ruf (kein Rapport) → sofort; QSO im Austausch → deferred (QSO läuft
  zu Ende, dann IDLE); 2× HALT → sofort hart abbrechen (Notausgang).
- DeepSeek-R1-Fix: disable_cq_resume() statt nur stop_cq() (sonst CQ-Wiederaufleben).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from core.qso_state import (
    QSOState, QSOStateMachine, QSO_IN_EXCHANGE_STATES,
)
from ui.mw_qso import QSOMixin


# ── Konstante: Ruf vs QSO-Abgrenzung ─────────────────────────────────────
def test_exchange_states_exclude_ruf_phases():
    """Ruf-Phasen (rufen, kein Rapport empfangen) NICHT „im Austausch"."""
    assert QSOState.TX_CALL not in QSO_IN_EXCHANGE_STATES
    assert QSOState.WAIT_REPORT not in QSO_IN_EXCHANGE_STATES
    assert QSOState.CQ_CALLING not in QSO_IN_EXCHANGE_STATES
    assert QSOState.CQ_WAIT not in QSO_IN_EXCHANGE_STATES
    # Austausch = Rapport empfangen → wird geloggt:
    assert QSOState.TX_REPORT in QSO_IN_EXCHANGE_STATES
    assert QSOState.WAIT_RR73 in QSO_IN_EXCHANGE_STATES
    assert QSOState.WAIT_73 in QSO_IN_EXCHANGE_STATES


# ── disable_cq_resume (DeepSeek-R1-Fix) ──────────────────────────────────
def test_disable_cq_resume_clears_all_sources():
    """Löscht cq_mode + _was_cq + caller_queue — reines stop_cq() reichte NICHT."""
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm._was_cq = True
    sm._caller_queue.append(MagicMock(caller="EA3XX"))
    sm.disable_cq_resume()
    assert sm.cq_mode is False
    assert sm._was_cq is False
    assert sm._caller_queue == []


def test_disable_cq_resume_keeps_running_qso_state():
    """Greift NICHT in den State ein → laufendes QSO läuft regulär zu Ende."""
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.WAIT_RR73
    sm.disable_cq_resume()
    assert sm.state == QSOState.WAIT_RR73   # unberührt


# ── _on_cancel Dispatcher-Routing ────────────────────────────────────────
def _disp_obj(armed, state):
    return SimpleNamespace(
        _halt_armed=armed,
        qso_sm=SimpleNamespace(state=state),
        _execute_full_halt=MagicMock(),
        _arm_deferred_halt=MagicMock(),
        qso_panel=MagicMock(),
    )


def test_on_cancel_ruf_executes_full_halt():
    """Ruf (WAIT_REPORT, kein Rapport) → sofort harter Stopp."""
    obj = _disp_obj(armed=False, state=QSOState.WAIT_REPORT)
    QSOMixin._on_cancel(obj)
    obj._execute_full_halt.assert_called_once()
    obj._arm_deferred_halt.assert_not_called()


def test_on_cancel_active_qso_arms_deferred():
    """Laufendes QSO (WAIT_RR73) → armieren (nicht hart abbrechen)."""
    obj = _disp_obj(armed=False, state=QSOState.WAIT_RR73)
    QSOMixin._on_cancel(obj)
    obj._arm_deferred_halt.assert_called_once()
    obj._execute_full_halt.assert_not_called()


def test_on_cancel_idle_executes_full_halt():
    """Nichts/nur Modus (IDLE) → sofort harter Stopp."""
    obj = _disp_obj(armed=False, state=QSOState.IDLE)
    QSOMixin._on_cancel(obj)
    obj._execute_full_halt.assert_called_once()


def test_on_cancel_second_press_forces_full_halt():
    """2× HALT (bereits armiert) → Notausgang: sofort hart abbrechen, auch im QSO."""
    obj = _disp_obj(armed=True, state=QSOState.WAIT_RR73)
    QSOMixin._on_cancel(obj)
    obj._execute_full_halt.assert_called_once()   # NICHT _arm_deferred_halt
    obj._arm_deferred_halt.assert_not_called()
    obj.qso_panel.add_info.assert_called()        # „HALT (2×)"-Meldung


# ── _arm_deferred_halt: Resume-Quellen still, QSO unberührt ───────────────
def test_arm_deferred_halt_silences_resume_sources():
    obj = SimpleNamespace(
        _halt_armed=False,
        _auto_hunt=MagicMock(active=True),
        _omni_cq=MagicMock(is_active=MagicMock(return_value=True)),
        qso_sm=MagicMock(),
        control_panel=MagicMock(),
        qso_panel=MagicMock(),
        statusBar=MagicMock(return_value=MagicMock()),
        _qso_pending_insert="stub",
        _deferred_insert_msg="stub",
    )
    QSOMixin._arm_deferred_halt(obj)
    assert obj._halt_armed is True
    obj._auto_hunt.stop_auto_hunt.assert_called_once_with("manual_halt")
    obj._omni_cq.stop.assert_called_once_with("manual_halt")
    obj.qso_sm.disable_cq_resume.assert_called_once()  # NICHT nur stop_cq
    assert obj._qso_pending_insert is None             # kein Einschub danach
    assert obj._deferred_insert_msg is None
    obj.control_panel.set_halt_armed.assert_called_once_with(True)


def test_execute_full_halt_resets_armed():
    """Harter HALT setzt das armiert-Flag + Button-Optik zurück."""
    obj = MagicMock()
    obj._halt_armed = True
    obj._auto_hunt = MagicMock(active=False)
    obj._omni_cq = MagicMock(is_active=MagicMock(return_value=False))
    obj.statusBar = MagicMock(return_value=MagicMock())
    QSOMixin._execute_full_halt(obj)
    assert obj._halt_armed is False
    obj.control_panel.set_halt_armed.assert_any_call(False)


# ── Armiert-Aufhebung bei IDLE ───────────────────────────────────────────
def test_state_change_to_idle_clears_armed():
    """Armiertes QSO endet (IDLE) → Flag + Button-Optik weg + Bestätigung."""
    obj = MagicMock()
    obj._halt_armed = True
    obj.decoder = MagicMock()
    obj.qso_sm = MagicMock(qso=None)
    obj.statusBar = MagicMock(return_value=MagicMock())
    QSOMixin._on_state_changed(obj, QSOState.IDLE)
    assert obj._halt_armed is False
    obj.control_panel.set_halt_armed.assert_called_with(False)
    obj.qso_panel.add_info.assert_called()


def test_state_change_to_idle_noop_when_not_armed():
    """Nicht armiert → IDLE-Wechsel ändert nichts an HALT-Optik."""
    obj = MagicMock()
    obj._halt_armed = False
    obj.decoder = MagicMock()
    obj.qso_sm = MagicMock(qso=None)
    QSOMixin._on_state_changed(obj, QSOState.IDLE)
    obj.control_panel.set_halt_armed.assert_not_called()
