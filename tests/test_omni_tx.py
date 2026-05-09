"""OMNI-TX Unit-Tests — Stop-Reasons + disable-Wrapper.

Hinweis: Pattern-, Block-Switch- und Pause/Resume-Tests liegen jetzt in
``tests/test_p2_omni_redesign.py`` (P2.OMNI-REDESIGN v4.0, v0.95.23).

Diese Datei behaelt nur Tests die nicht in P2 gespiegelt sind:
- 7 Stop-Reason-Emit-Tests (parametrize)
- disable() → easter_egg_off Backwards-Compat

Run: ./venv/bin/python3 -m pytest tests/test_omni_tx.py -v
"""
from __future__ import annotations

import pytest


@pytest.fixture
def qapp():
    """QApplication-Singleton — Voraussetzung fuer Qt-Signal-Emit."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def omni_tx_fresh():
    """Reset OmniTX-Singleton zwischen Tests."""
    from core import omni_tx as _omni
    _omni._instance = None
    yield
    _omni._instance = None


# ─────────────────────────────────────────────────────────────────────────────
# Stop-Reason-Signal-Emit (7 Reasons via parametrize)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("reason", [
    "manual_halt", "band_change", "ft_mode_change", "rx_mode_change",
    "totmann_expired", "easter_egg_off", "superseded",
])
def test_omni_stopped_signal_emits_with_reason(qapp, omni_tx_fresh, reason):
    """omni_stopped(reason) wird bei jedem Stop fuer alle 7 Reasons emittiert."""
    from core.omni_tx import OmniTX
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    received = []
    omni.omni_stopped.connect(lambda r: received.append(r))

    omni.stop_omni_tx(reason)
    assert received == [reason]
    assert omni.active is False


# ─────────────────────────────────────────────────────────────────────────────
# disable() — Backwards-compat Wrapper
# ─────────────────────────────────────────────────────────────────────────────

def test_disable_delegates_to_stop_with_easter_egg_off(qapp, omni_tx_fresh):
    """disable() ist Backwards-compat Wrapper → stop_omni_tx('easter_egg_off')."""
    from core.omni_tx import OmniTX
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=True)
    received = []
    omni.omni_stopped.connect(lambda r: received.append(r))

    omni.disable()
    assert omni.active is False
    assert received == ["easter_egg_off"]


# ─────────────────────────────────────────────────────────────────────────────
# Initial-State + Stop-Cleanup (P2.OMNI-REDESIGN v4.0 API)
# ─────────────────────────────────────────────────────────────────────────────

def test_initial_state_inactive(qapp, omni_tx_fresh):
    """Frisch instanziierter OmniTX ist inaktiv, Block 1, slot_index 0."""
    from core.omni_tx import OmniTX
    omni = OmniTX()
    assert omni.active is False
    assert omni.block == 1
    assert omni._slot_index == 0
    assert omni.is_paused() is False


def test_stop_omni_tx_cleanup(qapp, omni_tx_fresh):
    """stop_omni_tx setzt active=False, slot_index=0, _paused=False."""
    from core.omni_tx import OmniTX
    omni = OmniTX()
    omni.start_with_parity_for_next_slot(next_is_even=False)
    omni.advance()
    omni.advance()
    omni.pause()
    assert omni._slot_index == 2
    assert omni.is_paused() is True

    omni.stop_omni_tx("manual_halt")
    assert omni.active is False
    assert omni._slot_index == 0
    assert omni.is_paused() is False
