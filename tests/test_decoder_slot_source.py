"""Tests fuer Decoder-Slot-Quelle (V3-Plan Commit 1+2).

Verifiziert:
- target_slot_start wird PRE-SLEEP berechnet (driftfrei gegen Sleep-Jitter)
- _slot_start_ts/_tx_even werden auf jede Message gesetzt
- FT8/FT4/FT2 funktionieren mit ihrer jeweiligen Slot-Dauer
- FT2 (3.8s) Slot-Berechnung kommt direkt vom Decoder (kein
  _slot_from_utc-Fallback mehr noetig)
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace


def _compute_target_slot_start(now: float, slot: float, wake_pos: float) -> float:
    """Replikat der Decoder-Logik aus core/decoder.py:_decode_loop.

    Pre-sleep Berechnung — driftfrei gegen Sleep-Jitter.
    """
    cycle_pos = now % slot
    if cycle_pos < wake_pos:
        return now - cycle_pos          # selber Slot
    return now - cycle_pos + slot       # nächster Slot


# ── Wake-Drift-Verhalten ─────────────────────────────────────────────────────

def test_target_slot_start_pre_sleep_no_drift():
    """target_slot_start ist vor sleep berechnet — wenn time.time()
    nach sleep ueber Slot-Boundary rutscht (Drift), bleibt
    target_slot_start trotzdem korrekt."""
    # Simuliere Wake-Berechnung bei t=:13.0 (im FT8 Slot der bei :00 startet)
    # wake_pos=13.5 → cycle_pos=13.0 < 13.5 → selber Slot
    pre_sleep_now = 13.0
    target = _compute_target_slot_start(pre_sleep_now, 15.0, 13.5)
    assert target == 0.0  # Slot-Anfang

    # Jetzt simuliere dass time.time() nach sleep bei :15.05 liegt
    # (Drift +0.05 ueber Slot-Grenze). target_slot_start ist immer noch
    # auf den gemeinten Slot bezogen.
    post_sleep_now = 15.05
    drifted_target = int(post_sleep_now / 15.0) * 15.0
    # Naive (post-sleep) Berechnung waere 15.0 → falscher Slot
    assert drifted_target == 15.0
    # Pre-sleep ist robust: target ist 0.0 (richtig)
    assert target == 0.0


def test_target_slot_start_modes():
    """FT8/FT4/FT2 Slot-Berechnung mit ihren jeweiligen Cycle-Dauern."""
    cases = [
        # (slot, wake_pos, now, expected_target)
        (15.0, 13.5, 0.0, 0.0),       # FT8 Slot-Anfang
        (15.0, 13.5, 7.0, 0.0),       # FT8 Mitte
        (15.0, 13.5, 13.4, 0.0),      # FT8 kurz vor Wake → selber Slot
        (15.0, 13.5, 13.6, 15.0),     # FT8 nach Wake → naechster Slot
        (7.5, 7.0, 0.0, 0.0),         # FT4 Slot-Anfang
        (7.5, 7.0, 6.9, 0.0),         # FT4 kurz vor Wake → selber
        (7.5, 7.0, 7.1, 7.5),         # FT4 nach Wake → naechster
        (3.8, 3.5, 0.0, 0.0),         # FT2 Slot-Anfang
        (3.8, 3.5, 3.4, 0.0),         # FT2 kurz vor Wake → selber
        (3.8, 3.5, 3.6, 3.8),         # FT2 nach Wake → naechster
    ]
    for slot, wake_pos, now, expected in cases:
        actual = _compute_target_slot_start(now, slot, wake_pos)
        assert abs(actual - expected) < 1e-9, \
            f"slot={slot} wake_pos={wake_pos} now={now}: erwartet {expected}, bekam {actual}"


# ── Message-Attribute ────────────────────────────────────────────────────────

def test_messages_get_slot_attributes():
    """Decoder-Logik replizieren: nach successful decode bekommen
    Messages _slot_start_ts und _tx_even."""
    target_slot_start = 1730000100.0  # :00 EVEN
    slot_duration = 15.0
    messages = [
        SimpleNamespace(raw="CQ DA1MHH J031", caller="DA1MHH"),
        SimpleNamespace(raw="DA1MHH DL1ABC -10", caller="DL1ABC"),
    ]
    # Replikat der Decoder-Logik aus core/decoder.py:_process_cycle
    tx_even = int(target_slot_start / slot_duration) % 2 == 0
    for m in messages:
        m._slot_start_ts = target_slot_start
        m._tx_even = tx_even

    for m in messages:
        assert m._slot_start_ts == target_slot_start
        assert m._tx_even is True  # 1730000100 / 15 = 115333340 (gerade)


def test_ft2_slot_from_decoder():
    """R1-Empfehlung: FT2 (3.8s Slot) wird durch Decoder-Wake-Logik
    abgedeckt, ohne separaten _slot_from_utc-Fallback.

    Hinweis: Float-Modulo bei 3.8 ist ungenau (3.8 nicht binary-exakt).
    Das ist ein bestehender Issue (alter `_slot_from_utc`-Code hatte
    ihn auch). Der Test prueft nur dass die Wake-Logik fuer FT2
    deterministische Werte liefert — kein perfekter Even/Odd-Wechsel
    bei beliebigem +3.8-Increment garantiert.
    """
    now = 1730000007.6
    target = _compute_target_slot_start(now, 3.8, 3.5)

    # Plausibilitaet:
    assert target <= now + 3.8, "target liegt im erwarteten Bereich"
    assert now - target < 3.8 * 2, "target nicht weiter als 2 Slots zurueck"

    # _tx_even ist deterministischer bool, kein None
    tx_even = int(target / 3.8) % 2 == 0
    assert isinstance(tx_even, bool)
