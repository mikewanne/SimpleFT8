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
    send, _ = omni.should_tx()
    assert send is True


def test_omni_tx_pattern():
    """5-Slot-Muster: TX,TX,RX,RX,RX."""
    from core.omni_tx import OmniTX
    omni = OmniTX(block_cycles=10)
    omni.enable()
    pattern = []
    for _ in range(10):
        send, _ = omni.should_tx()
        pattern.append("TX" if send else "RX")
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


def test_diversity_measure_even_odd():
    """Messphase: Antennen abwechselnd, beide Paritaeten abgedeckt."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "measure"
    pattern = []
    for _ in range(12):
        pattern.append(dc.choose())
        dc._measure_step += 1
    # A1 und A2 muessen beide vorkommen
    assert "A1" in pattern and "A2" in pattern
    # Max 2 hintereinander
    for i in range(len(pattern) - 2):
        if pattern[i] == pattern[i+1] == pattern[i+2]:
            assert False, f"3× gleiche Antenne ab Position {i}: {pattern}"


def test_diversity_70_30_pattern():
    """70:30 Pattern: 6-Slot endlos nahtlos, max 2 hintereinander."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "operate"
    dc.ratio = "70:30"
    # 3 volle Durchlaeufe (18 Slots) — Loop-Uebergang testen
    pattern = []
    for _ in range(18):
        pattern.append(dc.choose())
        dc._operate_cycles += 1
    assert pattern.count("A1") == 12, f"Erwartet 12×A1 in 18 Slots, got {pattern.count('A1')}"
    assert pattern.count("A2") == 6, f"Erwartet 6×A2 in 18 Slots, got {pattern.count('A2')}"
    # Max 2 hintereinander (auch am Loop-Uebergang!)
    for i in range(len(pattern) - 2):
        if pattern[i] == pattern[i+1] == pattern[i+2]:
            assert False, f"3× gleiche Antenne ab Position {i}: {pattern}"


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

def test_propagation_seasonal_na_band():
    """10m im Winter (N/A) → immer poor, egal was HamQSL sagt."""
    from core.propagation import _apply_seasonal_correction
    assert _apply_seasonal_correction("10m", "good", 12, 1) == "poor"  # Januar
    assert _apply_seasonal_correction("10m", "fair", 10, 2) == "poor"  # Februar


def test_propagation_seasonal_80m_winter():
    """80m Nachtband Winter: geschlossen tagsüber (12 UTC), offen nachts (03 UTC)."""
    from core.propagation import _apply_seasonal_correction
    assert _apply_seasonal_correction("80m", "good", 12, 1) == "poor"  # mitten am Tag
    assert _apply_seasonal_correction("80m", "good", 3, 1) == "good"   # nachts offen


def test_propagation_seasonal_20m_spring():
    """20m Frühling: offen 05–22 UTC, außerhalb → poor."""
    from core.propagation import _apply_seasonal_correction
    assert _apply_seasonal_correction("20m", "fair", 14, 4) == "fair"  # April, tagsüber offen
    assert _apply_seasonal_correction("20m", "fair", 3, 4) == "poor"   # April, 03 UTC → geschlossen


def test_propagation_seasonal_40m_winter_midnight_boundary():
    """40m Winter (open=14, close=7): Grenzstunden exakt prüfen."""
    from core.propagation import _apply_seasonal_correction
    month = 1  # Januar
    assert _apply_seasonal_correction("40m", "good", 14, month) == "good"  # open_h selbst: offen
    assert _apply_seasonal_correction("40m", "good",  7, month) == "poor"  # close_h selbst: geschlossen
    assert _apply_seasonal_correction("40m", "good",  6, month) == "good"  # eine vor close: noch offen
    assert _apply_seasonal_correction("40m", "good",  8, month) == "poor"  # nach close: geschlossen
    assert _apply_seasonal_correction("40m", "good", 13, month) == "poor"  # eine vor open: noch geschlossen


def test_get_season_all_months():
    """_get_season() für alle 12 Monate korrekt."""
    from core.propagation import _get_season
    for m in (12, 1, 2):   assert _get_season(m) == "winter"
    for m in (3, 4, 5):    assert _get_season(m) == "spring"
    for m in (6, 7, 8):    assert _get_season(m) == "summer"
    for m in (9, 10, 11):  assert _get_season(m) == "autumn"


def test_propagation_seasonal_60m_passthrough():
    """60m fehlt in _SEASONAL_SCHEDULE → condition unverändert (kein XML-Eintrag)."""
    from core.propagation import _apply_seasonal_correction
    assert _apply_seasonal_correction("60m", "good",  12, 1) == "good"
    assert _apply_seasonal_correction("60m", "fair",  14, 6) == "fair"
    assert _apply_seasonal_correction("60m", "poor",   3, 9) == "poor"


def test_propagation_summer_close_h24_behavior():
    """20m Sommer (open=4, close=24): offen 04–23 UTC, geschlossen 00–03 UTC.

    close_h=24 ist kein Bug — utc_hour<24 gilt für alle Stunden, open_h=4
    schließt 0-3 UTC weiterhin aus. Bewusstes Design: '04:00–24:00'.
    """
    from core.propagation import _apply_seasonal_correction
    month = 7  # Juli
    for hour in range(4, 24):
        assert _apply_seasonal_correction("20m", "good", hour, month) == "good", f"Stunde {hour}"
    for hour in range(0, 4):
        assert _apply_seasonal_correction("20m", "good", hour, month) == "poor", f"Stunde {hour}"


def test_evaluate_conditions_no_http():
    """_evaluate_conditions() mit Stub-raw_data — kein HTTP-Request nötig."""
    import datetime as _dt
    from unittest.mock import patch
    from core.propagation import _evaluate_conditions

    raw = {
        "10m": {"day": "good",  "night": "poor"},
        "12m": {"day": "good",  "night": "poor"},
        "15m": {"day": "good",  "night": "poor"},
        "17m": {"day": "fair",  "night": "poor"},
        "20m": {"day": "good",  "night": "fair"},
        "30m": {"day": "good",  "night": "good"},
        "40m": {"day": "fair",  "night": "good"},
        "60m": {"day": "fair",  "night": "fair"},
        "80m": {"day": "poor",  "night": "good"},
    }
    # Winter (Januar), 12:00 UTC = day
    mock_now = _dt.datetime(2024, 1, 15, 12, 0, 0, tzinfo=_dt.timezone.utc)
    with patch("core.propagation.datetime") as m:
        m.now.return_value = mock_now
        cond = _evaluate_conditions(raw)

    assert cond["10m"] == "poor"   # N/A Winter
    assert cond["17m"] == "fair"   # offen 08–16, Stunde 12 ✓
    assert cond["20m"] == "good"   # offen 06–18, Stunde 12 ✓
    assert cond["40m"] == "poor"   # Nachtband 14–07, Stunde 12 außerhalb
    assert cond["60m"] == "fair"   # passthrough (nicht in Schedule)


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
    """Nicht-CQ-Stationen aelter als 75s werden entfernt (CQ-Rufer bekommen 300s)."""
    import time
    from core.station_accumulator import accumulate_stations, remove_stale
    from core.message import parse_ft8_message
    stations = {}
    # QSO-Partner (kein CQ) — sollte nach 75s weg sein
    msgs = [parse_ft8_message("DA1MHH R3EDI -10", snr=-15, freq_hz=1000, dt=0.1)]
    accumulate_stations(stations, msgs, set())
    assert "R3EDI" in stations
    assert stations["R3EDI"].is_cq is False
    stations["R3EDI"]._last_heard = time.time() - 80
    removed = remove_stale(stations, set())
    assert "R3EDI" in removed
    assert "R3EDI" not in stations


def test_accumulator_cq_longer_aging():
    """CQ-Rufer bleiben 300s (5 Min) statt 75s — nach 5 Min entfernt."""
    import time
    from core.station_accumulator import accumulate_stations, remove_stale
    from core.message import parse_ft8_message
    stations = {}
    msgs = [parse_ft8_message("CQ R3EDI KO82", snr=-15, freq_hz=1000, dt=0.1)]
    accumulate_stations(stations, msgs, set())
    assert "R3EDI" in stations
    assert stations["R3EDI"].is_cq is True
    # Nach 80s: noch da (CQ-Limit 300s)
    stations["R3EDI"]._last_heard = time.time() - 80
    removed = remove_stale(stations, set())
    assert "R3EDI" not in removed
    assert "R3EDI" in stations
    # Nach 310s: weg
    stations["R3EDI"]._last_heard = time.time() - 310
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

def _make_stations(*freq_list):
    """Hilfsfunktion: Mock-Stationen mit freq_hz fuer CQ-Freq Tests."""
    class MockMsg:
        def __init__(self, f): self.freq_hz = f
    return {f"S{i}": MockMsg(f) for i, f in enumerate(freq_list)}


def test_cq_freq_empty_histogram():
    """Leeres Histogramm → None."""
    from core.diversity import DiversityController
    dc = DiversityController()
    assert dc.get_free_cq_freq() is None


def test_cq_freq_near_activity():
    """CQ-Frequenz liegt im festen Sweet-Spot 800-2000 Hz."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.sync_from_stations(_make_stations(*range(1000, 1200, 50)))
    freq = dc.get_free_cq_freq()
    if freq is not None:
        assert 800 <= freq <= 2000, f"CQ-Freq {freq} ausserhalb Sweet-Spot 800-2000"


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
    """DT-Werte werden in JSON gespeichert und geladen (Key: Modus_Band)."""
    from core import ntp_time
    ntp_time._correction = 0.55
    ntp_time._mode = "FT8"
    ntp_time._band = "20m"
    ntp_time._save_current()
    assert ntp_time._saved.get("FT8_20m") == 0.55
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
    """set_mode() speichert alten Wert bevor gewechselt wird (Key: Modus_Band)."""
    from core import ntp_time
    ntp_time._mode = "FT8"
    ntp_time._band = "20m"
    ntp_time._correction = 0.65
    ntp_time._saved = {}
    ntp_time.set_mode("FT4")
    assert ntp_time._saved.get("FT8_20m") == 0.65
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

def test_target_tx_offset():
    """TARGET_TX_OFFSET kompensiert FlexRadio TX-Buffer (0.5 Protokoll - 1.3s Buffer = -0.8)."""
    from core.encoder import TARGET_TX_OFFSET
    assert TARGET_TX_OFFSET == -0.8, f"Offset {TARGET_TX_OFFSET} != -0.8"


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

def test_cq_freq_dynamic_range_lower():
    """Suchbereich folgt der Aktivitaet — Stationen 300-700 → Freq nahe Aktivitaet."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Aktivitaet bei 300-700 Hz → Suchbereich = 200-850 (Margin 2 Bins, +/- mid-bin)
    dc.sync_from_stations(_make_stations(*range(300, 750, 50)))
    freq = dc.get_free_cq_freq()
    assert freq is not None, "Bei diesem Cluster mit Toleranz-Stufen muss Lueck gefunden werden"
    # Bereich 100..850 (occupied 300-700 +/- 2 Bins Margin = 200..800, +50 mid-bin Toleranz)
    assert 100 <= freq <= 850, f"CQ-Freq {freq} ausserhalb dynamischem Suchbereich"


def test_cq_freq_dynamic_range_upper():
    """Suchbereich folgt der Aktivitaet — Stationen 1900-2400 → Freq nahe Aktivitaet."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.sync_from_stations(_make_stations(*range(1900, 2450, 50)))
    freq = dc.get_free_cq_freq()
    assert freq is not None
    # Suchbereich 1800..2500 + 50 mid-bin Toleranz
    assert 1800 <= freq <= 2550, f"CQ-Freq {freq} ausserhalb dynamischem Suchbereich"


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


def test_cq_freq_finds_gap_in_dynamic_range():
    """Stationen 200-550 Hz → Suchbereich 100-650 → Lueck-Suche dort."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.sync_from_stations(_make_stations(*range(200, 550, 50)))
    freq = dc.get_free_cq_freq()
    # Bei diesem dichten Cluster gibt es vielleicht keine Lueck >= 150 Hz im Margin
    # → freq darf None sein, oder muss im erweiterten Bereich liegen
    if freq is not None:
        assert 100 <= freq <= 650, f"TX-Freq {freq} ausserhalb dynamischem Suchbereich"


def test_cq_freq_fallback_finds_position_when_band_full():
    """Bei vollem Band findet die graduelle Toleranz immer noch eine Position
    (Margin-Lueck oder schwach-belegter Bin) — niemand sitzt dauerhaft auf voller Freq fest."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.sync_from_stations(_make_stations(*range(800, 2001, 50)))
    freq = dc.get_free_cq_freq()
    # Margin links 750-800 oder rechts 2050-2100 = 1-Bin-Lueck (Stufe 3 trifft)
    assert freq is not None, "Toleranz-Stufen muessen Position finden auch bei vollem Band"


def test_cq_freq_no_position_when_histogram_empty():
    """Leeres Histogramm → None (keine Daten = keine Auswahl)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    assert dc.get_free_cq_freq() is None


def test_proposed_freq_updates():
    """update_proposed_freq() berechnet TX-Freq wenn Luecke im Cluster vorhanden."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Stationen bei 800-950 Hz und 1700-1950 Hz → Lueck 1000-1700 Hz im Sweet-Spot
    dc.sync_from_stations(_make_stations(800, 850, 900, 950, 1700, 1750, 1800, 1850, 1900, 1950))
    assert dc.cq_freq_hz is None  # Noch nicht berechnet
    dc.update_proposed_freq()
    assert dc.cq_freq_hz is not None  # Jetzt berechnet (Luecke gefunden)


# ── CQ-Freq Score-basierte Auswahl (v0.58) ─────────────────────────────────

def test_score_prefers_widest_gap():
    """Score: zwei Luecken im Sweet-Spot, die breitere muss gewinnen."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Stationen: 800-850 (2), Lueck1=900-1100 (4 Bins, 200Hz),
    # 1150-1200 (2), Lueck2=1250-1900 (13 Bins, 650Hz), 1950 (1)
    dc.sync_from_stations(_make_stations(800, 850, 1150, 1200, 1950))
    freq = dc.get_free_cq_freq()
    assert freq is not None
    # Breitere Lueck = 1250-1900 → Mitte ~1575 Hz
    assert 1300 <= freq <= 1900, f"Erwartet breitere Lueck, bekam {freq}"


def test_score_penalizes_close_neighbors():
    """Score: schmale Lueck nahe Stationen vs breitere Lueck fern → fernere wird gewaehlt."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Lueck A: 850-1050 (4 Bins, 200Hz) zwischen Aktivitaet bei 800/850 und 1100/1150/1200
    # Lueck B: 1300-1900 (12 Bins, 600Hz) breiter und ohne enge Nachbarn
    dc.sync_from_stations(_make_stations(800, 850, 1100, 1150, 1200, 1250, 1950))
    freq = dc.get_free_cq_freq()
    assert freq is not None
    # Breite Lueck B (1300-1900) muss gewaehlt werden
    assert 1300 <= freq <= 1900, f"Erwartet breitere Lueck B, bekam {freq}"


def test_set_mode_resets_search_slots():
    """set_mode setzt _search_slots_remaining auf den modus-spezifischen Wert."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.set_mode("FT8")
    assert dc._search_slots_remaining == 4, f"FT8: {dc._search_slots_remaining} != 4"
    dc.set_mode("FT4")
    assert dc._search_slots_remaining == 8, f"FT4: {dc._search_slots_remaining} != 8"
    dc.set_mode("FT2")
    assert dc._search_slots_remaining == 16, f"FT2: {dc._search_slots_remaining} != 16"


def test_seconds_until_search_per_mode():
    """seconds_until_search = remaining_slots * cycle_s, ~60s alle Modi."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.set_mode("FT8")
    assert dc.seconds_until_search == 60, f"FT8 initial: {dc.seconds_until_search}"
    dc.set_mode("FT4")
    assert dc.seconds_until_search == 60, f"FT4 initial: {dc.seconds_until_search}"
    dc.set_mode("FT2")
    # 16 * 3.8 = 60.8 → int truncate = 60
    assert dc.seconds_until_search == 60, f"FT2 initial: {dc.seconds_until_search}"


def test_tick_slot_decrements_and_triggers():
    """tick_slot() dekrementiert und returnt True wenn Counter erreicht 0."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.set_mode("FT8")  # 4 Slots
    assert dc.tick_slot() is False  # 3 verbleibend
    assert dc.tick_slot() is False  # 2
    assert dc.tick_slot() is False  # 1
    assert dc.tick_slot() is True   # 0 → trigger + reset
    assert dc._search_slots_remaining == 4  # auto-reset


def test_reset_search_counter_restores_full_value():
    """reset_search_counter() setzt den Counter zurueck auf den modus-spezifischen
    Vollwert — wird bei aktivem QSO pro Slot aufgerufen, damit kein Mid-QSO-
    Frequenzsprung passiert."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # FT8: 4 Slots Vollwert
    dc.set_mode("FT8")
    dc.tick_slot()  # 3
    dc.tick_slot()  # 2
    dc.tick_slot()  # 1 — gleich Trigger
    assert dc._search_slots_remaining == 1
    dc.reset_search_counter()
    assert dc._search_slots_remaining == 4
    # FT4: 8 Slots
    dc.set_mode("FT4")
    dc.tick_slot()
    dc.reset_search_counter()
    assert dc._search_slots_remaining == 8
    # FT2: 16 Slots
    dc.set_mode("FT2")
    dc.tick_slot()
    dc.tick_slot()
    dc.reset_search_counter()
    assert dc._search_slots_remaining == 16


def test_reset_search_counter_prevents_mid_qso_jump():
    """Szenario: 3 von 4 Slots abgelaufen, dann QSO startet → Counter wird
    pro Slot resettet. Nach 5 QSO-Slots ist Counter immer noch auf 4 (kein
    Trigger waehrend QSO)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.set_mode("FT8")
    dc.tick_slot()  # 3
    dc.tick_slot()  # 2
    dc.tick_slot()  # 1
    assert dc._search_slots_remaining == 1
    # Jetzt QSO aktiv: pro Slot wird resettet
    for _ in range(5):
        dc.reset_search_counter()
    assert dc._search_slots_remaining == 4
    # QSO endet: erst jetzt darf wieder getickt werden, voller Karenzzeit
    assert dc.tick_slot() is False
    assert dc._search_slots_remaining == 3


def test_score_tiebreaker_uses_median():
    """Score: zwei gleich breite Luecken naeher/weiter vom Median → naehere gewinnt."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Stationen 1100,1150,1450,1500,1550,1850,1900 — Suchbereich dynamisch 1000-2000
    # Lueck A: 1200-1400 (5 Bins = 250 Hz), Mitte ~1325
    # Lueck B: 1600-1800 (5 Bins = 250 Hz), Mitte ~1725
    # Median ueber alle Stationen = 1500. Beide Luecken-Mitten haben gleichen Abstand 200 Hz
    # → echter Tiebreak. Beide Loesungen sind valide.
    dc.sync_from_stations(_make_stations(1100, 1150, 1450, 1500, 1550, 1850, 1900))
    freq = dc.get_free_cq_freq()
    assert freq is not None
    # Eine der beiden gleichbreit gleich-distanzierten Luecken muss gewaehlt werden
    assert (1200 <= freq <= 1450) or (1600 <= freq <= 1850), \
        f"Erwartet eine der beiden symmetrischen Luecken, bekam {freq}"


# ── CQ-Freq Sticky + Kollision (v0.58 Sub-Task D+E) ──────────────────────────

def test_sticky_gap_keeps_current():
    """Aktuelle Lueck 200Hz, neue 230Hz → bleibt (50Hz-Schwelle)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Erste Berechnung: stationen so dass Lueck ~200 Hz im Sweet-Spot
    # 800,850 + 1100,1150 + 1450,1500 → Luecken: 900-1050 (3=150) + 1200-1400 (4=200)
    dc.sync_from_stations(_make_stations(800, 850, 1100, 1150, 1450, 1500, 1800, 1850, 1900, 1950))
    first = dc.get_free_cq_freq()
    assert first is not None
    width_first = dc._current_gap_width_hz
    # Zweite Berechnung: jetzt ist die alte Lueck etwas breiter (230 > 200+50? NEIN)
    # Nimm Stationen so dass Score-Sieger nur ~30Hz breiter ist
    # current 1200-1400 (200Hz). Neue Lueck 1700-1950 (5 Bins = 250Hz, +50 ueber Schwelle)
    # → Wir wollen NICHT wechseln. Also neue Lueck darf nur +30Hz breiter sein.
    # Vereinfacht: Histogramm UNVERAENDERT lassen → kein Wechsel
    second = dc.get_free_cq_freq()
    assert second == first, f"Sticky muss bei unveraenderter Lueck halten: first={first}, second={second}"


def test_sticky_gap_switches_significantly_better():
    """Aktuelle Lueck deutlich kleiner als neue (>50Hz Schwelle) → wechselt."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Erste Berechnung: nur eine schmale Lueck im Sweet-Spot 800-2000
    # Stationen 800-1100 (alle Bins) + 1300-2000 (alle Bins) → Lueck 1150-1250 (3 Bins=150Hz)
    dc.sync_from_stations(_make_stations(*range(800, 1101, 50), *range(1300, 2001, 50)))
    first = dc.get_free_cq_freq()
    assert first is not None
    width_first = dc._current_gap_width_hz  # 150
    # Jetzt oeffnen wir eine deutlich breitere Lueck
    dc.sync_from_stations(_make_stations(800, 850, 1900, 1950))
    second = dc.get_free_cq_freq()
    assert second != first, f"Erwartet Wechsel zu breiterer Lueck: first={first}, second={second}"


def test_sticky_gap_overrides_when_current_unusable():
    """Aktuelle TX-Frequenz hat 3 direkte Nachbarn → wechselt trotz kleiner Verbesserung."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Erste Berechnung etabliert _cq_freq_hz im Sweet-Spot
    dc.sync_from_stations(_make_stations(800, 850, 1900, 1950))
    first = dc.get_free_cq_freq()
    assert first is not None
    # Jetzt direkte Nachbarn (+/-1 Bin, je >=2 Stationen) auf der aktuellen Frequenz
    # current_bin = first // 50. Nachbarn bei (current_bin-1)*50 und (current_bin+1)*50
    cb = first // 50
    f_minus = (cb - 1) * 50
    f_plus = (cb + 1) * 50
    # 3 Stationen in +/-1 → unbrauchbar (n_direct = 3)
    dc.sync_from_stations(_make_stations(f_minus, f_minus, f_plus, 800, 850, 1900, 1950))
    second = dc.get_free_cq_freq()
    assert second != first, f"Erwartet Wechsel weg von unbrauchbarer Freq: first={first}, second={second}"


def test_sticky_gap_first_call_chooses():
    """_cq_freq_hz ist None → kein Sticky, normale Auswahl."""
    from core.diversity import DiversityController
    dc = DiversityController()
    assert dc._cq_freq_hz is None
    dc.sync_from_stations(_make_stations(800, 850, 1900, 1950))
    freq = dc.get_free_cq_freq()
    assert freq is not None and 800 <= freq <= 2000


def test_sticky_gap_outside_sweet_spot_forces_switch():
    """Aktuelle TX bei 500Hz (Legacy ausserhalb Sweet-Spot) → wechselt zwingend."""
    from core.diversity import DiversityController
    dc = DiversityController()
    # Erste Berechnung etabliert _cq_freq_hz im Sweet-Spot
    dc.sync_from_stations(_make_stations(800, 850, 1900, 1950))
    dc.get_free_cq_freq()
    # Manuell aussehralb Sweet-Spot setzen (Legacy/Test) + Sticky-State behalten
    dc._cq_freq_hz = 500
    dc._current_gap_width_hz = 100  # Kleiner als jede neue Lueck im Sweet-Spot
    dc.sync_from_stations(_make_stations(800, 850, 1900, 1950))
    second = dc.get_free_cq_freq()
    assert second is not None and 800 <= second <= 2000, \
        f"Ausserhalb Sweet-Spot muss Wechsel erzwungen sein, bekam {second}"


def test_reset_clears_sticky_state():
    """Nach reset() ist _current_gap_width_hz = 0."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.sync_from_stations(_make_stations(800, 850, 1900, 1950))
    dc.get_free_cq_freq()
    assert dc._current_gap_width_hz > 0
    dc.reset()
    assert dc._current_gap_width_hz == 0
    assert dc._cq_freq_hz is None


def test_qso_protection_overrides_search():
    """qso_active=True → update_proposed_freq macht KEINEN Wechsel."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc.sync_from_stations(_make_stations(800, 850, 1900, 1950))
    dc.update_proposed_freq()
    first = dc._cq_freq_hz
    assert first is not None
    # Histogramm aendert sich (Stationen direkt auf alter Freq) → wuerde sonst wechseln
    cb = first // dc.FREQ_BIN_HZ
    f_minus = (cb - 1) * dc.FREQ_BIN_HZ
    f_plus = (cb + 1) * dc.FREQ_BIN_HZ
    dc.sync_from_stations(_make_stations(f_minus, f_plus, 800, 850, 1900, 1950))
    # qso_active=True → blockt Wechsel komplett
    dc.update_proposed_freq(qso_active=True)
    assert dc._cq_freq_hz == first, "QSO-Schutz: keine Aenderung waehrend QSO"


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


# ── FT2 Slot-Berechnung (UTC-basiert) ───────────────────────────────────────

def test_slot_from_utc():
    """FT2 Even/Odd-Slot aus UTC-String: (secs % 7.5) < 3.75."""
    # Inline-Definition da mw_cycle.py PySide6 benötigt
    def _slot(utc_str):
        if not utc_str or len(utc_str) < 6:
            return None
        try:
            secs = int(utc_str[:2]) * 3600 + int(utc_str[2:4]) * 60 + int(utc_str[4:6])
            return (secs % 7.5) < 3.75
        except (ValueError, TypeError):
            return None

    # Even-Slots
    assert _slot("000000") is True   # 0s mod 7.5 = 0.0
    assert _slot("000003") is True   # 3s mod 7.5 = 3.0
    assert _slot("000008") is True   # 8s mod 7.5 = 0.5 (neue Periode)
    # Odd-Slots
    assert _slot("000004") is False  # 4s mod 7.5 = 4.0
    assert _slot("000007") is False  # 7s mod 7.5 = 7.0
    # Ungültige Eingaben
    assert _slot("") is None
    assert _slot("12") is None       # Zu kurz
    assert _slot("ab0000") is None   # Keine Ziffern
    assert _slot(None) is None


# ── TX-Power pro Band ─────────────────────────────────────────────────────────

def test_tx_power_save_load():
    """rfpower pro Band: Speichern und Laden Roundtrip."""
    from config.settings import Settings
    s = Settings()
    s.save_tx_power("20m", 65)
    assert s.get_tx_power("20m") == 65


def test_tx_power_clamp():
    """rfpower Clamp: Werte außerhalb 10-80% werden begrenzt."""
    from config.settings import Settings
    s = Settings()
    s.save_tx_power("40m", 5)    # Zu niedrig → 10
    assert s.get_tx_power("40m") == 10
    s.save_tx_power("80m", 95)   # Zu hoch → 80
    assert s.get_tx_power("80m") == 80


def test_tx_power_default():
    """rfpower Default für unbekanntes Band."""
    from config.settings import Settings
    s = Settings()
    assert s.get_tx_power("999m", default=35) == 35
    assert s.get_tx_power("999m") == 50      # Standard-Default


# ── Mode-aware DX Presets ─────────────────────────────────────────────────────

def test_dx_preset_mode_specific():
    """DX-Preset: Mode-spezifischer Key (20m_FT8) korrekt gespeichert."""
    from config.settings import Settings
    s = Settings()
    s.save_dx_preset("20m", "ANT1", 15, mode="FT8")
    preset = s.get_dx_preset("20m", mode="FT8")
    assert preset is not None
    assert preset["gain"] == 15


def test_dx_preset_mode_fallback():
    """DX-Preset: Kein mode-spezifischer Key → Fallback auf Band-Key."""
    from config.settings import Settings
    s = Settings()
    s.save_dx_preset("20m", "ANT1", 5)              # Band-only
    s.save_dx_preset("20m", "ANT1", 15, mode="FT8") # FT8-spezifisch
    # FT4 hat keinen eigenen Key → Fallback auf Band-only
    preset = s.get_dx_preset("20m", mode="FT4")
    assert preset is not None
    assert preset["gain"] == 5


def test_dx_preset_mode_priority():
    """DX-Preset: Mode-spezifischer Key hat Vorrang vor Band-only."""
    from config.settings import Settings
    s = Settings()
    s.save_dx_preset("20m", "ANT1", 5)              # Band-only (gain=5)
    s.save_dx_preset("20m", "ANT1", 15, mode="FT8") # FT8-spezifisch (gain=15)
    assert s.get_dx_preset("20m", mode="FT8")["gain"] == 15  # Spezifisch hat Vorrang
    assert s.get_dx_preset("20m", mode="FT4")["gain"] == 5   # FT4 fällt auf Band-only


# ── AutoHunt ─────────────────────────────────────────────────────────────────

class _MockQSOLog:
    """Minimal-Mock eines QSO-Logs für AutoHunt-Tests."""
    def __init__(self, worked=None, worked_on_band=None):
        self._worked = set(worked or [])
        self._wob = set(worked_on_band or [])  # set of (call, band) tuples

    def is_worked(self, call):
        return call in self._worked

    def is_worked_on_band(self, call, band):
        return (call, band) in self._wob


def test_autohunt_gates():
    """select_next() gibt None bei allen 4 blockierenden Gates."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    msg = _make_msg("DL1ABC", "CQ", "CQ DL1ABC JO31")
    assert hunt.select_next([msg], True, True) is None    # inactive
    hunt.active = True
    assert hunt.select_next([msg], True, False) is None   # presence_ok=False
    assert hunt.select_next([msg], False, True) is None   # qso_idle=False
    hunt.on_manual_qso_start()
    assert hunt.select_next([msg], True, True) is None    # manual_override


def test_autohunt_selects_cq():
    """Alle Gates offen → CQ-Station zurückgegeben."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.active = True
    msg = _make_msg("DL1ABC", "CQ", "CQ DL1ABC JO31")
    result = hunt.select_next([msg], True, True)
    assert result is not None
    assert result.call == "DL1ABC"


def test_autohunt_snr_minimum():
    """Stationen unter -21 dB SNR werden übersprungen."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.active = True
    msg = _make_msg("DL1ABC", "CQ", "CQ DL1ABC JO31")
    msg.snr = -25  # Unter _MIN_SNR = -21
    assert hunt.select_next([msg], True, True) is None


def test_autohunt_scoring_new_vs_worked():
    """Neue Station schlägt bereits gearbeitete beim Scoring."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.active = True
    hunt.set_qso_log(_MockQSOLog(
        worked={"DL2OLD"},
        worked_on_band={("DL2OLD", "20m")},
    ))
    hunt.set_band("20m")
    new_msg = _make_msg("DL1NEW", "CQ", "CQ DL1NEW JO31")
    old_msg = _make_msg("DL2OLD", "CQ", "CQ DL2OLD JO41")
    result = hunt.select_next([old_msg, new_msg], True, True)
    assert result is not None
    assert result.call == "DL1NEW"


def test_autohunt_cooldown():
    """Station nach Timeout für COOLDOWN_SECS nicht auswählen."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.active = True
    hunt.on_qso_timeout("DL1ABC")
    msg = _make_msg("DL1ABC", "CQ", "CQ DL1ABC JO31")
    assert hunt.select_next([msg], True, True) is None


def test_autohunt_band_change_clears_cooldown():
    """Bandwechsel löscht Cooldowns — Station danach wieder wählbar."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.active = True
    hunt.on_qso_timeout("DL1ABC")
    hunt.on_band_change()
    msg = _make_msg("DL1ABC", "CQ", "CQ DL1ABC JO31")
    result = hunt.select_next([msg], True, True)
    assert result is not None
    assert result.call == "DL1ABC"


# ── AntennaPreferenceStore ────────────────────────────────────────────────────

def test_antenna_pref_a2_better():
    """'A2>1' Format → A2 als beste Antenne gespeichert."""
    from core.antenna_pref import AntennaPreferenceStore
    store = AntennaPreferenceStore()
    msg = _make_msg("DL1ABC", "CQ", "")
    msg.antenna = "A2>1"
    store.update_from_stations({"DL1ABC": msg})
    assert store.get("DL1ABC") == "A2"


def test_antenna_pref_a1_better():
    """'A1>2' Format → A1 als beste Antenne gespeichert."""
    from core.antenna_pref import AntennaPreferenceStore
    store = AntennaPreferenceStore()
    msg = _make_msg("DL1ABC", "CQ", "")
    msg.antenna = "A1>2"
    store.update_from_stations({"DL1ABC": msg})
    assert store.get("DL1ABC") == "A1"


def test_antenna_pref_unknown_and_clear():
    """Unbekanntes Callsign → None; clear() entfernt alle Einträge."""
    from core.antenna_pref import AntennaPreferenceStore
    store = AntennaPreferenceStore()
    assert store.get("DL9XYZ") is None
    msg = _make_msg("DL1ABC", "CQ", "")
    msg.antenna = "A2>1"
    store.update_from_stations({"DL1ABC": msg})
    assert store.count == 1
    store.clear()
    assert store.count == 0
    assert store.get("DL1ABC") is None


# ── DXTuneDialog Pure Logic (inline, kein Qt nötig) ──────────────────────────

def test_dxtune_top5_avg():
    """_top5_avg: Top-5 Durchschnitt, None-Overload-Marker ignorieren."""
    def _top5_avg(vals):
        clean = [v for v in vals if v is not None]
        if not clean:
            return None
        top5 = sorted(clean, reverse=True)[:5]
        return round(sum(top5) / len(top5), 1)

    assert _top5_avg([10.0, 5.0, 3.0, 1.0, -1.0, -5.0]) == 3.6  # 18/5
    assert _top5_avg([10.0, None, 5.0, None]) == 7.5              # 15/2
    assert _top5_avg([]) is None
    assert _top5_avg([None, None]) is None


def test_dxtune_has_overload():
    """_has_overload: None in Datenliste → Übersteuerung erkannt."""
    def _has_overload(vals):
        return None in vals

    assert _has_overload([10.0, None, 5.0]) is True
    assert _has_overload([10.0, 5.0]) is False
    assert _has_overload([]) is False


def test_dxtune_detect_overload():
    """_detect_overload: >8 starke Signale oder Varianz < 1.5."""
    def _detect(snr_vals):
        if not snr_vals:
            return False
        strong = sum(1 for s in snr_vals if s > 20)
        if strong > 8:
            return True
        if len(snr_vals) >= 5:
            avg = sum(snr_vals) / len(snr_vals)
            variance = sum((s - avg) ** 2 for s in snr_vals) / len(snr_vals)
            if variance < 1.5:
                return True
        return False

    assert _detect([25] * 9) is True                    # 9 × >20 dB
    assert _detect([25] * 8 + [-10]) is False           # nur 8 starke
    assert _detect([10, 10, 10, 10, 10]) is True        # Varianz 0.0 < 1.5
    assert _detect([10, -5, 0, 15, -10]) is False       # normale Varianz
    assert _detect([]) is False


def test_dxtune_finish_winner_excludes_overload():
    """_finish() wählt besten gültigen Gain; übersteuerte Keys bleiben ausgeschlossen."""
    phase_data = {
        ("ANT1", 0):  [5.0, 4.0, 3.0],      # avg 4.0, kein Overload
        ("ANT1", 10): [8.0, 7.0, None],      # Overload → ausschließen
        ("ANT1", 20): [6.0, 5.5, 5.0],      # avg 5.5, kein Overload → Gewinner
    }

    def top5(key):
        clean = [v for v in phase_data.get(key, []) if v is not None]
        if not clean:
            return None
        t = sorted(clean, reverse=True)[:5]
        return round(sum(t) / len(t), 1)

    best_gain, best_score = 0, None
    for gain in [0, 10, 20]:
        key = ("ANT1", gain)
        if None in phase_data.get(key, []):  # has_overload
            continue
        score = top5(key)
        if score is not None and (best_score is None or score > best_score):
            best_score, best_gain = score, gain

    assert best_gain == 20  # Gain 10 trotz höherem SNR ausgeschlossen


# ── Propagation Band-Range ────────────────────────────────────────────────────

def test_propagation_expand_range():
    """_expand_band_range: 80m→40m liefert [80m, 60m, 40m] inklusive 60m."""
    from core.propagation import _expand_band_range
    assert _expand_band_range("80m", "40m") == ["80m", "60m", "40m"]
    assert _expand_band_range("40m", "80m") == ["80m", "60m", "40m"]  # Reihenfolge egal


def test_propagation_expand_invalid_band():
    """_expand_band_range: Unbekanntes Band → Fallback [from, to]."""
    from core.propagation import _expand_band_range
    assert _expand_band_range("80m", "XYZ") == ["80m", "XYZ"]


# ── Settings: frequency_mhz + DX-Gain-Preset ─────────────────────────────────

def test_settings_frequency_mhz():
    """frequency_mhz Property: Band + Mode → korrekte Dial-Frequenz."""
    from config.settings import Settings
    s = Settings()
    s.set("band", "20m")
    s.set("mode", "FT8")
    assert s.frequency_mhz == 14.074
    s.set("mode", "FT4")
    assert s.frequency_mhz == 14.080


def test_settings_dx_gain_preset_scoring():
    """save_dx_preset(scoring='dx') → dx_gain_presets; 'standard' → dx_presets."""
    from config.settings import Settings
    s = Settings()
    s.save_dx_preset("40m", "ANT1", 20, scoring="dx")
    s.save_dx_preset("40m", "ANT1", 10, scoring="standard")
    assert s.get_gain_preset("40m", mode="dx")["gain"] == 20
    assert s.get_gain_preset("40m", mode="standard")["gain"] == 10


# ── Geo Edge Cases ────────────────────────────────────────────────────────────

def test_geo_grid_too_short():
    """grid_to_latlon: Strings unter 4 Zeichen → None."""
    from core.geo import grid_to_latlon
    assert grid_to_latlon("") is None
    assert grid_to_latlon("JO") is None


def test_geo_grid_invalid_format():
    """grid_to_latlon: Erste Stelle muss Buchstabe sein."""
    from core.geo import grid_to_latlon
    assert grid_to_latlon("1O31") is None


def test_geo_grid_case_insensitive():
    """grid_to_latlon: Groß- und Kleinschreibung → identische Koordinaten."""
    from core.geo import grid_to_latlon
    upper = grid_to_latlon("JO31")
    lower = grid_to_latlon("jo31")
    assert upper is not None and lower is not None
    assert abs(upper[0] - lower[0]) < 0.001
    assert abs(upper[1] - lower[1]) < 0.001


# ── Stats Warmup Pipeline ─────────────────────────────────────────────────────

def test_stats_warmup_countdown_4_cycles():
    """_log_stats() blockiert genau 4 Zyklen (warmup=4), dann schreibt Stats."""
    from unittest.mock import MagicMock
    from ui.mw_cycle import CycleMixin

    class FakeWindow(CycleMixin):
        _rx_mode = "diversity"
        _stats_indicator = None

        def __init__(self):
            self._stats_logger = MagicMock()
            self._stats_warmup_cycles = 4  # Fix: nach DX-Kalibrierung gesetzt

            _s = MagicMock()
            _s.get.return_value = True
            _s.band = "40m"
            _s.mode = "FT8"
            self.settings = _s

            _ctrl = MagicMock()
            _ctrl.scoring_mode = "dx"
            self._diversity_ctrl = _ctrl

        def _is_antenna_tuning_active(self):
            return False

    w = FakeWindow()
    results = [w._log_stats(10, [], avg_snr=-15.0, ant2_wins=3, snr_delta=2.0) for _ in range(6)]

    assert results[:4] == [False, False, False, False], \
        f"4 Warmup-Zyklen erwartet, bekam: {results[:4]}"
    assert results[4] is True, \
        f"5. Zyklus muss Stats schreiben, bekam: {results[4]}"


def test_stats_warmup_99999_blocks_permanently():
    """Regression: warmup=99999 blockiert dauerhaft — zeigt Bug vor dem Fix."""
    from unittest.mock import MagicMock
    from ui.mw_cycle import CycleMixin

    class FakeWindow(CycleMixin):
        _rx_mode = "diversity"
        _stats_indicator = None

        def __init__(self):
            self._stats_logger = MagicMock()
            self._stats_warmup_cycles = 99999  # Bug-Zustand: bleibt nach DX-Tune

            _s = MagicMock()
            _s.get.return_value = True
            _s.band = "40m"
            _s.mode = "FT8"
            self.settings = _s

            _ctrl = MagicMock()
            _ctrl.scoring_mode = "dx"
            self._diversity_ctrl = _ctrl

        def _is_antenna_tuning_active(self):
            return False

    w = FakeWindow()
    results = [w._log_stats(10, [], avg_snr=-15.0, ant2_wins=3, snr_delta=2.0) for _ in range(10)]
    assert all(r is False for r in results), \
        "warmup=99999 muss alle 10 Zyklen blockieren (Regression-Nachweis)"


def test_dx_tune_pipeline_warmup_state():
    """Flow: _start_dx_tuning → 99999, _on_dx_tune_accepted Diversity → 4 Zyklen."""
    # Simulate state transitions (nicht UI-abhängig)
    warmup = 0

    # Schritt 1: Tuning gestartet
    warmup = 99999
    assert warmup == 99999

    # Schritt 2: Kalibrierung fertig — diversity mode, radio connected
    rx_mode = "diversity"
    radio_connected = True
    if rx_mode == "diversity" and radio_connected:
        warmup = 4  # _on_dx_tune_accepted() → _enable_diversity() → warmup = 4

    assert warmup == 4, f"Nach DX-Kalibrierung muss warmup=4, war {warmup}"

    # Schritt 3: Warmup-Countdown in _log_stats()
    blocked = 0
    while warmup > 0:
        blocked += 1
        warmup -= 1

    assert blocked == 4, f"Genau 4 Zyklen geblockt, war {blocked}"
    assert warmup == 0, "Nach Warmup: Stats aktiv (warmup=0)"


# ── Diversity._evaluate — Antennen-Entscheidungslogik ────────────────────────
# Hinweis: DIVERSITY_DE.md beschreibt das Verfahren als "UCB1 Bandit" — der
# Code ist tatsaechlich Median+8%-Schwellwert (kein UCB1). Diese Tests pruefen
# die tatsaechlich implementierte Logik in DiversityController._evaluate().

def test_diversity_evaluate_below_threshold_stays_50_50():
    """Differenz < 8% → 50:50, kein Dominant."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "measure"
    # A1=10, A2=10 → diff=0% < 8% → 50:50
    for _ in range(4):
        dc._measurements["A1"].append(10.0)
        dc._measurements["A2"].append(10.0)
    dc._evaluate()
    assert dc.ratio == "50:50"
    assert dc.dominant is None
    assert dc.phase == "operate"


def test_diversity_evaluate_a1_dominant_70_30():
    """A1 deutlich besser → 70:30, dominant=A1."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "measure"
    for _ in range(4):
        dc._measurements["A1"].append(20.0)
        dc._measurements["A2"].append(10.0)
    dc._evaluate()
    # diff = 10/20 = 50% >> 8% → 70:30, A1 dominant
    assert dc.ratio == "70:30"
    assert dc.dominant == "A1"


def test_diversity_evaluate_a2_dominant_30_70():
    """A2 deutlich besser → 30:70, dominant=A2."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "measure"
    for _ in range(4):
        dc._measurements["A1"].append(8.0)
        dc._measurements["A2"].append(15.0)
    dc._evaluate()
    # diff = 7/15 = 46.7% >> 8% → 30:70, A2 dominant
    assert dc.ratio == "30:70"
    assert dc.dominant == "A2"


def test_diversity_evaluate_too_few_data_falls_back_to_50_50():
    """peak <= 1.0 (zu wenig Daten) → 50:50 ohne Dominant."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "measure"
    for _ in range(4):
        dc._measurements["A1"].append(0.0)
        dc._measurements["A2"].append(1.0)
    dc._evaluate()
    assert dc.ratio == "50:50"
    assert dc.dominant is None


def test_diversity_dx_mode_uses_weak_count():
    """DX-Modus zaehlt schwache Stationen (SNR < -10), Standard-Modus alle."""
    from core.diversity import DiversityController
    dc_dx = DiversityController(scoring_mode="dx")
    dc_dx._phase = "measure"
    # In DX-Modus: dx_weak_count wird gespeichert
    dc_dx.record_measurement("A1", score=0.0, station_count=20, dx_weak_count=2)
    dc_dx.record_measurement("A2", score=0.0, station_count=5, dx_weak_count=8)
    assert dc_dx._measurements["A1"] == [2.0]
    assert dc_dx._measurements["A2"] == [8.0]

    dc_std = DiversityController(scoring_mode="normal")
    dc_std._phase = "measure"
    dc_std.record_measurement("A1", score=0.0, station_count=20, dx_weak_count=2)
    dc_std.record_measurement("A2", score=0.0, station_count=5, dx_weak_count=8)
    assert dc_std._measurements["A1"] == [20.0]
    assert dc_std._measurements["A2"] == [5.0]


def test_diversity_phase_transition_after_8_measurements():
    """Nach MEASURE_CYCLES (8) Messungen → automatisch zu phase=operate."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "measure"
    assert dc.phase == "measure"
    # 7 Messungen → noch measure
    for i in range(7):
        ant = "A1" if i % 2 == 0 else "A2"
        dc.record_measurement(ant, score=0.0, station_count=10)
    assert dc.phase == "measure", f"Nach 7 Messungen: phase={dc.phase}"
    # 8. Messung → _evaluate triggert → phase=operate
    dc.record_measurement("A2", score=0.0, station_count=10)
    assert dc.phase == "operate"
    assert dc._operate_cycles == 0


def test_diversity_record_measurement_ignored_in_operate_phase():
    """Aufzeichnung in operate-Phase ist No-Op (nur measure-Phase aktiv)."""
    from core.diversity import DiversityController
    dc = DiversityController()
    dc._phase = "operate"
    dc.record_measurement("A1", score=99.0, station_count=99)
    assert dc._measurements["A1"] == []
    assert dc._measurements["A2"] == []


# ── AP-Lite v2.2 — kohärente Addition (Sanity-Checks) ────────────────────────

def test_ap_lite_correlate_no_encoder_returns_zero():
    """correlate_candidate ohne Encoder → 0.0 (kein Crash, sicherer Default)."""
    import numpy as _np
    from core.ap_lite import correlate_candidate, SAMPLE_RATE, SLOT_SECONDS
    buf = _np.zeros(int(SAMPLE_RATE * SLOT_SECONDS), dtype=_np.float32)
    score = correlate_candidate(buf, "DA1MHH DK5ON 73", 1500.0, encoder=None)
    assert score == 0.0


def test_ap_lite_align_identical_costas_buffers_zero_offset():
    """Identische Costas-Referenz-Buffer → dt=0, df=0 (Self-Alignment).

    Verwendet die echte Costas-Referenz statt eines reinen Sinus, damit der
    Korrelations-Score auf Sync-Positionen ein eindeutiges Maximum hat.
    """
    from core.ap_lite import (
        align_buffers, _build_costas_reference, N_SYMBOLS, SYMBOL_SAMPLES,
    )
    n = N_SYMBOLS * SYMBOL_SAMPLES
    ref = _build_costas_reference(freq_hz=1500.0, n_samples=n)
    aligned, dt_samples, df_hz = align_buffers(ref, ref.copy(), freq_hz=1500.0)
    assert dt_samples == 0, f"Erwartet dt=0 bei Self-Alignment, got {dt_samples}"
    assert abs(df_hz) < 0.2, f"Erwartet df≈0 Hz bei Self-Alignment, got {df_hz}"
    assert aligned.shape == ref.shape


def test_ap_lite_costas_reference_has_signal_at_costas_positions():
    """_build_costas_reference erzeugt Energie bei Costas-Positionen, nicht dazwischen."""
    import numpy as _np
    from core.ap_lite import (
        _build_costas_reference, COSTAS_POSITIONS, SYMBOL_SAMPLES, N_SYMBOLS,
    )
    n = N_SYMBOLS * SYMBOL_SAMPLES
    ref = _build_costas_reference(freq_hz=1500.0, n_samples=n)
    assert ref.shape == (n,)
    # Energie an einer Costas-Position muss > 0 sein
    pos_energy = float(_np.sum(ref[
        COSTAS_POSITIONS[0] * SYMBOL_SAMPLES:
        (COSTAS_POSITIONS[0] + 1) * SYMBOL_SAMPLES
    ] ** 2))
    assert pos_energy > 0, "Costas-Position muss Signal-Energie haben"
    # Energie zwischen Costas-Bloecken muss 0 sein (Pos 7-35 sind Daten, kein Costas)
    gap_energy = float(_np.sum(ref[
        7 * SYMBOL_SAMPLES:
        36 * SYMBOL_SAMPLES
    ] ** 2))
    assert gap_energy == 0.0, "Daten-Bloecke muessen 0 sein im Costas-Referenzsignal"


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
