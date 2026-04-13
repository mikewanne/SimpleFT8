#!/usr/bin/env python3
"""SimpleFT8 Unit Tests — alle Core-Module ohne Radio.

Ausfuehren:
    cd SimpleFT8
    source venv/bin/activate
    python3 -m pytest tests/test_modules.py -v

Oder direkt:
    python3 tests/test_modules.py
"""

import sys
import os

# Projekt-Root in sys.path einfuegen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np


# ── AGC ──────────────────────────────────────────────────────────────────────

def test_agc_loud_signal():
    """Lautes Signal → Gain sinkt unter 1.0."""
    from core.decoder import _apply_agc
    loud = (np.random.randn(180000) * 25000).astype(np.int16)
    state = (1.0, 1.0)
    for _ in range(5):
        _, state = _apply_agc(loud, state)
    assert state[0] < 1.0, f"AGC bei lautem Signal: gain={state[0]}"


def test_agc_normal_signal():
    """Normales Signal (Ziel-RMS) → Gain bleibt nahe 1.0."""
    from core.decoder import _apply_agc
    normal = (np.random.randn(180000) * 8225).astype(np.int16)
    state = (1.0, 1.0)
    for _ in range(10):
        _, state = _apply_agc(normal, state)
    assert 0.7 < state[0] < 1.5, f"AGC bei normalem Signal: gain={state[0]}"


def test_agc_clipping_protection():
    """Clipping-Schutz: kein int16 Overflow."""
    from core.decoder import _apply_agc
    extreme = np.full(1000, 30000, dtype=np.int16)
    out, _ = _apply_agc(extreme, (3.0, 3.0))
    assert np.max(out) <= 32767, f"Clipping: max={np.max(out)}"


def test_agc_silence():
    """Stille → Gain rampt auf Maximum (erwartet, kein Bug)."""
    from core.decoder import _apply_agc
    silence = np.zeros(12000, dtype=np.int16)
    _, state = _apply_agc(silence, (1.0, 1.0))
    assert state[0] >= 1.0, f"AGC bei Stille: gain={state[0]}"


# ── NTP Time ─────────────────────────────────────────────────────────────────

def test_ntp_reset():
    """Reset setzt Korrektur auf 0."""
    from core import ntp_time
    ntp_time.reset()
    assert ntp_time.get_correction() == 0.0


def test_ntp_too_few_stations():
    """Weniger als 5 Stationen → keine Korrektur."""
    from core import ntp_time
    ntp_time.reset()
    assert not ntp_time.update_from_decoded([0.3, 0.4])


def test_ntp_positive_correction():
    """10 Stationen mit dt=+0.8 → kumulative Korrektur +0.8 (erster Zyklus = 100%)."""
    from core import ntp_time
    ntp_time.reset()
    # Braucht 4 Zyklen (MEASURE_CYCLES) bis Korrektur angewendet wird
    for _ in range(4):
        ntp_time.update_from_decoded([0.8] * 10)
    corr = ntp_time.get_correction()
    assert 0.5 < corr < 1.0, f"DT-Korrektur: {corr}"
    ntp_time.reset()


def test_ntp_deadband():
    """DT unter 0.1s (Totband) → keine Korrektur."""
    from core import ntp_time
    ntp_time.reset()
    for _ in range(4):
        ntp_time.update_from_decoded([0.05] * 10)
    assert ntp_time.get_correction() == 0.0, f"Totband: sollte 0 sein, ist {ntp_time.get_correction()}"
    ntp_time.reset()


# ── OMNI-TX ──────────────────────────────────────────────────────────────────

def test_omni_tx_disabled():
    """Deaktiviert → should_tx() immer True."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=10)
    assert omni.should_tx() is True


def test_omni_tx_pattern():
    """5-Slot-Muster: TX,TX,RX,RX,RX."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=10)
    omni.enable()
    pattern = []
    for _ in range(10):
        pattern.append("TX" if omni.should_tx() else "RX")
        omni.advance()
    expected = ["TX", "TX", "RX", "RX", "RX", "TX", "TX", "RX", "RX", "RX"]
    assert pattern == expected, f"Muster falsch: {pattern}"
    omni.disable()


def test_omni_tx_block_switch():
    """Block-Wechsel nach block_cycles Zyklen."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=10)
    omni.enable()
    for _ in range(10):
        omni.advance()
    assert omni.block == 2, f"Block nach 10: {omni.block}"
    omni.disable()


def test_omni_tx_min_guard():
    """block_cycles Guard: min 10."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=3)
    assert omni.block_cycles == 10


def test_omni_tx_qso_reset():
    """QSO-Start setzt Zykluszaehler zurueck."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=10)
    omni.enable()
    for _ in range(5):
        omni.advance()
    omni.on_qso_started()
    assert omni._cycle_count == 0
    omni.disable()


# ── AP-Lite ──────────────────────────────────────────────────────────────────

def test_ap_lite_candidates_wait_report():
    """WAIT_REPORT → 6 Kandidaten (SNR-Fenster)."""
    from core.ap_lite import generate_candidates
    cands = generate_candidates(1, "DK5ON", "DA1MHH", "JO31", -10)
    assert len(cands) == 6
    assert all("DA1MHH" in c and "DK5ON" in c for c in cands)


def test_ap_lite_candidates_wait_rr73():
    """WAIT_RR73 → 3 Kandidaten (RR73, 73, RRR)."""
    from core.ap_lite import generate_candidates
    cands = generate_candidates(2, "DK5ON", "DA1MHH", "JO31")
    assert len(cands) == 3
    assert "DA1MHH DK5ON RR73" in cands


def test_ap_lite_candidates_cq_wait():
    """CQ_WAIT → 0 Kandidaten (zu viele Unbekannte)."""
    from core.ap_lite import generate_candidates
    assert len(generate_candidates(3, "DK5ON", "DA1MHH", "JO31")) == 0


def test_ap_lite_buffer_management():
    """Buffer speichern und loeschen."""
    from core.ap_lite import APLite
    ap = APLite()
    ap.enabled = True
    pcm = np.zeros(180000, dtype=np.float32)
    ap.on_decode_failed(pcm, 1000.0, "DK5ON", 1500.0, 1, "DA1MHH", "JO31")
    assert len(ap._buffers) == 1
    ap.clear()
    assert len(ap._buffers) == 0


def test_ap_lite_freq_mismatch():
    """Frequenz-Abweichung >30Hz → kein Rescue."""
    from core.ap_lite import APLite
    ap = APLite()
    ap.enabled = True
    pcm = np.zeros(180000, dtype=np.float32)
    ap.on_decode_failed(pcm, 1000.0, "DK5ON", 1500.0, 1, "DA1MHH", "JO31")
    result = ap.try_rescue(pcm, 1015.0, "DK5ON", 1600.0, 1, "DA1MHH", "JO31")
    assert result is None  # freq diff > 30Hz


# ── Diversity ────────────────────────────────────────────────────────────────

def test_diversity_50_50_pattern():
    """50:50 Pattern: A1,A1,A2,A2 (Even+Odd pro Antenne)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "50:50"
    pattern = []
    for _ in range(8):
        pattern.append(dc.choose())
        dc._operate_cycles += 1
    assert pattern == ["A1", "A1", "A2", "A2", "A1", "A1", "A2", "A2"]


def test_diversity_70_30_pattern():
    """70:30 Pattern: 7× A1, 3× A2 in 10 Zyklen."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "70:30"
    pattern = []
    for _ in range(10):
        pattern.append(dc.choose())
        dc._operate_cycles += 1
    assert pattern.count("A1") == 7


# ── Radio Factory ────────────────────────────────────────────────────────────

def test_preamp_presets():
    """PREAMP_PRESETS hat korrekte Band-Werte."""
    from radio.presets import PREAMP_PRESETS
    assert PREAMP_PRESETS["20m"] == 10
    assert PREAMP_PRESETS["40m"] == 10
    assert PREAMP_PRESETS["15m"] == 20


def test_factory_ic7300_not_implemented():
    """IC-7300 Typ → NotImplementedError."""
    from radio.radio_factory import create_radio

    class FakeSettings:
        def get(self, k, d=None):
            return {"radio_type": "ic7300"}.get(k, d)

    try:
        create_radio(FakeSettings())
        assert False, "Haette NotImplementedError werfen sollen"
    except NotImplementedError:
        pass


def test_factory_unknown_type():
    """Unbekannter Typ → ValueError."""
    from radio.radio_factory import create_radio

    class BadSettings:
        def get(self, k, d=None):
            return {"radio_type": "kenwood"}.get(k, d)

    try:
        create_radio(BadSettings())
        assert False, "Haette ValueError werfen sollen"
    except ValueError:
        pass


# ── Propagation ──────────────────────────────────────────────────────────────

def test_propagation_step_down():
    """Stufen-Abstufung: good→fair, fair→poor, poor→poor."""
    from core.propagation import _step_down
    assert _step_down("good") == "fair"
    assert _step_down("fair") == "poor"
    assert _step_down("poor") == "poor"


def test_propagation_time_correction_80m():
    """80m mittags (12 UTC) → eine Stufe schlechter."""
    from core.propagation import _apply_time_correction
    assert _apply_time_correction("80m", "good", 12) == "fair"
    assert _apply_time_correction("80m", "good", 2) == "good"


def test_propagation_time_correction_20m():
    """20m nachts (3 UTC) → eine Stufe schlechter."""
    from core.propagation import _apply_time_correction
    assert _apply_time_correction("20m", "fair", 14) == "fair"
    assert _apply_time_correction("20m", "fair", 3) == "poor"


# ── Syntax Checks ────────────────────────────────────────────────────────────

def test_syntax_main_window():
    """main_window.py Syntax korrekt."""
    with open("ui/main_window.py") as f:
        compile(f.read(), "main_window.py", "exec")


def test_syntax_flexradio():
    """flexradio.py Syntax korrekt."""
    with open("radio/flexradio.py") as f:
        compile(f.read(), "flexradio.py", "exec")


def test_no_private_radio_access():
    """Kein privater FlexRadio-Zugriff in UI-Dateien."""
    import re
    ui_files = ["ui/main_window.py", "ui/dx_tune_dialog.py"]
    for path in ui_files:
        if not os.path.exists(path):
            continue
        with open(path) as f:
            content = f.read()
        matches = re.findall(r"self\.radio\._\w+", content)
        assert not matches, f"{path}: Private Zugriffe: {set(matches)}"


# ── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    # Alle test_ Funktionen sammeln und ausfuehren
    tests = [(name, func) for name, func in sorted(globals().items())
             if name.startswith("test_") and callable(func)]

    passed = 0
    failed = 0
    for name, func in tests:
        try:
            func()
            print(f"  OK  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            traceback.print_exc()
            failed += 1

    print()
    print(f"{'=' * 50}")
    print(f"{passed} bestanden, {failed} fehlgeschlagen, {passed + failed} gesamt")
    if failed:
        print("TESTS FEHLGESCHLAGEN!")
        sys.exit(1)
    else:
        print("ALLE TESTS BESTANDEN")
    print(f"{'=' * 50}")
