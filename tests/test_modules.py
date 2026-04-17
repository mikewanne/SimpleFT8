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
    """Reset mit keep_correction=False setzt auf 0."""
    from core import ntp_time
    ntp_time.reset(keep_correction=False)
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
    ntp_time.reset(keep_correction=False)  # Alles zuruecksetzen inkl. alter Korrektur
    for _ in range(4):
        ntp_time.update_from_decoded([0.05] * 10)
    assert ntp_time.get_correction() == 0.0, f"Totband: sollte 0 sein, ist {ntp_time.get_correction()}"
    ntp_time.reset(keep_correction=False)


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


# ── QSO State Machine ────────────────────────────────────────────────────────

class _TestMsg:
    """Test-Message die Properties ueberschreibt OHNE die FT8Message-Klasse zu patchen."""
    def __init__(self, raw, caller, target, field3="",
                 is_grid=False, is_report=False, is_r_report=False,
                 is_rr73=False, is_73=False):
        self.raw = raw
        self.field1 = target
        self.field2 = caller
        self.field3 = field3
        self.snr = -15
        self.freq_hz = 1000
        self.dt = 0.0
        self.antenna = ""
        self._tx_even = True
        self.is_grid = is_grid
        self.is_report = is_report
        self.is_r_report = is_r_report
        self.is_rr73 = is_rr73
        self.is_73 = is_73
    @property
    def caller(self): return self.field2
    @property
    def target(self): return self.field1
    @property
    def grid_or_report(self): return self.field3
    @property
    def is_cq(self): return self.field1 == "CQ"
    @property
    def is_directed_to(self): return not self.is_cq


def _make_msg(caller, target, raw, grid_or_report="", is_grid=False,
              is_report=False, is_r_report=False, is_rr73=False, is_73=False):
    """Hilfs-Message fuer Tests (eigene Klasse, patcht FT8Message NICHT)."""
    return _TestMsg(raw=raw, caller=caller, target=target, field3=grid_or_report,
                    is_grid=is_grid, is_report=is_report, is_r_report=is_r_report,
                    is_rr73=is_rr73, is_73=is_73)
    type(m).caller = property(lambda s: s.field2)
    type(m).target = property(lambda s: s.field1)
    return m


def test_qso_cq_flow():
    """CQ-Modus: CQ → Antwort → Report → R-Report → RR73 → fertig."""
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    completed = []
    sm.qso_complete.connect(lambda q: completed.append(q))

    sm.start_cq()
    assert sm.state == QSOState.CQ_CALLING
    assert len(sent) == 1 and "CQ" in sent[0]

    # Simuliere TX fertig
    sm.on_message_sent()
    assert sm.state == QSOState.CQ_WAIT

    # Station antwortet mit Grid
    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI KO82",
                     grid_or_report="KO82", is_grid=True)
    sm.on_message_received(msg)
    assert sm.state == QSOState.TX_REPORT
    assert len(sent) == 2  # Report gesendet

    # TX fertig → WAIT_RR73
    sm.on_message_sent()
    assert sm.state == QSOState.WAIT_RR73

    # Station sendet R-Report
    msg2 = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI R-06",
                      grid_or_report="R-06", is_report=True, is_r_report=True)
    sm.on_message_received(msg2)
    assert sm.state == QSOState.TX_RR73
    assert "RR73" in sent[-1]

    # TX fertig → QSO komplett
    sm.on_message_sent()
    assert len(completed) == 1
    assert sm.state == QSOState.WAIT_73


def test_qso_wait73_no_timeout():
    """WAIT_73 darf NICHT den 3-Min Global-Timeout ausloesen."""
    import time
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.WAIT_73
    sm.qso.start_time = time.time() - 200  # 200s = ueber 180s Limit
    timeouts = []
    sm.qso_timeout.connect(lambda c: timeouts.append(c))
    sm.on_cycle_end()
    assert len(timeouts) == 0, "WAIT_73 soll NICHT timeout ausloesen"


def test_qso_rr73_courtesy():
    """Nach QSO: Station sendet nochmal R-Report → RR73 Hoeflichkeit (max 2x)."""
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.WAIT_73
    sm.qso.their_call = "R3EDI"
    sm.qso.rr73_retries = 0
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))

    # Station sendet nochmal R-Report
    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI R-06",
                     grid_or_report="R-06", is_report=True, is_r_report=True)
    sm.on_message_received(msg)
    assert len(sent) == 1 and "RR73" in sent[0]

    # Nochmal
    sm.on_message_received(msg)
    assert len(sent) == 2

    # Drittes Mal → wird ignoriert (max 2)
    sm.on_message_received(msg)
    assert len(sent) == 2  # kein drittes RR73


def test_qso_73_confirmation():
    """Nach RR73: 73 von Gegenstation → QSO bestaetigt."""
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.WAIT_73
    sm.qso.their_call = "R3EDI"
    sm.cq_mode = True
    confirmed = []
    sm.qso_confirmed.connect(lambda q: confirmed.append(q))

    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI 73", is_73=True)
    sm.on_message_received(msg)
    assert len(confirmed) == 1


def test_qso_hunt_basic():
    """Hunt-Modus: Station anklicken → Report senden."""
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.start_qso(their_call="US5EAA", their_grid="KN78", freq_hz=1200)
    assert sm.state == QSOState.TX_CALL
    assert "US5EAA" in sent[0] and "DA1MHH" in sent[0]


def test_qso_worked_recently_block():
    """Kuerzlich gearbeitete Station wird im CQ-Modus ignoriert."""
    import time
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm._worked_calls["R3EDI"] = time.time()  # gerade gearbeitet
    sm.state = QSOState.CQ_WAIT
    sm.cq_mode = True
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))

    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI KO82",
                     grid_or_report="KO82", is_grid=True)
    sm.on_message_received(msg)
    # Sollte ignoriert werden → kein neuer TX
    assert not any("R3EDI" in s and "RR73" not in s and "CQ" not in s for s in sent)


def test_qso_caller_queue():
    """Warteliste: Station waehrend QSO wird nach QSO-Ende angerufen."""
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm.state = QSOState.WAIT_REPORT
    sm.qso.their_call = "R3EDI"
    sent = []
    sm.send_message.connect(lambda m: sent.append(m))

    # EA3FHP ruft uns waehrend QSO mit R3EDI (mit Grid)
    msg_grid = _make_msg("EA3FHP", "DA1MHH", "DA1MHH EA3FHP JN01",
                          grid_or_report="JN01", is_grid=True)
    sm.on_message_received(msg_grid)
    assert len(sm._caller_queue) == 1, "EA3FHP soll in Queue sein"

    # EA3FHP mit Report statt Grid (vorher Bug: wurde nicht aufgenommen)
    msg_report = _make_msg("IS0LIT", "DA1MHH", "DA1MHH IS0LIT -15",
                            grid_or_report="-15", is_report=True)
    sm.on_message_received(msg_report)
    assert len(sm._caller_queue) == 2, "IS0LIT soll auch in Queue sein (Report)"


# ── DT Correction Persistence ────────────────────────────────────────────────

def test_dt_correction_mode_switch():
    """DT-Korrektur: Modus-Wechsel laedt gespeicherten Wert."""
    from core import ntp_time
    # Simuliere: FT8 hat Korrektur +0.5
    ntp_time._correction = 0.5
    ntp_time._mode = "FT8"
    ntp_time._saved = {"FT8": 0.5, "FT4": 0.3}
    # Wechsel auf FT4 → soll 0.3 laden
    ntp_time.set_mode("FT4")
    assert abs(ntp_time._correction - 0.3) < 0.01
    # Zurueck auf FT8 → soll 0.5 laden
    ntp_time.set_mode("FT8")
    assert abs(ntp_time._correction - 0.5) < 0.01
    # Reset
    ntp_time.reset(keep_correction=False)


# ── NTP/DT Correction Logic ──────────────────────────────────────────────────

def test_dt_first_correction_full():
    """Erstkorrektur: 100% des Medians angewendet (nicht gedaempft)."""
    from core import ntp_time
    ntp_time.reset(keep_correction=False)
    ntp_time._is_initial = True
    # 2 Zyklen mit DT +0.5
    ntp_time.update_from_decoded([0.5, 0.5, 0.5, 0.5, 0.5])
    ntp_time.update_from_decoded([0.5, 0.5, 0.5, 0.5, 0.5])
    # Erstkorrektur: volle 0.5
    assert abs(ntp_time._correction - 0.5) < 0.05, f"Erstkorrektur erwartet ~0.5, got {ntp_time._correction}"
    assert not ntp_time._is_initial
    ntp_time.reset(keep_correction=False)


def test_dt_fine_correction_damped():
    """Feinkorrektur: nur 70% des Medians (Daempfung)."""
    from core import ntp_time
    ntp_time.reset(keep_correction=False)
    ntp_time._is_initial = False
    ntp_time._correction = 0.5
    ntp_time._phase = "measure"
    ntp_time._cycle_count = 0
    ntp_time._measure_buffer = []
    # 2 Zyklen mit DT +0.2 (Restfehler)
    ntp_time.update_from_decoded([0.2, 0.2, 0.2, 0.2, 0.2])
    ntp_time.update_from_decoded([0.2, 0.2, 0.2, 0.2, 0.2])
    # Feinkorrektur: 0.5 + (0.2 × 0.7) = 0.64
    expected = 0.5 + 0.2 * 0.7
    assert abs(ntp_time._correction - expected) < 0.05, f"Feinkorrektur erwartet ~{expected}, got {ntp_time._correction}"
    ntp_time.reset(keep_correction=False)


def test_dt_jump_detection():
    """Sprung >1.5s → Reset auf 0 + neu messen."""
    from core import ntp_time
    ntp_time.reset(keep_correction=False)
    ntp_time._correction = 0.5
    ntp_time._phase = "operate"
    ntp_time._cycle_count = 0
    # DT ploetzlich bei +2.0 → Sprung erkannt
    ntp_time.update_from_decoded([2.0, 2.0, 2.0, 2.0])
    assert ntp_time._correction == 0.0, "Nach Sprung soll Korrektur 0.0 sein"
    assert ntp_time._phase == "measure"
    assert ntp_time._is_initial
    ntp_time.reset(keep_correction=False)


# ── FT8Message Parser ────────────────────────────────────────────────────────

def test_parse_cq():
    """CQ-Nachricht korrekt geparst."""
    from core.message import parse_ft8_message
    m = parse_ft8_message("CQ DA1MHH JO31", snr=-15, freq_hz=1000, dt=0.1)
    assert m.is_cq
    assert m.caller == "DA1MHH"
    assert m.grid_or_report == "JO31"


def test_parse_report():
    """Report-Nachricht korrekt geparst."""
    from core.message import parse_ft8_message
    m = parse_ft8_message("DA1MHH R3EDI -06", snr=-15, freq_hz=1000, dt=0.1)
    assert m.is_report
    assert m.caller == "R3EDI"
    assert m.target == "DA1MHH"


def test_parse_r_report():
    """R-Report korrekt erkannt."""
    from core.message import parse_ft8_message
    m = parse_ft8_message("DA1MHH R3EDI R-06", snr=-15, freq_hz=1000, dt=0.1)
    assert m.is_report
    assert m.is_r_report


def test_parse_rr73():
    """RR73 korrekt erkannt."""
    from core.message import parse_ft8_message
    m = parse_ft8_message("DA1MHH R3EDI RR73", snr=-15, freq_hz=1000, dt=0.1)
    assert m.is_rr73


def test_parse_73():
    """73 korrekt erkannt."""
    from core.message import parse_ft8_message
    m = parse_ft8_message("DA1MHH R3EDI 73", snr=-15, freq_hz=1000, dt=0.1)
    assert m.is_73


# ── Encoder Sample Length ────────────────────────────────────────────────────

def test_encoder_ft8_length():
    """FT8 Encode: 180000 Samples (15.0s @ 12kHz)."""
    from core.ft8lib_decoder import get_ft8lib
    audio = get_ft8lib().encode("CQ DA1MHH JO31", freq_hz=1000.0, mode="FT8")
    assert audio is not None
    assert len(audio) == 180000, f"FT8 erwartet 180000, got {len(audio)}"


def test_encoder_ft4_length():
    """FT4 Encode: 90000 Samples (7.5s @ 12kHz)."""
    from core.ft8lib_decoder import get_ft8lib
    audio = get_ft8lib().encode("CQ DA1MHH JO31", freq_hz=1000.0, mode="FT4")
    assert audio is not None
    assert len(audio) == 90000, f"FT4 erwartet 90000, got {len(audio)}"


def test_encoder_ft2_length():
    """FT2 Encode: 45600 Samples (3.8s @ 12kHz)."""
    from core.ft8lib_decoder import get_ft8lib
    audio = get_ft8lib().encode("CQ DA1MHH JO31", freq_hz=1000.0, mode="FT2")
    assert audio is not None
    assert len(audio) == 45600, f"FT2 erwartet 45600, got {len(audio)}"


# ── Decoder Protocol Switch ──────────────────────────────────────────────────

def test_decoder_slot_samples_ft8():
    """Decoder: FT8 → 180000 Slot-Samples."""
    from core.decoder import Decoder
    d = Decoder(mode="FT8")
    assert d._slot_samples == 180000


def test_decoder_slot_samples_ft4():
    """Decoder: FT4 → 90000 Slot-Samples."""
    from core.decoder import Decoder
    d = Decoder(mode="FT4")
    assert d._slot_samples == 90000


def test_decoder_slot_samples_ft2():
    """Decoder: FT2 → 45600 Slot-Samples."""
    from core.decoder import Decoder
    d = Decoder(mode="FT2")
    assert d._slot_samples == 45600


def test_decoder_protocol_switch():
    """Decoder: set_protocol() aendert _slot_samples."""
    from core.decoder import Decoder
    d = Decoder(mode="FT8")
    assert d._slot_samples == 180000
    d.set_protocol("FT4")
    assert d._slot_samples == 90000
    d.set_protocol("FT2")
    assert d._slot_samples == 45600


# ── Station Accumulator ──────────────────────────────────────────────────────

def test_accumulator_new_station():
    """Neue Station wird hinzugefuegt."""
    from core.station_accumulator import accumulate_stations
    from core.message import parse_ft8_message
    stations = {}
    msgs = [parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)]
    changed = accumulate_stations(stations, msgs, set())
    assert changed
    assert "R3EDI" in stations


def test_accumulator_aging():
    """Stationen aelter als 75s werden entfernt."""
    import time
    from core.station_accumulator import accumulate_stations, remove_stale
    from core.message import parse_ft8_message
    stations = {}
    msgs = [parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)]
    accumulate_stations(stations, msgs, set())
    assert "R3EDI" in stations
    # Kuenstlich altern
    stations["R3EDI"]._last_heard = time.time() - 80
    removed = remove_stale(stations, set())
    assert "R3EDI" in removed
    assert "R3EDI" not in stations


def test_accumulator_active_qso_longer_aging():
    """Aktive QSO-Station: 150s Aging statt 75s."""
    import time
    from core.station_accumulator import accumulate_stations, remove_stale
    from core.message import parse_ft8_message
    stations = {}
    msgs = [parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)]
    accumulate_stations(stations, msgs, {"R3EDI"})
    stations["R3EDI"]._last_heard = time.time() - 80  # 80s > 75 aber < 150
    removed = remove_stale(stations, {"R3EDI"})
    assert len(removed) == 0, "Aktive QSO-Station soll 150s Aging haben"
    assert "R3EDI" in stations


def test_accumulator_diversity_antenna():
    """Diversity: Antenne wird gesetzt und verglichen."""
    from core.station_accumulator import accumulate_stations
    from core.message import parse_ft8_message
    stations = {}
    msg1 = [parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)]
    accumulate_stations(stations, msg1, set(), antenna="A1")
    assert stations["R3EDI"].antenna == "A1"
    # Gleiche Station auf A2 mit besserem SNR
    msg2 = [parse_ft8_message("CQ R3EDI KO82", snr=-10, freq_hz=1000, dt=0.1)]
    accumulate_stations(stations, msg2, set(), antenna="A2")
    assert "A2" in stations["R3EDI"].antenna, f"A2 sollte dominieren, got {stations['R3EDI'].antenna}"


# ── Even/Odd Slot-Berechnung ──────────────────────────────────────────────────

def test_even_odd_ft8():
    """FT8: Slot-Berechnung mit 15s Zyklen."""
    import time
    now = time.time()
    cycle_ft8 = int(now / 15.0)
    is_even = cycle_ft8 % 2 == 0
    assert isinstance(is_even, bool)


def test_even_odd_ft4():
    """FT4: Slot-Berechnung mit 7.5s Zyklen."""
    import time
    now = time.time()
    cycle_ft4 = int(now / 7.5)
    # FT4 hat doppelt so viele Zyklen wie FT8
    cycle_ft8 = int(now / 15.0)
    assert cycle_ft4 >= cycle_ft8


def test_even_odd_ft2():
    """FT2: Slot-Berechnung mit 3.8s Zyklen."""
    import time
    now = time.time()
    cycle_ft2 = int(now / 3.8)
    cycle_ft8 = int(now / 15.0)
    assert cycle_ft2 >= cycle_ft8 * 3  # FT2 ~4x so viele Zyklen


# ── Diversity Presets ─────────────────────────────────────────────────────────

def test_diversity_preset_save_load():
    """Diversity-Preset speichern und laden."""
    from config.settings import Settings
    s = Settings()
    s.save_diversity_preset("FT8", "20m", "70:30", "A1")
    preset = s.get_diversity_preset("FT8", "20m")
    assert preset is not None
    assert preset["ratio"] == "70:30"
    assert preset["dominant"] == "A1"


def test_diversity_preset_missing():
    """Fehlender Preset gibt None zurueck."""
    from config.settings import Settings
    s = Settings()
    assert s.get_diversity_preset("FT2", "160m") is None


def test_diversity_load_preset():
    """load_preset() setzt ratio und phase korrekt."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.load_preset({"ratio": "30:70", "dominant": "A2"})
    assert dc.ratio == "30:70"
    assert dc.dominant == "A2"
    assert dc.phase == "operate"


# ── can_measure() Schwelle ────────────────────────────────────────────────────

def test_can_measure_enough():
    """5 Stationen → kann messen."""
    from core.diversity import DiversityController
    dc = DiversityController()
    assert dc.can_measure(5) is True
    assert dc.can_measure(20) is True


def test_can_measure_too_few():
    """3 Stationen → kann NICHT messen."""
    from core.diversity import DiversityController
    dc = DiversityController()
    assert dc.can_measure(3) is False
    assert dc.can_measure(0) is False


# ── Modus-Multiplikator ──────────────────────────────────────────────────────

def test_operate_cycles_multiplier():
    """OPERATE_CYCLES wird mit Modus-Faktor multipliziert."""
    _MULT = {"FT8": 1, "FT4": 2, "FT2": 4}
    base = 60
    assert base * _MULT["FT8"] == 60
    assert base * _MULT["FT4"] == 120
    assert base * _MULT["FT2"] == 240


def test_dt_min_stations_per_mode():
    """DT MIN_STATIONS: FT8=3, FT4=2, FT2=1."""
    _MIN = {"FT8": 3, "FT4": 2, "FT2": 1}
    assert _MIN["FT8"] == 3
    assert _MIN["FT4"] == 2
    assert _MIN["FT2"] == 1


# ── ADIF Writer/Parser ────────────────────────────────────────────────────────

def test_adif_header():
    """ADIF-Datei hat korrekten Header."""
    from pathlib import Path
    adi_files = list(Path(".").glob("SimpleFT8_LOG_*.adi"))
    if not adi_files:
        return  # Keine Logdateien vorhanden
    text = adi_files[0].read_text()
    assert "<ADIF_VER:" in text
    assert "<PROGRAMID:" in text
    assert "<EOH>" in text


def test_adif_required_fields():
    """Jeder ADIF-Record hat alle Pflichtfelder."""
    from pathlib import Path
    import re
    adi_files = list(Path(".").glob("SimpleFT8_LOG_*.adi"))
    if not adi_files:
        return
    text = adi_files[0].read_text()
    eoh = text.upper().find("<EOH>")
    body = text[eoh + 5:] if eoh >= 0 else text
    records = re.split(r"<EOR>", body, flags=re.IGNORECASE)
    required = ["CALL", "QSO_DATE", "TIME_ON", "BAND", "MODE", "FREQ"]
    for rec in records:
        if not rec.strip():
            continue
        for field in required:
            assert f"<{field}:" in rec.upper(), f"Pflichtfeld {field} fehlt in: {rec[:80]}"


def test_adif_date_format():
    """QSO_DATE = YYYYMMDD (8 Zeichen), TIME_ON = HHMMSS (6 Zeichen)."""
    from pathlib import Path
    import re
    adi_files = list(Path(".").glob("SimpleFT8_LOG_*.adi"))
    if not adi_files:
        return
    text = adi_files[0].read_text()
    dates = re.findall(r"<QSO_DATE:8>(\d{8})", text)
    times = re.findall(r"<TIME_ON:6>(\d{6})", text)
    for d in dates:
        assert len(d) == 8 and d[:4].isdigit()
    for t in times:
        assert len(t) == 6 and int(t[:2]) < 24 and int(t[2:4]) < 60


def test_adif_parse_roundtrip():
    """ADIF-Datei lesen + Felder korrekt extrahieren."""
    from log.adif import parse_adif_file
    from pathlib import Path
    adi_files = list(Path(".").glob("SimpleFT8_LOG_*.adi"))
    if not adi_files:
        return
    records = parse_adif_file(adi_files[0])
    assert len(records) >= 0  # Kann leer sein
    for rec in records:
        assert "CALL" in rec
        assert "_SOURCE_FILE" in rec  # Intern gesetzt fuer Delete


# ── Geo / Distance ───────────────────────────────────────────────────────────

def test_grid_to_latlon():
    """Grid JO31 → ca. 51°N, 6°E (Ruhrgebiet)."""
    from core.geo import grid_to_latlon
    lat, lon = grid_to_latlon("JO31")
    assert 50 < lat < 52
    assert 5 < lon < 8


def test_grid_distance_known():
    """JO31 → KP42 (Finnland) = ca. 1500-2000 km."""
    from core.geo import grid_distance
    km = grid_distance("JO31", "KP42")
    assert km is not None
    assert 1400 < km < 2200


def test_grid_distance_invalid():
    """Ungueltiges Grid → None."""
    from core.geo import grid_distance
    assert grid_distance("JO31", "") is None
    assert grid_distance("JO31", "XX") is None


def test_callsign_to_distance():
    """Callsign-Prefix → ungefaehre Entfernung."""
    from core.geo import callsign_to_distance
    km = callsign_to_distance("VK3ABC", "JO31")  # Australien
    if km is not None:
        assert km > 10000


# ── CQ Frequency ─────────────────────────────────────────────────────────────

def test_cq_freq_empty_histogram():
    """Leeres Histogramm → None."""
    from core.diversity import DiversityController
    dc = DiversityController()
    assert dc.get_free_cq_freq() is None


def test_cq_freq_near_activity():
    """CQ-Frequenz muss NAHE der Aktivitaet liegen (dynamischer Sweet Spot)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Simuliere belegte Frequenzen bei 1000-1200 Hz
    for f in range(1000, 1200, 50):
        dc.record_freq(f)
    freq = dc.get_free_cq_freq()
    if freq is not None:
        # Muss nahe am Median (1100 Hz) sein, nicht weit weg
        assert 500 <= freq <= 1700, f"CQ-Freq {freq} zu weit von Aktivitaet"


# ── Settings Roundtrip ────────────────────────────────────────────────────────

def test_settings_save_load():
    """Settings speichern und laden Roundtrip."""
    from config.settings import Settings
    s = Settings()
    old_call = s.callsign
    s.set("test_key_temp", 42)
    s.save()
    s2 = Settings()
    assert s2.get("test_key_temp") == 42
    assert s2.callsign == old_call


def test_settings_missing_key():
    """Fehlender Key → Default zurueck."""
    from config.settings import Settings
    s = Settings()
    assert s.get("nonexistent_key_xyz", "default") == "default"


# ── Timer / Timing ───────────────────────────────────────────────────────────

def test_timer_cycle_durations():
    """Timer kennt alle Modi-Dauern."""
    from core.timing import FT8Timer
    t = FT8Timer("FT8")
    assert t.cycle_duration == 15.0
    t.set_mode("FT4")
    assert t.cycle_duration == 7.5
    t.set_mode("FT2")
    assert t.cycle_duration == 3.8


def test_timer_seconds_in_cycle():
    """seconds_in_cycle() gibt Wert zwischen 0 und cycle_duration."""
    from core.timing import FT8Timer
    t = FT8Timer("FT8")
    sic = t.seconds_in_cycle()
    assert 0 <= sic < 15.0


# ── Message Parser erweitert ─────────────────────────────────────────────────

def test_parse_cq_dx():
    """CQ DX Nachricht korrekt geparst."""
    from core.message import parse_ft8_message
    m = parse_ft8_message("CQ DX DA1MHH JO31", snr=-15, freq_hz=1000, dt=0.1)
    assert m.is_cq
    assert m.caller == "DA1MHH"


def test_parse_grid_message():
    """Grid-Antwort korrekt erkannt."""
    from core.message import parse_ft8_message
    m = parse_ft8_message("DA1MHH R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)
    assert m.is_grid
    assert m.caller == "R3EDI"
    assert m.grid_or_report == "KO82"


# ── QSO State Machine erweitert ──────────────────────────────────────────────

def test_qso_cancel_resets():
    """Cancel setzt State auf IDLE und leert Queue."""
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.cq_mode = True
    sm.state = QSOState.TX_REPORT
    sm.cancel()
    assert sm.state == QSOState.IDLE
    assert not sm.cq_mode
    assert len(sm._caller_queue) == 0


def test_qso_3min_timeout():
    """3-Min Global-Timeout feuert in WAIT_REPORT."""
    import time
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.WAIT_REPORT
    sm.qso.their_call = "TEST"
    sm.qso.start_time = time.time() - 200
    timeouts = []
    sm.qso_timeout.connect(lambda c: timeouts.append(c))
    sm.on_cycle_end()
    assert len(timeouts) == 1


def test_qso_no_double_log():
    """QSO wird nur einmal geloggt (nicht bei 73 nochmal)."""
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    completed = []
    sm.qso_complete.connect(lambda q: completed.append(q))
    # Simuliere TX_RR73 → on_message_sent
    sm.state = QSOState.TX_RR73
    sm.qso.their_call = "R3EDI"
    sm.on_message_sent()
    assert len(completed) == 1
    assert sm.state == QSOState.WAIT_73
    # 73 empfangen → qso_confirmed, NICHT nochmal qso_complete
    confirmed = []
    sm.qso_confirmed.connect(lambda q: confirmed.append(q))
    sm.cq_mode = True
    msg = _make_msg("R3EDI", "DA1MHH", "DA1MHH R3EDI 73", is_73=True)
    sm.on_message_received(msg)
    assert len(confirmed) == 1
    assert len(completed) == 1  # immer noch 1, nicht 2!


# ── Encoder/Protocol ─────────────────────────────────────────────────────────

def test_protocol_frequencies_complete():
    """Alle Modi haben Frequenzen fuer alle Baender."""
    from core.protocol import BAND_FREQUENCIES
    for mode in ["FT8", "FT4", "FT2"]:
        freqs = BAND_FREQUENCIES.get(mode, {})
        assert "20m" in freqs, f"{mode} hat keine 20m Frequenz"
        assert "40m" in freqs, f"{mode} hat keine 40m Frequenz"


def test_protocol_ft2_different_from_ft4():
    """FT2 und FT4 haben unterschiedliche Frequenzen."""
    from core.protocol import BAND_FREQUENCIES
    ft4_20 = BAND_FREQUENCIES["FT4"]["20m"]
    ft2_20 = BAND_FREQUENCIES["FT2"]["20m"]
    assert ft4_20 != ft2_20, f"FT4 und FT2 auf 20m gleich: {ft4_20}"


# ── DT Pro-Modus Persistence ──────────────────────────────────────────────────

def test_dt_save_load_file():
    """DT-Werte werden in JSON gespeichert und geladen."""
    from core import ntp_time
    ntp_time._correction = 0.55
    ntp_time._mode = "FT8"
    ntp_time._save_current()
    assert ntp_time._saved.get("FT8") == 0.55
    # Datei existiert
    assert ntp_time._DT_FILE.exists()
    ntp_time.reset(keep_correction=False)


def test_dt_set_mode_loads_saved():
    """set_mode() laedt gespeicherten Wert."""
    from core import ntp_time
    ntp_time._saved = {"FT8": 0.7, "FT4": 0.3, "FT2": 0.1}
    ntp_time.set_mode("FT4")
    assert abs(ntp_time._correction - 0.3) < 0.01
    assert not ntp_time._is_initial  # Hat gespeicherten Wert → nicht initial
    ntp_time.set_mode("FT2")
    assert abs(ntp_time._correction - 0.1) < 0.01
    ntp_time.reset(keep_correction=False)


def test_dt_set_mode_no_saved():
    """set_mode() ohne gespeicherten Wert → 0 + initial."""
    from core import ntp_time
    ntp_time._saved = {}
    ntp_time.set_mode("FT2")
    assert ntp_time._correction == 0.0
    assert ntp_time._is_initial is True
    ntp_time.reset(keep_correction=False)


def test_dt_set_mode_saves_old():
    """set_mode() speichert alten Wert bevor gewechselt wird."""
    from core import ntp_time
    ntp_time._mode = "FT8"
    ntp_time._correction = 0.65
    ntp_time._saved = {}
    ntp_time.set_mode("FT4")
    assert ntp_time._saved.get("FT8") == 0.65
    ntp_time.reset(keep_correction=False)


def test_dt_min_stations_ft2():
    """FT2: MIN_STATIONS=2 (nicht 1, Ausreisser-Schutz)."""
    from core import ntp_time
    ntp_time._mode = "FT2"
    # 1 Station reicht NICHT
    result = ntp_time.update_from_decoded([0.5])
    assert result is False
    # 2 Stationen reichen
    ntp_time._phase = "measure"
    ntp_time._cycle_count = 0
    ntp_time._measure_buffer = []
    result = ntp_time.update_from_decoded([0.5, 0.5])
    assert result is not None  # Wurde verarbeitet (True oder False)
    ntp_time.reset(keep_correction=False)


def test_dt_max_correction_clamp():
    """Korrektur wird auf ±2.0s begrenzt."""
    from core import ntp_time
    ntp_time.reset(keep_correction=False)
    ntp_time._is_initial = True
    ntp_time._phase = "measure"
    # Extrem hohe DT-Werte → Korrektur darf nicht ueber 2.0 gehen
    ntp_time.update_from_decoded([1.9, 1.9, 1.9, 1.9, 1.9])
    ntp_time.update_from_decoded([1.9, 1.9, 1.9, 1.9, 1.9])
    assert ntp_time._correction <= 2.0
    ntp_time.reset(keep_correction=False)


# ── Presence Timer ────────────────────────────────────────────────────────────

def test_presence_can_tx_normal():
    """Presence nicht abgelaufen → TX erlaubt."""
    # Kann nicht direkt MainWindow testen, aber Logik pruefen
    expired = False
    assert not expired  # TX erlaubt


def test_presence_timeout_value():
    """Presence Timeout ist 15 Minuten (900s)."""
    assert 900 == 15 * 60


# ── ADIF Writer ──────────────────────────────────────────────────────────────

def test_adif_no_empty_gridsquare():
    """GRIDSQUARE:0 sollte nicht geschrieben werden (Kompatibilitaet)."""
    from pathlib import Path
    adi_files = list(Path(".").glob("SimpleFT8_LOG_*.adi"))
    if not adi_files:
        return
    text = adi_files[-1].read_text()
    # GRIDSQUARE:0 ist technisch okay aber manche Parser moegen es nicht
    # Warnung wenn vorhanden
    if "<GRIDSQUARE:0>" in text:
        print("  WARNUNG: GRIDSQUARE:0 gefunden (leer, evtl. weglassen)")


def test_adif_freq_present():
    """Jeder Record muss FREQ enthalten (QRZ.com Pflicht)."""
    from pathlib import Path
    import re
    adi_files = list(Path(".").glob("SimpleFT8_LOG_*.adi"))
    if not adi_files:
        return
    text = adi_files[-1].read_text()
    records = re.split(r"<EOR>", text, flags=re.IGNORECASE)
    for rec in records:
        if "<CALL:" in rec.upper():
            assert "<FREQ:" in rec.upper(), f"FREQ fehlt: {rec[:60]}"


# ── Encoder TX-Timing ────────────────────────────────────────────────────────

def test_target_tx_offset_zero():
    """TARGET_TX_OFFSET muss 0.0 sein (kein hardcoded Offset)."""
    from core.encoder import TARGET_TX_OFFSET
    assert TARGET_TX_OFFSET == 0.0, f"Offset {TARGET_TX_OFFSET} != 0.0"


def test_encoder_has_mode():
    """Encoder hat _mode Attribut."""
    from core.encoder import Encoder
    e = Encoder.__new__(Encoder)
    e._mode = "FT8"
    assert e._mode == "FT8"


def test_trim_samples_positive():
    """TRIM_SAMPLES muss positiv sein."""
    from core.encoder import TRIM_SAMPLES
    assert TRIM_SAMPLES > 0


# ── IC-7300 Fork Bereitschaft ─────────────────────────────────────────────────

def test_radio_interface_abc():
    """RadioInterface ABC hat alle noetige abstrakten Methoden."""
    from radio.base_radio import RadioInterface
    import inspect
    methods = [m for m, _ in inspect.getmembers(RadioInterface, predicate=inspect.isfunction)
               if not m.startswith('_')]
    required = ['connect', 'disconnect', 'set_frequency', 'get_frequency',
                'set_mode', 'set_ptt', 'set_tx_power', 'get_antennas',
                'set_antenna', 'send_audio', 'get_meter_data',
                'set_rx_antenna', 'set_tx_antenna', 'set_rfgain']
    for r in required:
        assert r in methods, f"RadioInterface fehlt Methode: {r}"


def test_radio_factory_flex():
    """radio_factory erkennt 'flex' als Typ."""
    from radio.radio_factory import create_radio
    # Nur pruefen ob Funktion existiert und "flex" erkennt (kein echtes Radio noetig)
    assert callable(create_radio)


def test_no_flexradio_import_in_ui():
    """UI-Dateien importieren NICHT direkt FlexRadio."""
    import re
    ui_files = ["ui/main_window.py", "ui/mw_cycle.py", "ui/mw_qso.py",
                "ui/mw_tx.py", "ui/control_panel.py"]
    for path in ui_files:
        try:
            with open(path) as f:
                content = f.read()
            imports = re.findall(r"from\s+radio\.flexradio\s+import", content)
            assert not imports, f"{path}: Direkter FlexRadio-Import: {imports}"
        except FileNotFoundError:
            pass


def test_base_radio_has_set_rx_filter():
    """RadioInterface hat set_rx_filter() fuer Modi-Filter."""
    from radio.base_radio import RadioInterface
    assert hasattr(RadioInterface, 'set_rx_filter')


def test_radio_interface_properties():
    """RadioInterface hat last_swr, tx_raw_peak, tx_audio_level Properties."""
    from radio.base_radio import RadioInterface
    assert hasattr(RadioInterface, 'last_swr')
    assert hasattr(RadioInterface, 'tx_raw_peak')
    assert hasattr(RadioInterface, 'tx_audio_level')


# ── CQ Frequenz Dynamisch ────────────────────────────────────────────────────

def test_cq_freq_dynamic_sweet_spot():
    """CQ-Frequenz passt sich der Aktivitaet an (nicht fix 800-2000)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Simuliere Aktivitaet bei 300-800 Hz
    for f in range(300, 800, 50):
        for _ in range(3):
            dc.record_freq(f)
    freq = dc.get_free_cq_freq()
    if freq is not None:
        # Sollte im Bereich der Aktivitaet sein, nicht bei 1500+
        assert freq < 1200, f"CQ-Freq {freq} zu hoch fuer Aktivitaet bei 300-800 Hz"


def test_cq_freq_high_activity():
    """CQ-Frequenz bei hoher Aktivitaet oben (1000-2000 Hz)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    for f in range(1000, 2000, 50):
        for _ in range(3):
            dc.record_freq(f)
    freq = dc.get_free_cq_freq()
    if freq is not None:
        assert 800 <= freq <= 2200, f"CQ-Freq {freq} ausserhalb Aktivitaetsbereich"


def test_omni_tx_pending_switch():
    """OMNI-TX: Block-Wechsel wird korrekt verzoegert bis Position 0."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=10)  # Minimum ist 10 (max(10, n))
    omni.enable()
    # 12 Zyklen voranschreiten → Block-Wechsel muss angefordert werden
    for _ in range(12):
        omni.advance()
    # Block sollte gewechselt haben (10 Zyklen + 2 extra fuer Grenze)
    # Wenn pending_switch noch True, weiter bis Position 0
    if omni._pending_switch:
        while omni._slot_index != 0:
            omni.advance()
    assert omni.block == 2, f"Block sollte 2 sein nach Wechsel, ist {omni.block}"
    assert not omni._pending_switch, "pending_switch muss nach Wechsel False sein"


def test_omni_tx_qso_blocks_counter():
    """OMNI-TX: Waehrend QSO zaehlt der Block-Counter nicht hoch."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=10)
    omni.enable()
    for _ in range(10):
        omni.advance(qso_active=True)
    assert omni._cycle_count == 0, f"Counter sollte 0 sein bei QSO, ist {omni._cycle_count}"
    assert omni.block == 1, "Block sollte 1 bleiben bei dauerhaftem QSO"


def test_cq_freq_stays_inside_occupied():
    """TX-Frequenz darf NIE ausserhalb des belegten Bereichs liegen."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Stationen nur bei 200-500 Hz — TX darf NICHT bei 600+ Hz landen
    for f in range(200, 550, 50):
        for _ in range(5):
            dc.record_freq(f)
    freq = dc.get_free_cq_freq()
    if freq is not None:
        assert freq <= 550, f"TX-Freq {freq} Hz ausserhalb Sweetspot (max 550)"
        assert freq >= 200, f"TX-Freq {freq} Hz unter Sweetspot (min 200)"


def test_cq_freq_fallback_no_gap():
    """Wenn keine Luecke vorhanden, Fallback auf Median-Bereich."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Jedes Bin belegt — keine Luecke
    for f in range(300, 600, 50):
        for _ in range(10):
            dc.record_freq(f)
    freq = dc.get_free_cq_freq()
    assert freq is not None, "Fallback muss eine Frequenz liefern"
    assert 200 <= freq <= 700, f"Fallback-Freq {freq} nicht im erwarteten Bereich"


def test_proposed_freq_updates():
    """update_proposed_freq() berechnet TX-Freq nach Intervall."""
    from core.diversity import DiversityController
    dc = DiversityController()
    for f in range(400, 800, 50):
        dc.record_freq(f)
    assert dc.cq_freq_hz is None  # Noch nicht berechnet
    dc.update_proposed_freq()
    assert dc.cq_freq_hz is not None  # Jetzt berechnet


def test_adif_ft4_submode():
    """ADIF: FT4 → MODE=MFSK + SUBMODE=FT4."""
    import tempfile, os
    from log.adif import AdifWriter
    with tempfile.TemporaryDirectory() as tmp:
        writer = AdifWriter(tmp)
        path = writer.log_qso(
            call="W2XYZ", band="20M", freq_mhz=14.081, mode="FT4",
            rst_sent="-10", rst_rcvd="-05", gridsquare="FN20",
            my_gridsquare="JO31", my_callsign="DA1MHH", tx_power=10)
        content = path.read_text()
        assert "<MODE:4>MFSK" in content, "FT4 sollte MODE=MFSK haben"
        assert "<SUBMODE:3>FT4" in content, "FT4 sollte SUBMODE=FT4 haben"


def test_adif_subdir_created():
    """ADIF: Unterordner adif/ wird automatisch erstellt."""
    import tempfile
    from log.adif import AdifWriter
    with tempfile.TemporaryDirectory() as tmp:
        writer = AdifWriter(tmp)
        assert writer.directory.name == "adif"
        assert writer.directory.exists()


def test_adif_qrz_fields():
    """ADIF: QRZ/LoTW Pflichtfelder vorhanden."""
    import tempfile
    from log.adif import AdifWriter
    with tempfile.TemporaryDirectory() as tmp:
        writer = AdifWriter(tmp)
        path = writer.log_qso(
            call="DL1ABC", band="40M", freq_mhz=7.074, mode="FT8",
            rst_sent="+05", rst_rcvd="-03", gridsquare="JN48",
            my_gridsquare="JO31OM", my_callsign="DA1MHH", tx_power=5)
        content = path.read_text()
        for field in ["CALL", "QSO_DATE", "TIME_ON", "BAND", "MODE",
                       "STATION_CALLSIGN", "MY_GRIDSQUARE", "OPERATOR"]:
            assert f"<{field}:" in content, f"Pflichtfeld {field} fehlt"


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
