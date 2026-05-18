"""P81 — Auto-Hunt-Stop-Meldung defern bis nach "✓ QSO komplett"

Mike-Field-Test 18.05.2026: Maus-Inaktivitaet 5 Min erreicht waehrend
aktives QSO (state=WAIT_73) → Stop-Meldung erschien VOR "✓ QSO komplett"
im Panel.

Fix (v0.97.53): Defer-Flag `_auto_hunt_stop_msg_pending`. Polling-Tick
prueft `_qso_active_for_msg_defer()` und defert die Meldung wenn QSO
laeuft. Flush in `_on_qso_confirmed_visual`, `_on_qso_timeout`, `_on_cancel`
(HALT-Pfad — R1-F1 ROT).

Tests T1-T8:
- T1: state ∈ {IDLE, TIMEOUT, CQ_CALLING, CQ_WAIT} → add_info SOFORT, Flag False.
- T2: state=WAIT_73 → KEIN add_info, Flag=True, stop_auto_hunt aufgerufen.
- T3: Flag=True → _on_qso_confirmed_visual → add_qso_complete + Stop-Msg + Flag=False.
- T4: Flag=True → _on_qso_timeout → add_timeout + Stop-Msg + Flag=False (Safety-Net).
- T5: Flag=True → Manueller Auto-Hunt-Restart → Flag=False, KEIN add_info (Geister-Schutz).
- T6: Flag=False → _on_qso_confirmed_visual → KEIN Stop-Msg (Doppel-Emit-Schutz).
- T7: state=TX_RR73 → polling-tick → Flag=True; danach Courtesy-Send-fertig → Flush.
- T8 (R1-F1 ROT): Flag=True → HALT (_on_cancel) → Stop-Msg + Flag=False.
"""

from unittest.mock import MagicMock, patch

import pytest


# ── T1 — kein-QSO-States: add_info SOFORT, KEIN Defer ─────────────────


@pytest.mark.parametrize("state_name", ["IDLE", "TIMEOUT", "CQ_CALLING", "CQ_WAIT"])
def test_t1_polling_tick_sofort_bei_kein_qso(state_name):
    """state ∈ {IDLE,TIMEOUT,CQ_CALLING,CQ_WAIT} → add_info SOFORT, Flag bleibt False."""
    from core.qso_state import QSOState
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300
    obj._auto_hunt = MagicMock(active=True)
    obj._auto_hunt_polling_timer = MagicMock()
    obj._auto_hunt_last_mouse_t = 0.0
    obj._auto_hunt_stop_msg_pending = False
    obj.qso_sm = MagicMock(state=getattr(QSOState, state_name))
    obj._qso_active_for_msg_defer = (
        lambda: mw_mod.MainWindow._qso_active_for_msg_defer(obj)
    )
    obj.qso_panel = MagicMock()
    obj.control_panel = MagicMock()

    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 301.0
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)

    obj._auto_hunt.stop_auto_hunt.assert_called_once_with("mouse_inactive_5min")
    obj.qso_panel.add_info.assert_called_once()
    assert obj._auto_hunt_stop_msg_pending is False


# ── T2 — aktives QSO: Defer-Flag, KEIN add_info ───────────────────────


@pytest.mark.parametrize(
    "state_name",
    ["WAIT_REPORT", "TX_REPORT", "WAIT_RR73", "TX_RR73", "WAIT_73", "TX_73_COURTESY"],
)
def test_t2_polling_tick_defert_bei_aktivem_qso(state_name):
    """state ∈ aktive QSO-States → Flag=True, KEIN add_info, stop_auto_hunt OK."""
    from core.qso_state import QSOState
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300
    obj._auto_hunt = MagicMock(active=True)
    obj._auto_hunt_polling_timer = MagicMock()
    obj._auto_hunt_last_mouse_t = 0.0
    obj._auto_hunt_stop_msg_pending = False
    obj.qso_sm = MagicMock(state=getattr(QSOState, state_name))
    obj._qso_active_for_msg_defer = (
        lambda: mw_mod.MainWindow._qso_active_for_msg_defer(obj)
    )
    obj.qso_panel = MagicMock()
    obj.control_panel = MagicMock()

    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 301.0
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)

    obj._auto_hunt.stop_auto_hunt.assert_called_once_with("mouse_inactive_5min")
    obj.qso_panel.add_info.assert_not_called()
    assert obj._auto_hunt_stop_msg_pending is True


# ── T3 — Flush via _on_qso_confirmed_visual ───────────────────────────


def test_t3_flush_via_confirmed_visual():
    """Flag=True → add_qso_complete + add_info(Stop-Msg) + Flag=False."""
    from ui import mw_qso

    obj = MagicMock()
    obj._auto_hunt_stop_msg_pending = True
    obj.qso_panel = MagicMock()
    obj._flush_auto_hunt_stop_msg = lambda: (
        setattr(obj, "_auto_hunt_stop_msg_pending", False),
        obj.qso_panel.add_info("⏸ Auto-Hunt gestoppt ..."),
    )

    qso_data = MagicMock(their_call="IZ1JLP")
    mw_qso.QSOMixin._on_qso_confirmed_visual(obj, qso_data)

    obj.qso_panel.add_qso_complete.assert_called_once_with("IZ1JLP")
    obj.qso_panel.add_info.assert_called_once()
    assert obj._auto_hunt_stop_msg_pending is False


# ── T4 — Flush via _on_qso_timeout (Safety-Net Hard-Timeout) ──────────


def test_t4_flush_via_qso_timeout():
    """Flag=True → add_timeout + add_info(Stop-Msg) + Flag=False."""
    from ui import mw_qso

    obj = MagicMock()
    obj._auto_hunt_stop_msg_pending = True
    obj._active_qso_targets = MagicMock()
    obj.rx_panel = MagicMock()
    obj.qso_panel = MagicMock()
    obj._auto_hunt = MagicMock(active=False)
    obj.qso_sm = MagicMock(cq_mode=False)
    obj._omni_cq = MagicMock()
    obj.control_panel = MagicMock()
    obj._maybe_resume_omni = MagicMock()
    obj._flush_auto_hunt_stop_msg = lambda: (
        setattr(obj, "_auto_hunt_stop_msg_pending", False),
        obj.qso_panel.add_info("⏸ Auto-Hunt gestoppt ..."),
    )

    mw_qso.QSOMixin._on_qso_timeout(obj, "IZ1JLP")

    obj.qso_panel.add_timeout.assert_called_once_with("IZ1JLP")
    obj.qso_panel.add_info.assert_called_once()
    assert obj._auto_hunt_stop_msg_pending is False


# ── T5 — Manueller Auto-Hunt-Restart cleart Flag SILENT ───────────────


def test_t5_manual_restart_clear_silent():
    """Flag=True → btn-toggled(True) → Flag=False, KEIN add_info."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._auto_hunt = MagicMock(active=False)
    obj._auto_hunt_stop_msg_pending = True
    obj.settings = MagicMock(band="40m")
    obj._swr_blocked_bands = set()
    obj._omni_cq = MagicMock(is_active=MagicMock(return_value=False))
    obj._auto_hunt_polling_timer = MagicMock()
    obj._on_auto_hunt_polling_tick = MagicMock()
    obj.qso_panel = MagicMock()
    obj.control_panel = MagicMock()

    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 100.0
        mw_mod.MainWindow._on_btn_auto_hunt_toggled(obj, True)

    assert obj._auto_hunt_stop_msg_pending is False
    obj.qso_panel.add_info.assert_not_called()  # Geister-Schutz: kein Emit!
    obj._auto_hunt.start_auto_hunt.assert_called_once_with(600)


# ── T6 — Flag=False → KEIN Doppel-Emit bei _on_qso_confirmed_visual ───


def test_t6_kein_doppel_emit():
    """Flag=False → add_qso_complete + KEIN add_info (kein Geister-Emit)."""
    from ui import mw_qso

    obj = MagicMock()
    obj._auto_hunt_stop_msg_pending = False
    obj.qso_panel = MagicMock()
    # Echter Flush — prueft Flag-Logik
    obj._flush_auto_hunt_stop_msg = lambda: (
        mw_qso.QSOMixin._on_qso_confirmed_visual.__globals__  # no-op marker
    )
    # Use real flush logic via MainWindow:
    from ui import main_window as mw_mod
    obj._flush_auto_hunt_stop_msg = (
        lambda: mw_mod.MainWindow._flush_auto_hunt_stop_msg(obj)
    )

    qso_data = MagicMock(their_call="DA1MHH")
    mw_qso.QSOMixin._on_qso_confirmed_visual(obj, qso_data)

    obj.qso_panel.add_qso_complete.assert_called_once_with("DA1MHH")
    obj.qso_panel.add_info.assert_not_called()


# ── T7 — vollstaendiger Lebenszyklus: defer → Visual-Flush ────────────


def test_t7_full_cycle_defer_then_flush():
    """state=TX_RR73 → polling-tick → Flag=True; danach Visual → Flush."""
    from core.qso_state import QSOState
    from ui import main_window as mw_mod
    from ui import mw_qso

    obj = MagicMock()
    obj._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300
    obj._auto_hunt = MagicMock(active=True)
    obj._auto_hunt_polling_timer = MagicMock()
    obj._auto_hunt_last_mouse_t = 0.0
    obj._auto_hunt_stop_msg_pending = False
    obj.qso_sm = MagicMock(state=QSOState.TX_RR73)
    obj._qso_active_for_msg_defer = (
        lambda: mw_mod.MainWindow._qso_active_for_msg_defer(obj)
    )
    obj.qso_panel = MagicMock()
    obj.control_panel = MagicMock()
    obj._flush_auto_hunt_stop_msg = (
        lambda: mw_mod.MainWindow._flush_auto_hunt_stop_msg(obj)
    )

    # Phase 1: polling-tick → Flag=True
    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 301.0
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)
    assert obj._auto_hunt_stop_msg_pending is True
    obj.qso_panel.add_info.assert_not_called()

    # Phase 2: Visual feuert → Flush
    qso_data = MagicMock(their_call="IZ1JLP")
    mw_qso.QSOMixin._on_qso_confirmed_visual(obj, qso_data)

    obj.qso_panel.add_qso_complete.assert_called_once_with("IZ1JLP")
    obj.qso_panel.add_info.assert_called_once()
    assert obj._auto_hunt_stop_msg_pending is False


# ── T8 — R1-F1 ROT: HALT-Pfad flusht deferred Meldung ─────────────────


def test_t8_halt_flushes_pending():
    """R1-F1 (ROT): Flag=True + HALT → add_info(Stop-Msg) + Flag=False.

    _on_cancel emittiert weder qso_timeout noch qso_confirmed_visual —
    ohne Flush wuerde die Meldung dauerhaft verloren gehen.
    """
    from ui import main_window as mw_mod
    from ui import mw_qso

    obj = MagicMock()
    obj._auto_hunt_stop_msg_pending = True
    obj._active_qso_targets = MagicMock()
    obj.rx_panel = MagicMock()
    obj._abort_active_tx = MagicMock()
    obj.qso_sm = MagicMock()
    obj.control_panel = MagicMock()
    obj._auto_hunt = MagicMock(active=False)
    obj._omni_cq = MagicMock(is_active=MagicMock(return_value=False))
    obj.qso_panel = MagicMock()
    obj.statusBar = MagicMock(return_value=MagicMock())
    obj._last_qso_tx_even = "stub"
    obj._flush_auto_hunt_stop_msg = (
        lambda: mw_mod.MainWindow._flush_auto_hunt_stop_msg(obj)
    )

    mw_qso.QSOMixin._on_cancel(obj)

    # HALT-Meldung im Panel + Stop-Msg via Flush
    assert obj.qso_panel.add_info.call_count == 2
    halt_call = obj.qso_panel.add_info.call_args_list[0]
    stop_call = obj.qso_panel.add_info.call_args_list[1]
    assert "HALT" in str(halt_call)
    assert "Auto-Hunt gestoppt" in str(stop_call)
    assert obj._auto_hunt_stop_msg_pending is False
