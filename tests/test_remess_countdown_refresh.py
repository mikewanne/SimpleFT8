"""P83 Re-Mess-Countdown-Refresh (2026-05-23).

Mike-Bug 22.05.: dx_info-Label "noch X Stunden bis Re-Mess" updated
sich nur bei User-Aktionen (Band-/Modus-Wechsel) — bleibt stale waehrend
Stunden vergehen. Fix: pro Slot im _on_cycle_finished-Hook
_update_gain_status_display aufrufen.

Hier: Verifizieren dass der Cycle-Hook _update_gain_status_display
aufruft, und dass der rx_active-Guard weiter greift.
"""
from unittest.mock import MagicMock

from ui.mw_cycle import CycleMixin


def test_on_cycle_finished_refreshes_gain_status_display():
    """rx_active=True → _update_gain_status_display wird aufgerufen
    (zusaetzlich zum bestehenden qso_sm.on_decoder_finished)."""
    fake_self = MagicMock()
    fake_self.rx_panel._rx_active = True

    CycleMixin._on_cycle_finished(fake_self)

    fake_self.qso_sm.on_decoder_finished.assert_called_once()
    fake_self._update_gain_status_display.assert_called_once()


def test_on_cycle_finished_skips_when_rx_inactive():
    """rx_active=False (Guard) → weder QSO-State-Update noch
    Display-Refresh. Existierender Pfad bleibt unangetastet."""
    fake_self = MagicMock()
    fake_self.rx_panel._rx_active = False

    CycleMixin._on_cycle_finished(fake_self)

    fake_self.qso_sm.on_decoder_finished.assert_not_called()
    fake_self._update_gain_status_display.assert_not_called()


def test_call_order_state_before_display():
    """State-Maschine vor UI-Update — Pattern aus dem Cycle-Handler:
    `on_decoder_finished` wird VOR `_update_gain_status_display`
    aufgerufen, damit das Display den finalen State sieht."""
    fake_self = MagicMock()
    fake_self.rx_panel._rx_active = True
    call_order: list[str] = []
    fake_self.qso_sm.on_decoder_finished.side_effect = (
        lambda: call_order.append("on_decoder_finished")
    )
    fake_self._update_gain_status_display.side_effect = (
        lambda: call_order.append("_update_gain_status_display")
    )

    CycleMixin._on_cycle_finished(fake_self)

    assert call_order == [
        "on_decoder_finished",
        "_update_gain_status_display",
    ]
