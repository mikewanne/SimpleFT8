#!/usr/bin/env python3
"""Tests fuer v0.94 KALIBRIEREN-Button RX-Modus-spezifische Pipeline.

- Normal-Modus: nur Phase 2 (Gain), kein _pending_dx_diversity-Flag.
- Diversity Standard/DX: Phase 2 + Phase 3 (via _pending_dx_diversity).
- Cancel-Pfad: _on_dx_tune_rejected resetet die Pending-Flags.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_self(*, rx_mode="normal", scoring_mode="normal"):
    fake_self = MagicMock()
    fake_self._rx_mode = rx_mode
    fake_self._diversity_ctrl = MagicMock()
    fake_self._diversity_ctrl.scoring_mode = scoring_mode
    # Pending-Flags Default
    fake_self._pending_dx_diversity = False
    fake_self._pending_diversity_scoring = None
    return fake_self


# ── KALIBRIEREN je nach RX-Modus ────────────────────────────────────────────


def test_kalibrieren_normal_only_phase2():
    """Normal-Modus: KALIBRIEREN → nur Phase 2, kein Pending-Flag."""
    from ui.mw_radio import RadioMixin
    fake_self = _make_self(rx_mode="normal")
    RadioMixin._handle_dx_tuning(fake_self)
    assert fake_self._pending_dx_diversity is False, \
        "Normal-Modus darf _pending_dx_diversity NICHT setzen"
    fake_self._start_dx_tuning.assert_called_once_with(scoring_mode="stations")


def test_kalibrieren_diversity_standard_full_pipeline():
    """Diversity Standard: Phase 2 (gain=stations) + Phase 3 Pending-Flag."""
    from ui.mw_radio import RadioMixin
    fake_self = _make_self(rx_mode="diversity", scoring_mode="normal")
    RadioMixin._handle_dx_tuning(fake_self)
    assert fake_self._pending_dx_diversity is True
    assert fake_self._pending_diversity_scoring == "normal"
    fake_self._start_dx_tuning.assert_called_once_with(scoring_mode="stations")


def test_kalibrieren_diversity_dx_full_pipeline():
    """Diversity DX: Phase 2 (gain=snr) + Phase 3 Pending mit dx-Scoring."""
    from ui.mw_radio import RadioMixin
    fake_self = _make_self(rx_mode="diversity", scoring_mode="dx")
    RadioMixin._handle_dx_tuning(fake_self)
    assert fake_self._pending_dx_diversity is True
    assert fake_self._pending_diversity_scoring == "dx"
    fake_self._start_dx_tuning.assert_called_once_with(scoring_mode="snr")


# ── Cancel-Pfad ─────────────────────────────────────────────────────────────


def test_cancel_resets_pending_flags():
    """_on_dx_tune_rejected setzt _pending_dx_diversity wieder auf False."""
    from ui.mw_radio import RadioMixin
    fake_self = _make_self(rx_mode="diversity", scoring_mode="dx")
    fake_self._pending_dx_diversity = True
    fake_self._pending_diversity_scoring = "dx"
    fake_self.encoder = MagicMock()
    fake_self.encoder.is_transmitting = False
    fake_self.radio = MagicMock()
    fake_self.radio.ip = "192.168.1.68"
    RadioMixin._on_dx_tune_rejected(fake_self)
    assert fake_self._pending_dx_diversity is False, \
        "Cancel muss _pending_dx_diversity zuruecksetzen — sonst startet "\
        "Phase 3 beim naechsten Diversity-Aktivieren ungewollt"
    assert fake_self._pending_diversity_scoring is None
    assert fake_self._dx_tune_dialog is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
