"""OMNI-TX Unit-Tests (v0.78) — 5-Slot-Pattern, Block-Wechsel, Stop-Logik.

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
# Initial-State + Konstruktor-Defaults
# ─────────────────────────────────────────────────────────────────────────────

def test_initial_state_inactive(qapp, omni_tx_fresh):
    from core.omni_tx import OmniTX
    omni = OmniTX()
    assert omni.active is False
    assert omni.block == 1
    assert omni._cycle_count == 0
    assert omni._slot_index == 0
    assert omni._pending_switch is False


def test_default_block_cycles_is_80(qapp, omni_tx_fresh):
    """Plan v3.2: Default block_cycles ist 80, nicht 40."""
    from core.omni_tx import OmniTX
    omni = OmniTX()
    assert omni.block_cycles == 80


# ─────────────────────────────────────────────────────────────────────────────
# enable() / Aktivierung
# ─────────────────────────────────────────────────────────────────────────────

def test_enable_resets_state(qapp, omni_tx_fresh):
    from core.omni_tx import OmniTX
    omni = OmniTX()
    # Vorbedingung: dirty State
    omni._slot_index = 3
    omni.block = 2
    omni._cycle_count = 50
    omni._pending_switch = True

    omni.enable()
    assert omni.active is True
    assert omni._slot_index == 0
    assert omni.block == 1
    assert omni._cycle_count == 0
    assert omni._pending_switch is False


# ─────────────────────────────────────────────────────────────────────────────
# 5-Slot-Pattern Verifikation (should_tx)
# ─────────────────────────────────────────────────────────────────────────────

def test_5_slot_pattern_block1(qapp, omni_tx_fresh):
    """Block 1 (Even-First): TX(Even), TX(Odd), RX, RX, RX."""
    from core.omni_tx import OmniTX
    omni = OmniTX()
    omni.enable()
    # is_even=True ist hier Dummy — should_tx liefert anhand Slot+Block
    expected = [
        (True, True),   # Pos 0: TX Even
        (True, False),  # Pos 1: TX Odd
        (False, None),  # Pos 2: RX
        (False, None),  # Pos 3: RX
        (False, None),  # Pos 4: RX
    ]
    for pos, (exp_send, exp_target) in enumerate(expected):
        send, target = omni.should_tx()
        assert send == exp_send, f"Pos {pos}: expected send={exp_send}"
        assert target == exp_target, f"Pos {pos}: expected target_even={exp_target}"
        omni.advance(qso_active=False)


def test_5_slot_pattern_block2(qapp, omni_tx_fresh):
    """Block 2 (Odd-First): TX(Odd), TX(Even), RX, RX, RX."""
    from core.omni_tx import OmniTX
    omni = OmniTX()
    omni.enable()
    omni.block = 2
    expected = [
        (True, False),  # Pos 0: TX Odd
        (True, True),   # Pos 1: TX Even
        (False, None),
        (False, None),
        (False, None),
    ]
    for pos, (exp_send, exp_target) in enumerate(expected):
        send, target = omni.should_tx()
        assert send == exp_send, f"Pos {pos}: expected send={exp_send}"
        assert target == exp_target, f"Pos {pos}: expected target_even={exp_target}"
        omni.advance(qso_active=False)


# ─────────────────────────────────────────────────────────────────────────────
# Block-Wechsel-Logik
# ─────────────────────────────────────────────────────────────────────────────

def test_block_switch_after_block_cycles(qapp, omni_tx_fresh):
    """Counter erreicht block_cycles → Block-Wechsel (an Pos 0)."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=10)
    omni.enable()
    # 10 Zyklen → bei Pos 0 wieder, Counter reset, Block flipped
    for _ in range(10):
        omni.advance(qso_active=False)
    # Pattern-Laenge 5, 10 Zyklen = 2 voll → wieder Pos 0, Block sollte flippen
    # (10-Counter erreicht an Pos 4, _switch_block markiert _pending_switch,
    # naechster advance->Pos 0 ruft _do_switch_block)
    # Ein weiterer advance um pending zu resolven
    omni.advance(qso_active=False)
    assert omni.block == 2, f"Expected Block 2 nach 10 Zyklen, got Block {omni.block}"


def test_block_switch_at_position_0_only(qapp, omni_tx_fresh):
    """_pending_switch wartet bis slot_index == 0.

    block_cycles wird durch max(10, ...) immer auf >=10 geclampt.
    Mit 10 Zyklen erreicht der Counter block_cycles bei Pos (10 % 5) = 0,
    d.h. der Wechsel wuerde sofort erfolgen. Wir umgehen das indem wir
    block_cycles=11 setzen — Counter erreicht 11 bei Pos (11 % 5) = 1.
    """
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=11)
    omni.enable()
    # 11 advances → slot_index=1, count=11 → _switch_block, slot != 0 → pending
    for _ in range(11):
        omni.advance(qso_active=False)
    assert omni._pending_switch is True
    assert omni.block == 1, "Block sollte noch 1 sein bis Pos 0 erreicht"
    # Pos 1 → 2 → 3 → 4 (4 advances bis Pos 0)
    for _ in range(3):
        omni.advance(qso_active=False)
    assert omni.block == 1, "Pending soll bis Pos 0 warten"
    # Pos 4 → Pos 0 → _do_switch_block
    omni.advance(qso_active=False)
    assert omni.block == 2
    assert omni._pending_switch is False


# ─────────────────────────────────────────────────────────────────────────────
# QSO-Verhalten
# ─────────────────────────────────────────────────────────────────────────────

def test_qso_resets_counter_keeps_block(qapp, omni_tx_fresh):
    """on_qso_started → count=0, Block + pending bleiben unveraendert."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=10)
    omni.enable()
    omni.block = 2
    omni._cycle_count = 7
    omni._pending_switch = True

    omni.on_qso_started()
    assert omni._cycle_count == 0
    assert omni.block == 2
    assert omni._pending_switch is True


# ─────────────────────────────────────────────────────────────────────────────
# stop_omni_tx — Bug-Fix C6 (_pending_switch reset)
# ─────────────────────────────────────────────────────────────────────────────

def test_stop_omni_tx_resets_pending_switch(qapp, omni_tx_fresh):
    """Bug-Fix V3 C6: stop_omni_tx muss _pending_switch=False setzen.

    Sonst springt Block nach Re-enable() sofort weil pending noch True ist.
    """
    from core.omni_tx import OmniTX
    omni = OmniTX()
    omni.enable()
    omni._pending_switch = True
    omni._slot_index = 3
    omni._cycle_count = 50

    omni.stop_omni_tx("manual_halt")
    assert omni.active is False
    assert omni._pending_switch is False
    assert omni._slot_index == 0
    assert omni._cycle_count == 0


@pytest.mark.parametrize("reason", [
    "manual_halt", "band_change", "ft_mode_change", "rx_mode_change",
    "totmann_expired", "easter_egg_off", "superseded",
])
def test_omni_stopped_signal_emits_with_reason(qapp, omni_tx_fresh, reason):
    """omni_stopped(reason) wird bei jedem Stop fuer alle 7 Reasons emittiert."""
    from core.omni_tx import OmniTX
    omni = OmniTX()
    omni.enable()
    received = []
    omni.omni_stopped.connect(lambda r: received.append(r))

    omni.stop_omni_tx(reason)
    assert received == [reason]
    assert omni.active is False


def test_disable_delegates_to_stop_with_easter_egg_off(qapp, omni_tx_fresh):
    """disable() ist Backwards-compat Wrapper → stop_omni_tx('easter_egg_off')."""
    from core.omni_tx import OmniTX
    omni = OmniTX()
    omni.enable()
    received = []
    omni.omni_stopped.connect(lambda r: received.append(r))

    omni.disable()
    assert omni.active is False
    assert received == ["easter_egg_off"]
