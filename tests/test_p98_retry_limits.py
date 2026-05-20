"""P98 (20.05.2026, v0.97.70) — Retry-Limits 3 → 5.

Mike-Field-Test 20.05.2026:
- TA4SSK: 3. Sende-Versuch hat noch gerade die Antwort gebracht → 3 ist knapp
- DG8DBW: Report empfangen, 2× RR73 gesendet → Timeout (zu früh)

Mike-Spec + DeepSeek-R1-Brainstorm-Empfehlung: beide Retry-Limits auf 5.
- `MAX_RR73_RETRIES`: 3 → 5 (Modul-Konstante in core/qso_state.py)
- `max_calls` Default: 3 → 5 (QSOData dataclass + alle Settings-Fallbacks)

R1-F2-Bugfix: `ui/mw_cycle.py:515` war hartcodiert auf 3 → liest jetzt
aus Settings (sonst ignoriert Auto-Hunt das User-Setting).
R1-F3: Tests importieren `MAX_RR73_RETRIES` statt 5 zu hartcodieren.

Test-Coverage:
- T1: MAX_RR73_RETRIES == 5 (Konstante hochgesetzt)
- T2: QSOData.max_calls Default == 5
- T3: QSOStateMachine.max_calls Default == 5
- T4: WAIT_REPORT erlaubt 5 Retries vor TIMEOUT
- T5: WAIT_RR73 erlaubt 5 Retries vor TIMEOUT
- T6: Settings-Fallback in main_window/mw_qso ist 5
- T7: mw_cycle Auto-Hunt-Pfad liest aus Settings (R1-F2 Bugfix)
- T8: 5 Retries x ~30s passt unter MAX_QSO_DURATION = 180s
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_t1_max_rr73_retries_is_5():
    """P98: MAX_RR73_RETRIES wurde von 3 auf 5 erhöht."""
    from core.qso_state import MAX_RR73_RETRIES
    assert MAX_RR73_RETRIES == 5, (
        "P98: MAX_RR73_RETRIES muss 5 sein (Mike-Field-Test "
        "Beobachtung: bei halbem QSO 3 Retries zu knapp)")


def test_t2_qsodata_max_calls_default_is_5():
    """P98: QSOData.max_calls Klassen-Default ist 5."""
    from core.qso_state import QSOData
    qd = QSOData()
    assert qd.max_calls == 5, "P98: QSOData.max_calls Default muss 5 sein"


def test_t3_state_machine_max_calls_default_is_5():
    """P98: QSOStateMachine.__init__ setzt max_calls auf 5."""
    from core.qso_state import QSOStateMachine
    sm = QSOStateMachine("DA1MHH", "JO31")
    assert sm.max_calls == 5, (
        "P98: QSOStateMachine.max_calls Default muss 5 sein")


def test_t4_wait_report_allows_5_retries():
    """P98: WAIT_REPORT lässt 5 Retries laufen bevor TIMEOUT."""
    from core.qso_state import QSOStateMachine, QSOState
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.WAIT_REPORT
    sm.qso.their_call = "DA1TST"
    sm.qso.our_snr = "-12"
    sm.qso.calls_made = 1   # initial Send hat schon stattgefunden
    sm.qso.max_calls = 5    # P98 Default
    sent = []
    timeouts = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.qso_timeout.connect(lambda c: timeouts.append(c))

    # Simuliere 4 Retry-Zyklen (calls_made geht von 1 → 5)
    for retry_round in range(4):
        sm.qso.timeout_cycles = 1  # on_cycle_end hat schon inkrementiert
        sm.on_decoder_finished()
        sm.state = QSOState.WAIT_REPORT
        sm.qso.timeout_cycles = 0
    # Nach 4 Retries: calls_made = 5 (initial 1 + 4 Retries)
    assert sm.qso.calls_made == 5
    assert len(sent) == 4
    assert len(timeouts) == 0, "Noch kein Timeout nach 4 Retries"

    # 5. Retry-Versuch sollte TIMEOUT auslösen weil calls_made == max_calls
    sm.qso.timeout_cycles = 1
    sm.on_decoder_finished()
    # Timeout-Signal emittiert; State wird via _resume_cq_if_needed
    # weitergeschaltet (z.B. zu IDLE), darum prüfen wir das Signal.
    assert len(timeouts) == 1, (
        "P98: 5. Retry mit calls_made == max_calls (5) muss TIMEOUT-Signal triggern")
    assert timeouts[0] == "DA1TST"
    assert len(sent) == 4, (
        "Kein weiterer Send nach Timeout (Retry-Limit erreicht)")


def test_t5_wait_rr73_allows_5_retries():
    """P98: WAIT_RR73 lässt 5 Retries laufen bevor TIMEOUT."""
    from core.qso_state import QSOStateMachine, QSOState, MAX_RR73_RETRIES
    sm = QSOStateMachine("DA1MHH", "JO31")
    sm.state = QSOState.WAIT_RR73
    sm.qso.their_call = "DA1TST"
    sm.qso.our_snr = "R-15"
    sm.qso.rr73_retries = 0
    sent = []
    timeouts = []
    sm.send_message.connect(lambda m: sent.append(m))
    sm.qso_timeout.connect(lambda c: timeouts.append(c))

    # Simuliere MAX_RR73_RETRIES (=5) Retries
    for retry_round in range(MAX_RR73_RETRIES):
        sm.qso.timeout_cycles = 1
        sm.on_decoder_finished()
        # Nach Retry: state=TX_REPORT, timeout_cycles=0
        assert sm.state == QSOState.TX_REPORT
        sm.state = QSOState.WAIT_RR73  # zurück für nächsten Cycle
    assert sm.qso.rr73_retries == MAX_RR73_RETRIES  # 5
    assert len(sent) == MAX_RR73_RETRIES
    assert len(timeouts) == 0, "Noch kein Timeout nach 5 Retries"

    # Nächster Retry-Versuch → TIMEOUT (rr73_retries > MAX)
    sm.qso.timeout_cycles = 1
    sm.on_decoder_finished()
    assert len(timeouts) == 1, (
        "P98: nach 5 Retries muss TIMEOUT-Signal greifen")
    assert timeouts[0] == "DA1TST"
    assert len(sent) == MAX_RR73_RETRIES, (
        "Kein weiterer Send nach Timeout")


def test_t6_settings_fallback_is_5():
    """P98: Settings-Fallbacks `get("max_calls", X)` müssen X=5 sein."""
    import inspect
    from ui import main_window, mw_qso

    mw_src = inspect.getsource(main_window)
    qso_src = inspect.getsource(mw_qso)

    # Es darf KEIN `get("max_calls", 3)` mehr geben
    assert 'get("max_calls", 3)' not in mw_src, (
        "P98: main_window.py darf nicht mehr get('max_calls', 3) nutzen")
    assert 'get("max_calls", 3)' not in qso_src, (
        "P98: mw_qso.py darf nicht mehr get('max_calls', 3) nutzen")
    # 5er-Fallback muss da sein
    assert 'get("max_calls", 5)' in mw_src
    assert 'get("max_calls", 5)' in qso_src


def test_t7_mw_cycle_reads_from_settings_not_hardcoded():
    """P98 R1-F2-Bugfix: Auto-Hunt-Pfad in mw_cycle liest max_calls aus
    Settings statt hartcodiert 3 zu setzen."""
    import inspect
    import re
    from ui import mw_cycle
    src = inspect.getsource(mw_cycle)
    # Kommentar-Zeilen ausfiltern (Beschreibungen können „= 3" enthalten)
    code_lines = [ln for ln in src.splitlines()
                  if not ln.strip().startswith("#")]
    code_only = "\n".join(code_lines)
    # Hartcodierte 3 darf in CODE nicht mehr existieren
    assert not re.search(r"self\.qso_sm\.max_calls\s*=\s*3\b", code_only), (
        "P98 R1-F2: mw_cycle darf max_calls NICHT mehr hartcodieren auf 3")
    # Aus Settings lesen
    assert 'self.settings.get("max_calls"' in code_only, (
        "P98 R1-F2: mw_cycle muss max_calls aus Settings lesen")


def test_t8_5_retries_fit_under_qso_duration():
    """P98: 5 Retries × 30s = 150s bleibt unter MAX_QSO_DURATION = 180s.

    Mathematische Verifikation des Zeit-Budgets — 6 TX-Slots
    (initial + 5 Retries) + 5 RX-Slots dazwischen = 11 × 15s = 165s.
    Knapp aber drin.
    """
    from core.qso_state import MAX_QSO_DURATION, MAX_RR73_RETRIES
    FT8_SLOT_S = 15
    initial_send = 1
    total_sends = initial_send + MAX_RR73_RETRIES  # 6
    rx_slots_between = MAX_RR73_RETRIES  # 5
    total_slots = total_sends + rx_slots_between  # 11
    worst_case_s = total_slots * FT8_SLOT_S
    assert worst_case_s < MAX_QSO_DURATION, (
        f"P98: {worst_case_s}s muss < {MAX_QSO_DURATION}s sein "
        "(Gesamt-Timeout greift sonst vor Retry-Limit)")


def test_t9_config_settings_default_is_5():
    """P98: config/settings.py initial-Default ist 5 (statt 99)."""
    from config.settings import Settings
    # Defaults inspizieren über frische Settings-Instanz
    # ohne externe Datei (in-memory)
    src = inspect.getsource(Settings)
    # _DEFAULTS-Block enthält max_calls: 5
    import config.settings as settings_module
    src_full = inspect.getsource(settings_module)
    assert '"max_calls": 5' in src_full, (
        "P98: config/settings.py DEFAULTS muss max_calls: 5 sein")


def test_t10_settings_dialog_reset_uses_5():
    """P98: Settings-Dialog _reset_defaults setzt Combo auf Index 1 (=5)."""
    import inspect
    from ui import settings_dialog
    src = inspect.getsource(settings_dialog)
    # Reset-Block setzt jetzt Index 1 (5W), nicht mehr 3 (99W)
    assert "max_calls_combo.setCurrentIndex(1)" in src, (
        "P98: Reset-Default muss auf Index 1 (=5) zeigen")
