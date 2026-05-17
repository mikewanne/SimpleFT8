"""P54-FIX (v0.97.45) — echte Closed-Loop-Convergenz beim TUNE.

Mike's Konzept: statt fälschlich `(band, 10W, rf=10)` hart zu speichern,
regelt die App während des TUNE den Slider hoch/runter bis FWDPWR ≈ 10W
rauskommt. DANN wird der echte Slider-Wert gespeichert.

Plus Krücken-Skalierung in _apply_rf_preset wenn nur 1 Stützpunkt für
ein Band vorhanden ist.

Tests T1-T18 decken Convergenz-Schleife, Cancel-Race, Plausibilität,
Krücke und Hardware-Sync ab.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest


# ──────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────


def _make_mw_tx_for_convergence(fwdpwr_sequence, cancelled=False,
                                  radio_ip="192.168.1.1"):
    """Mock-Self fuer _tune_converge_to_target.

    fwdpwr_sequence: Liste von FWDPWR-Mittelwerten je Iteration.
    Helper installiert MagicMock fuer set_rfpower_direct + iteriert
    `_fwdpwr_samples` aus der Sequenz.
    """
    obj = MagicMock()
    obj.radio.ip = radio_ip
    obj.radio.set_rfpower_direct = MagicMock()
    obj._fwdpwr_samples = []
    obj._tune_convergence_cancelled = cancelled

    # Simuliere _wait_with_event_loop: füllt _fwdpwr_samples pro Iteration.
    fwdpwr_iter = iter(fwdpwr_sequence)

    def fake_wait(ms):
        try:
            next_fwdpwr = next(fwdpwr_iter)
            obj._fwdpwr_samples = [next_fwdpwr, next_fwdpwr]  # 2 Samples
        except StopIteration:
            obj._fwdpwr_samples = []

    obj._wait_with_event_loop = fake_wait
    return obj


# ──────────────────────────────────────────────────────────────────────
# T1-T6 — _tune_converge_to_target
# ──────────────────────────────────────────────────────────────────────


def test_t1_lineares_radio_konvergiert_bei_rf10():
    """Bei linearem Radio (FWDPWR=10W bei rf=10) → Convergenz Iter 0."""
    from ui import mw_tx
    obj = _make_mw_tx_for_convergence([10.0])  # Initial-Sample = 10W
    result = mw_tx.TXMixin._tune_converge_to_target(obj, target_w=10)
    assert result == 10


def test_t2_off_band_konvergiert_hoch():
    """Off-Band: FWDPWR=7W bei rf=10 → App regelt hoch bis ~14."""
    from ui import mw_tx
    # Sequenz: Initial=7W, dann nach rf=14 → 10W
    obj = _make_mw_tx_for_convergence([7.0, 10.0])
    result = mw_tx.TXMixin._tune_converge_to_target(obj, target_w=10)
    # Erwartet: erste Iter rechnet rf hoch (step >= 1), dann konvergiert
    assert result is not None
    assert result > 10  # Hochgeregelt


def test_t3_fwdpwr_ueber_ziel_reduziert():
    """FWDPWR=15W > 10W Ziel → App reduziert rf."""
    from ui import mw_tx
    obj = _make_mw_tx_for_convergence([15.0, 10.0])
    result = mw_tx.TXMixin._tune_converge_to_target(obj, target_w=10)
    assert result is not None
    assert result < 10  # Runtergeregelt


def test_t4_max_iterations_returnt_best_effort():
    """Max-Iter erreicht → letzten rf-Wert zurueckgeben (best-effort)."""
    from ui import mw_tx
    # Sequenz oszilliert nie unter Toleranz: 7, 13, 7, 13, 7, 13
    obj = _make_mw_tx_for_convergence([7.0, 13.0, 7.0, 13.0, 7.0, 13.0])
    result = mw_tx.TXMixin._tune_converge_to_target(
        obj, target_w=10, max_iterations=5
    )
    # Sollte nach 5 Iterationen einen rf-Wert zurueckgeben (nicht None)
    assert result is not None
    assert 1 <= result <= 100


def test_t5_kein_fwdpwr_signal_returnt_none():
    """Wenn FWDPWR durchgehend 0 → returnt None."""
    from ui import mw_tx
    obj = _make_mw_tx_for_convergence([0.0])  # Kein Signal
    result = mw_tx.TXMixin._tune_converge_to_target(obj, target_w=10)
    assert result is None


def test_t6_cancel_flag_bricht_ab():
    """Cancel-Flag während Schleife → returnt None ohne weitere Iter."""
    from ui import mw_tx
    obj = _make_mw_tx_for_convergence([7.0, 10.0], cancelled=True)
    result = mw_tx.TXMixin._tune_converge_to_target(obj, target_w=10)
    assert result is None


# ──────────────────────────────────────────────────────────────────────
# T7 — Phase B SWR-Check (in _tune_stop)
# ──────────────────────────────────────────────────────────────────────


def test_t7_phase_b_skip_bei_swr_bad():
    """SWR > Limit nach Phase A → Phase B skippen, _tune_converged_rf=None.

    Source-Level: _tune_stop muss SWR-Check VOR _tune_converge_to_target
    machen.
    """
    src = open("ui/mw_tx.py").read()
    idx = src.find("def _tune_stop")
    end = src.find("\n    def ", idx + 5)
    block = src[idx:end if end > 0 else len(src)]
    assert "swr_after_match" in block, "SWR-Check fehlt in _tune_stop"
    assert "swr_limit" in block, "swr_limit-Check fehlt"
    # Phase B SKIP muss vorkommen
    assert "Phase B SKIP" in block or "_tune_converged_rf = None" in block


# ──────────────────────────────────────────────────────────────────────
# T8-T12 — _tune_post_swr_check
# ──────────────────────────────────────────────────────────────────────


def _make_mw_tx_for_post_check(swr=1.5, fwdpwr_samples=None,
                                 converged_rf=None, auto_running=False):
    """Mock-Self fuer _tune_post_swr_check-Tests."""
    obj = MagicMock()
    obj._tune_post_check_token = object()
    obj._tune_in_progress = True
    obj._auto_tune_running = auto_running
    obj._auto_tune_dialog = MagicMock() if auto_running else None
    obj.radio.ip = "192.168.1.1"
    obj.radio.last_swr = swr
    obj.radio.radio_type = "flexradio"
    obj.settings.get = MagicMock(side_effect=lambda k, d=None: {
        "swr_limit": 3.0,
    }.get(k, d))
    obj.settings.band = "40m"
    obj.settings.mode = "FT8"
    obj._fwdpwr_samples = list(fwdpwr_samples or [])
    obj._swr_blocked_bands = set()
    obj._rx_mode = "normal"
    obj._diversity_ctrl = MagicMock(scoring_mode="normal")
    obj._tune_converged_rf = converged_rf
    obj._rfpower_current = 50
    return obj


def test_t8_post_check_speichert_konvergierten_wert():
    """R1-F4: Save mit konvergiertem rf (z.B. 14), NICHT hart 10."""
    from ui import mw_tx
    obj = _make_mw_tx_for_post_check(
        swr=1.5, fwdpwr_samples=[9.5], converged_rf=14
    )
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj.rf_preset_store.save.assert_called_once_with(
        "flexradio", "40m", 10, 14  # 10W-Schluessel, rf=14 (konvergiert)
    )


def test_t9_post_check_fallback_rf10_bei_none():
    """R1-F9: Wenn _tune_converged_rf=None → Fallback rf=10 (Backward-Compat)."""
    from ui import mw_tx
    obj = _make_mw_tx_for_post_check(
        swr=1.5, fwdpwr_samples=[9.5], converged_rf=None
    )
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj.rf_preset_store.save.assert_called_once_with(
        "flexradio", "40m", 10, 10  # Fallback
    )


def test_t10_post_check_plausibility_rf_too_low():
    """R1-F5 ORANGE: rf < 3 → kein Save (Hardware-Anomalie)."""
    from ui import mw_tx
    obj = _make_mw_tx_for_post_check(
        swr=1.5, fwdpwr_samples=[9.5], converged_rf=2
    )
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj.rf_preset_store.save.assert_not_called()


def test_t11_post_check_plausibility_rf_too_high():
    """R1-F5 ORANGE: rf > 50 → kein Save (Hardware-Anomalie)."""
    from ui import mw_tx
    obj = _make_mw_tx_for_post_check(
        swr=1.5, fwdpwr_samples=[9.5], converged_rf=60
    )
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj.rf_preset_store.save.assert_not_called()


def test_t12_post_check_ruft_set_power_nach_apply():
    """R1-F1 ROT: nach _apply_rf_preset → radio.set_power explicit."""
    from ui import mw_tx
    obj = _make_mw_tx_for_post_check(
        swr=1.5, fwdpwr_samples=[9.5], converged_rf=14
    )
    obj._rfpower_current = 14
    obj._apply_rf_preset = MagicMock()
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj.radio.set_power.assert_called_with(14)


# ──────────────────────────────────────────────────────────────────────
# T13-T17 — _kruecken_skalierung + _apply_rf_preset
# ──────────────────────────────────────────────────────────────────────


def _make_mw_tx_for_krucke(presets_dict):
    """Mock fuer _kruecken_skalierung — get_all returnt presets_dict."""
    obj = MagicMock()
    obj.radio.radio_type = "flexradio"
    obj.rf_preset_store.get_all = MagicMock(
        return_value={"40m": presets_dict}
    )
    return obj


def test_t13_kruecke_mit_1_stuetzpunkt():
    """1 Stützpunkt (10W=rf 14) → für 50W: 14*5*0.9 = 63."""
    from ui import mw_tx
    obj = _make_mw_tx_for_krucke({10: {"rf": 14}})
    result = mw_tx.TXMixin._kruecken_skalierung(obj, "40m", 50)
    assert result == 63


def test_t14_kruecke_mit_0_stuetzpunkten():
    """Kein Stützpunkt → None."""
    from ui import mw_tx
    obj = _make_mw_tx_for_krucke({})
    result = mw_tx.TXMixin._kruecken_skalierung(obj, "40m", 50)
    assert result is None


def test_t15_kruecke_mit_2_stuetzpunkten():
    """2+ Stützpunkte → None (Hybrid-Strategie soll übernehmen)."""
    from ui import mw_tx
    obj = _make_mw_tx_for_krucke({10: {"rf": 14}, 50: {"rf": 65}})
    result = mw_tx.TXMixin._kruecken_skalierung(obj, "40m", 80)
    assert result is None


def test_t16_kruecke_mit_anchor_rf_0():
    """Anchor rf=0 → None (defensiv)."""
    from ui import mw_tx
    obj = _make_mw_tx_for_krucke({10: {"rf": 0}})
    result = mw_tx.TXMixin._kruecken_skalierung(obj, "40m", 50)
    assert result is None


def test_t17_apply_rf_preset_nutzt_kruecke():
    """_apply_rf_preset ruft _kruecken_skalierung wenn store.load None returnt."""
    from ui import mw_tx
    obj = MagicMock()
    obj.radio.radio_type = "flexradio"
    obj.radio.ip = "1.2.3.4"
    obj.settings.band = "40m"
    obj.settings.get = MagicMock(side_effect=lambda k, d=None: {
        "power_preset": 50,
    }.get(k, d))
    obj._power_target = 50
    obj.rf_preset_store.load.return_value = None  # Kein direkter Treffer
    obj._kruecken_skalierung = MagicMock(return_value=63)

    mw_tx.TXMixin._apply_rf_preset(obj)

    obj._kruecken_skalierung.assert_called_once_with("40m", 50)
    assert obj._rfpower_current == 63


def test_t17b_apply_rf_preset_default_wenn_kruecke_none():
    """Wenn Krücke auch None → Settings-Default 50."""
    from ui import mw_tx
    obj = MagicMock()
    obj.radio.radio_type = "flexradio"
    obj.radio.ip = "1.2.3.4"
    obj.settings.band = "40m"
    obj.settings.get = MagicMock(side_effect=lambda k, d=None: {
        "power_preset": 50,
    }.get(k, d))
    obj._power_target = 50
    obj.rf_preset_store.load.return_value = None
    obj._kruecken_skalierung = MagicMock(return_value=None)
    obj.settings.get_tx_power = MagicMock(return_value=50)

    mw_tx.TXMixin._apply_rf_preset(obj)

    assert obj._rfpower_current == 50


# ──────────────────────────────────────────────────────────────────────
# T18 — State-Var Init in MainWindow
# ──────────────────────────────────────────────────────────────────────


def test_t18_state_vars_initialized_in_main_window():
    """R1-F3: _tune_converged_rf und _tune_convergence_cancelled in
    MainWindow.__init__ initialisiert (Source-Level)."""
    src = open("ui/main_window.py").read()
    assert "self._tune_converged_rf: int | None = None" in src
    assert "self._tune_convergence_cancelled: bool = False" in src
    # Final-R1 ROT: Re-Entry-Sperre fuer _tune_stop
    assert "self._tune_stop_active: bool = False" in src


# ──────────────────────────────────────────────────────────────────────
# T19 — Final-R1 ROT: _tune_stop Re-Entry-Sperre
# ──────────────────────────────────────────────────────────────────────


def test_t19_tune_stop_re_entry_setzt_cancel_flag():
    """Final-R1 ROT: Wenn _tune_stop bereits aktiv → 2. Aufruf setzt
    _tune_convergence_cancelled=True statt doppelt tune_off zu rufen."""
    from ui import mw_tx
    obj = MagicMock()
    obj._tune_stop_active = True  # erster _tune_stop läuft schon
    obj._tune_convergence_cancelled = False
    obj._tune_active = True
    obj._tune_auto_stop_token = None

    mw_tx.TXMixin._tune_stop(obj, None)

    # Re-Entry-Sperre greift: kein tune_off, aber Cancel-Flag gesetzt
    obj.radio.tune_off.assert_not_called()
    assert obj._tune_convergence_cancelled is True
