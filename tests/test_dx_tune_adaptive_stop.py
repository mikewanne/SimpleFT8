"""Tests fuer Adaptiv-Stop Phase 2 (Block 2 #7, v0.91).

Pruefen:
- Stop nach Runde 1 (4 Schritte) bei klarer Differenz (Δ_SNR>=4dB ODER Δ_STAT>=50%)
- Kein Stop bei fairen Verhaeltnissen
- Kein Stop bei Overload in einem Bucket
- Kein Stop bei zu wenig Stationen pro Bucket (<5)
- Stop ruft _finish() auf

Whitebox-Tests via _check_phase2_early_stop() — setzt _phase_data direkt.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.dx_tune_dialog import DXTuneDialog


def _ensure_app():
    return QApplication.instance() or QApplication([])


class _MockRadio:
    """Minimal-Mock fuer DXTuneDialog-Konstruktor."""
    def set_rx_antenna(self, ant): pass
    def set_rfgain(self, gain): pass
    def set_tx_antenna(self, ant): pass


def _make_dlg(scoring_mode="snr"):
    """DXTuneDialog mit Mock-Radio + _step bei 4 (Runde 1 fertig)."""
    _ensure_app()
    dlg = DXTuneDialog(_MockRadio(), "40m", scoring_mode=scoring_mode, rx_mode="diversity")
    dlg._step = 4  # Runde 1 abgeschlossen
    return dlg


def _populate_phase_data(dlg, ant1_snrs, ant2_snrs, gain=20):
    """Setzt _phase_data fuer Tests. Es werden die Werte fuer den
    'besseren' Gain (default 20) gefuettert; fuer den anderen Gain
    werden 5 schlechte Werte gesetzt um Pre-Conditions (>=5 St.) zu
    erfuellen.
    """
    other_gain = 10 if gain == 20 else 20
    dlg._phase_data[("ANT1", gain)] = list(ant1_snrs)
    dlg._phase_data[("ANT2", gain)] = list(ant2_snrs)
    dlg._phase_data[("ANT1", other_gain)] = [-15.0] * 5
    dlg._phase_data[("ANT2", other_gain)] = [-15.0] * 5


# ───── Stop-Cases ────────────────────────────────────────────────────


def test_phase2_stop_on_clear_snr_diff():
    """ANT1 deutlich staerker (Δ_SNR > 4dB) → Stop."""
    dlg = _make_dlg(scoring_mode="snr")
    # ANT1@20 = 0 dB Top5, ANT2@20 = -10 dB → Δ=10dB
    _populate_phase_data(
        dlg,
        ant1_snrs=[0, -1, -2, -3, -4, -5, -6, -7, -8, -9],   # 10 St.
        ant2_snrs=[-10, -11, -12, -13, -14, -15, -16, -17, -18, -19],  # 10 St.
    )
    assert dlg._check_phase2_early_stop() is True


def test_phase2_stop_on_clear_station_diff():
    """ANT1 viel mehr Stationen (Δ_STAT >= 50%) → Stop, scoring_mode='stations'."""
    dlg = _make_dlg(scoring_mode="stations")
    # ANT1=20 St., ANT2=8 St. → Δ_pct = 12/20 = 60%
    _populate_phase_data(
        dlg,
        ant1_snrs=[-5.0] * 20,
        ant2_snrs=[-5.0] * 8,
    )
    assert dlg._check_phase2_early_stop() is True


# ───── No-Stop-Cases ─────────────────────────────────────────────────


def test_phase2_no_stop_on_fair_metrics():
    """Faire Verhaeltnisse → kein Stop, regulaerer Pfad bis Schritt 8."""
    dlg = _make_dlg(scoring_mode="snr")
    # ANT1@20=-5dB Top5, ANT2@20=-6dB Top5 → Δ=1dB → kein Stop
    # Stationen: 14 vs 15 → Δ_pct = 1/15 = 6.7% → kein Stop
    _populate_phase_data(
        dlg,
        ant1_snrs=[-5, -6, -7, -8, -9, -10, -11, -12, -13, -14, -15, -16, -17, -18],   # 14 St.
        ant2_snrs=[-6, -7, -8, -9, -10, -11, -12, -13, -14, -15, -16, -17, -18, -19, -20],  # 15 St.
    )
    assert dlg._check_phase2_early_stop() is False


def test_phase2_no_stop_on_overload():
    """Overload-Marker in 1 Bucket → kein Stop trotz klarer Differenz."""
    dlg = _make_dlg(scoring_mode="snr")
    _populate_phase_data(
        dlg,
        ant1_snrs=[0, -1, -2, -3, -4, -5, -6, -7, -8, -9],   # 10 St.
        ant2_snrs=[-10, -11, -12, -13, -14, -15, -16, -17, -18, -19],  # 10 St.
    )
    # Overload-Marker (None) in einem Bucket einfuegen
    dlg._phase_data[("ANT1", 20)].append(None)
    assert dlg._check_phase2_early_stop() is False


def test_phase2_no_stop_on_low_station_count():
    """Alle Buckets <5 Stationen → kein Stop (Mess-Streuung-Schutz)."""
    dlg = _make_dlg(scoring_mode="snr")
    # Nur 3 Stationen pro Bucket — unter MIN_MEASURE_STATIONS=5
    dlg._phase_data[("ANT1", 10)] = [-15.0, -16.0, -17.0]
    dlg._phase_data[("ANT2", 10)] = [-15.0, -16.0, -17.0]
    dlg._phase_data[("ANT1", 20)] = [0.0, -1.0, -2.0]
    dlg._phase_data[("ANT2", 20)] = [-20.0, -21.0, -22.0]
    assert dlg._check_phase2_early_stop() is False


def test_phase2_stop_calls_finish():
    """Bei Stop: _finished=True und _results befuellt nach feed_cycle().

    Integration-Test: feed_cycle()-Pfad verifiziert dass _finish() aufgerufen wird.
    """
    dlg = _make_dlg(scoring_mode="snr")
    # 3 Buckets bereits befuellt, 4. Bucket bei feed_cycle drangepackt
    dlg._step = 3
    dlg._phase_data[("ANT1", 10)] = [-5.0] * 10
    dlg._phase_data[("ANT2", 10)] = [-5.0] * 10
    dlg._phase_data[("ANT1", 20)] = [0.0] * 10  # ANT1 deutlich besser
    # 4. Bucket = ANT2@20, wird im feed_cycle befuellt

    # Schedule: schedule[3] sollte (ANT2, 20) sein in Round 0
    expected_key = dlg._schedule[3]
    assert expected_key == ("ANT2", 20), f"Schedule[3]={expected_key}, expected (ANT2, 20)"

    # Mock messages mit ANT2@20 schwach
    class _Msg:
        def __init__(self, snr): self.snr = snr
    weak_messages = [_Msg(snr) for snr in [-15, -16, -17, -18, -19, -20, -21, -22, -23, -24]]

    dlg.feed_cycle(weak_messages)

    assert dlg._finished is True, "Adaptiv-Stop muss _finish() ausgeloest haben"
    assert "ant1_gain" in dlg._results
    assert "ant2_gain" in dlg._results
    assert "best_ant" in dlg._results
