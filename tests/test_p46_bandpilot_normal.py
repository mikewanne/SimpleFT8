"""P46 — Bandpilot Normal-Reintegration (v0.97.17).

Mike's Strategie-Wechsel 12.05.2026: P35-Bug-E (11.05.) zurueckgenommen.
Bandpilot darf jetzt auch in Normal aktiv werden + Normal als Target
empfehlen (3-Wege-Vergleich).

8 Tests:
- T1 Auto: current=normal → switch zu diversity_dx
- T2 Auto: current=diversity_dx → switch zu normal (vorher geblockt!)
- T3 Auto: current=normal, no_change → nichts
- T4 Manual: current=normal → Dialog
- T5 Manual: current=diversity_dx, top1=normal → Dialog, User waehlt normal
- T6 Auto: TX laeuft, target=normal → defer + tx_finished → wechselt
- T7 (R1-F4) Auto: current=normal, rec=None → Statusbar-Hinweis
- T8 (R1-F3) TX-pending: User wechselt Modus zwischenzeitlich → pending verworfen
"""

from unittest.mock import MagicMock

import pytest

from ui.mw_radio import RadioMixin


@pytest.fixture(scope="module")
def qapp():
    """Qt Application Instance — module-scoped."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _make_mock_self(*, mode: str, current: str | None, rec: dict | None,
                    is_transmitting: bool = False):
    """Mock-Objekt fuer self mit allen benoetigten Attributen."""
    self_mock = MagicMock()
    self_mock.settings.get = MagicMock(side_effect=lambda key, default=None:
                                       {"bandpilot_mode": mode}.get(key, default))
    self_mock._bandpilot.recommend.return_value = rec
    self_mock._current_rx_mode_string.return_value = current
    self_mock.encoder.is_transmitting = is_transmitting
    self_mock._bandpilot_pending = None
    self_mock._bandpilot_tx_connected = False
    self_mock._show_bandpilot_insufficient_data = MagicMock()
    self_mock._show_bandpilot_auto_toast = MagicMock()
    self_mock._show_bandpilot_manual_dialog = MagicMock(
        return_value=rec["top1"] if rec else None)
    self_mock._set_rx_mode_direct = MagicMock()
    self_mock._apply_bandpilot_auto = lambda b, h, r: \
        RadioMixin._apply_bandpilot_auto(self_mock, b, h, r)
    self_mock._apply_bandpilot_manual = lambda b, h, r, c: \
        RadioMixin._apply_bandpilot_manual(self_mock, b, h, r, c)
    return self_mock


# ── T1: Auto + current=normal → switch zu diversity_dx ─────────────────────


def test_auto_normal_to_diversity_dx():
    """P46: current=normal wird nicht mehr geblockt — switch laeuft durch."""
    rec = {
        "top1": "diversity_dx", "top1_mean": 50.0,
        "ranking": [("diversity_dx", 50.0), ("diversity_normal", 30.0),
                    ("normal", 10.0)],
        "decision": "switch", "decision_mode": "diversity_dx",
    }
    s = _make_mock_self(mode="auto", current="normal", rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is True, "Bandpilot sollte aktiv werden (P35-Bug-E zurueckgenommen)"
    s._set_rx_mode_direct.assert_called_once_with("diversity_dx")


# ── T2: Auto + target=normal → wechsel zu normal (vorher geblockt!) ──────


def test_auto_diversity_dx_to_normal():
    """P46: target=normal wird nicht mehr geblockt — switch zu normal laeuft."""
    rec = {
        "top1": "normal", "top1_mean": 50.0,
        "ranking": [("normal", 50.0), ("diversity_dx", 30.0),
                    ("diversity_normal", 10.0)],
        "decision": "switch", "decision_mode": "normal",
    }
    s = _make_mock_self(mode="auto", current="diversity_dx", rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is True
    s._set_rx_mode_direct.assert_called_once_with("normal")


# ── T3: Auto + current=normal, no_change → nichts ─────────────────────────


def test_auto_normal_no_change():
    """current=normal + top1=normal + no_change → kein Wechsel, kein Toast."""
    rec = {
        "top1": "normal", "top1_mean": 50.0,
        "ranking": [("normal", 50.0), ("diversity_dx", 30.0),
                    ("diversity_normal", 10.0)],
        "decision": "no_change", "decision_mode": "normal",
    }
    s = _make_mock_self(mode="auto", current="normal", rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is False
    s._set_rx_mode_direct.assert_not_called()
    s._show_bandpilot_auto_toast.assert_not_called()


# ── T4: Manual + current=normal → Dialog ──────────────────────────────────


def test_manual_normal_to_other():
    """Manual: current=normal + top1!=normal → Dialog erscheint."""
    rec = {
        "top1": "diversity_normal", "top1_mean": 30.0,
        "ranking": [("diversity_normal", 30.0), ("diversity_dx", 25.0),
                    ("normal", 10.0)],
        "decision": "switch", "decision_mode": "diversity_normal",
    }
    s = _make_mock_self(mode="manual", current="normal", rec=rec)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    s._show_bandpilot_manual_dialog.assert_called_once()
    # Dialog liefert top1 zurueck (default mock) → wechselt zu diversity_normal
    assert result is True
    s._set_rx_mode_direct.assert_called_once_with("diversity_normal")


# ── T5: Manual + User waehlt Normal → wechselt zu normal ─────────────────


def test_manual_other_to_normal():
    """Manual: top1=normal, User klickt Normal-Button → wechselt zu normal."""
    rec = {
        "top1": "normal", "top1_mean": 50.0,
        "ranking": [("normal", 50.0), ("diversity_dx", 30.0),
                    ("diversity_normal", 10.0)],
        "decision": "switch", "decision_mode": "normal",
    }
    s = _make_mock_self(mode="manual", current="diversity_dx", rec=rec)
    # Default: _show_bandpilot_manual_dialog returnt rec["top1"] = "normal"
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    s._show_bandpilot_manual_dialog.assert_called_once()
    assert result is True
    s._set_rx_mode_direct.assert_called_once_with("normal")


# ── T6: Auto + TX laeuft, target=normal → defer + tx_finished ────────────


def test_auto_normal_target_tx_pending():
    """Auto: TX laeuft + target=normal → pending gespeichert mit current."""
    rec = {
        "top1": "normal", "top1_mean": 50.0,
        "ranking": [("normal", 50.0), ("diversity_dx", 30.0),
                    ("diversity_normal", 10.0)],
        "decision": "switch", "decision_mode": "normal",
    }
    s = _make_mock_self(mode="auto", current="diversity_dx", rec=rec,
                        is_transmitting=True)
    # statusBar-Mock einbauen
    s.statusBar = MagicMock(return_value=MagicMock())
    s.encoder.tx_finished = MagicMock()
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is True
    # _set_rx_mode_direct NICHT direkt aufgerufen (TX laeuft → defer)
    s._set_rx_mode_direct.assert_not_called()
    # Pending-Tupel ist 5-elementig mit current als letztem
    assert s._bandpilot_pending is not None
    assert len(s._bandpilot_pending) == 5
    pending_band, _utc, _rec, target, pending_current = s._bandpilot_pending
    assert target == "normal"
    assert pending_current == "diversity_dx"


# ── T7 (R1-F4): Auto + current=normal + rec=None → Statusbar-Hinweis ──────


def test_normal_insufficient_data():
    """R1-F4: bei current=normal + rec=None → _show_bandpilot_insufficient_data."""
    s = _make_mock_self(mode="auto", current="normal", rec=None)
    result = RadioMixin._maybe_apply_bandpilot(s, "40m")
    assert result is False
    s._show_bandpilot_insufficient_data.assert_called_once()
    s._set_rx_mode_direct.assert_not_called()


# ── T8 (R1-F3): TX-pending verworfen wenn User Modus geaendert hat ─────────


def test_tx_pending_discarded_when_user_changed_mode():
    """R1-F3: User wechselt Modus waehrend TX → pending wird verworfen."""
    s = MagicMock()
    s._bandpilot_pending = ("40m", 13, {}, "normal", "diversity_dx")
    s.settings.band = "40m"  # Band unveraendert
    # User hat zwischenzeitlich manuell auf diversity_normal gewechselt
    s._current_rx_mode_string.return_value = "diversity_normal"
    s._set_rx_mode_direct = MagicMock()
    RadioMixin._on_bandpilot_tx_finished(s)
    # Pending sollte NICHT angewendet werden
    s._set_rx_mode_direct.assert_not_called()
    # Aber pending sollte gecleart sein (1× Versuch verbraucht)
    assert s._bandpilot_pending is None
