"""SimpleFT8 Pattern Tests — Validierung aller Antennen- und TX-Patterns.

Prueft:
- Paritaets-Verteilung (Even+Odd fuer jede Antenne)
- Loop-Uebergang nahtlos (max N hintereinander)
- Ratio korrekt
- OMNI-TX Even/Odd Alternierung
"""

import pytest
from core.diversity import DiversityController
from core.omni_tx import OmniTX


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def get_pattern(dc, n_cycles, mode="operate"):
    """Pattern aus DiversityController extrahieren."""
    pattern = []
    for _ in range(n_cycles):
        pattern.append(dc.choose())
        if mode == "measure":
            dc._measure_step += 1
        else:
            dc._operate_cycles += 1
    return pattern


def check_max_consecutive(pattern, max_allowed):
    """Prueft dass nie mehr als max_allowed gleiche hintereinander kommen."""
    for i in range(len(pattern) - max_allowed):
        window = pattern[i:i + max_allowed + 1]
        if len(set(window)) == 1:
            pytest.fail(f">{max_allowed}× '{window[0]}' ab Position {i}: {pattern}")


def check_both_parities(pattern, antenna, start_parity="even"):
    """Prueft dass eine Antenne BEIDE Paritaeten (Even+Odd) bekommt."""
    parities = set()
    for i, ant in enumerate(pattern):
        if ant == antenna:
            parity = "even" if (i % 2 == 0) else "odd"
            if start_parity == "odd":
                parity = "odd" if parity == "even" else "even"
            parities.add(parity)
    assert len(parities) == 2, \
        f"{antenna} bekommt nur {parities} (braucht even+odd): {pattern}"


def check_seamless_loop(pattern, max_consecutive):
    """Prueft Loop-Uebergang: Pattern 3× hintereinander, max N gleiche."""
    triple = pattern + pattern + pattern
    check_max_consecutive(triple, max_consecutive)


# ─── 50:50 Pattern ────────────────────────────────────────────────────────────

def test_5050_ratio():
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "50:50"
    p = get_pattern(dc, 8)
    assert p.count("A1") == 4 and p.count("A2") == 4

def test_5050_parities():
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "50:50"
    p = get_pattern(dc, 8)
    check_both_parities(p, "A1")
    check_both_parities(p, "A2")

def test_5050_seamless():
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "50:50"
    p = get_pattern(dc, 4)
    check_seamless_loop(p, 2)


# ─── 67:33 Pattern (70:30 Einstellung) ───────────────────────────────────────

def test_6733_ratio():
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "70:30"
    p = get_pattern(dc, 6)
    assert p.count("A1") == 4, f"Erwartet 4×A1: {p}"
    assert p.count("A2") == 2, f"Erwartet 2×A2: {p}"

def test_6733_parities():
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "70:30"
    p = get_pattern(dc, 12)  # 2 volle Durchlaeufe
    check_both_parities(p, "A1")
    check_both_parities(p, "A2")

def test_6733_seamless():
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "70:30"
    p = get_pattern(dc, 6)
    check_seamless_loop(p, 2)

def test_6733_max_consecutive():
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "70:30"
    p = get_pattern(dc, 18)  # 3 Durchlaeufe
    check_max_consecutive(p, 2)


# ─── 33:67 Pattern (30:70 Einstellung) ───────────────────────────────────────

def test_3367_ratio():
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "30:70"
    p = get_pattern(dc, 6)
    assert p.count("A2") == 4 and p.count("A1") == 2

def test_3367_seamless():
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "30:70"
    p = get_pattern(dc, 6)
    check_seamless_loop(p, 2)


# ─── Messphase Pattern ────────────────────────────────────────────────────────

def test_measure_both_antennas():
    dc = DiversityController()
    dc._phase = "measure"
    p = get_pattern(dc, 12, mode="measure")
    assert "A1" in p and "A2" in p

def test_measure_parities():
    dc = DiversityController()
    dc._phase = "measure"
    p = get_pattern(dc, 12, mode="measure")
    check_both_parities(p, "A1")
    check_both_parities(p, "A2")

def test_measure_max_consecutive():
    dc = DiversityController()
    dc._phase = "measure"
    p = get_pattern(dc, 18, mode="measure")
    check_max_consecutive(p, 2)


# ─── OMNI-TX Pattern ─────────────────────────────────────────────────────────

def test_omni_tx_pattern():
    omni = OmniTX(block_cycles=10)
    omni.enable()
    pattern = []
    for _ in range(10):
        send, _ = omni.should_tx()
        pattern.append(send)
        omni.advance()
    tx_count = pattern.count(True)
    rx_count = pattern.count(False)
    assert tx_count == 4, f"Erwartet 4 TX in 10 Slots: {pattern}"
    assert rx_count == 6, f"Erwartet 6 RX in 10 Slots: {pattern}"

def test_omni_tx_even_odd_alternation():
    """Block 1: Even zuerst, Block 2: Odd zuerst."""
    omni = OmniTX(block_cycles=10)
    omni.enable()
    # Block 1: erste TX should_tx → target_even=True (Even first)
    send1, even1 = omni.should_tx()
    assert send1 and even1 is True, f"Block 1 Pos 0: should be TX Even, got send={send1} even={even1}"
    omni.advance()
    send2, even2 = omni.should_tx()
    assert send2 and even2 is False, f"Block 1 Pos 1: should be TX Odd, got send={send2} even={even2}"

def test_omni_tx_seamless():
    """OMNI-TX Pattern muss nahtlos loopen (5-Slot Muster)."""
    omni = OmniTX(block_cycles=10)
    omni.enable()
    pattern = []
    for _ in range(15):  # 3 volle Durchlaeufe
        send, _ = omni.should_tx()
        pattern.append(send)
        omni.advance()
    assert pattern == [True,True,False,False,False] * 3

def test_omni_tx_block_switch():
    """Blockwechsel aendert TX-Slot Parity (Even→Odd)."""
    omni = OmniTX(block_cycles=10)
    omni.enable()
    assert omni.block == 1
    for _ in range(12):  # 10 Zyklen + 2 fuer Grenze
        omni.advance()
    # Block muss gewechselt haben (evtl. pending)
    if omni._pending_switch:
        while omni._slot_index != 0:
            omni.advance()
    assert omni.block == 2, f"Block sollte 2 sein: {omni.block}"
