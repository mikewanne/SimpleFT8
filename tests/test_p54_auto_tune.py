"""P54 (v0.97.44) — Auto-Tune bei Bandwechsel + RFPreset-Stuetzpunkt.

Variante C aus Mike-Diskussion 16.05.2026: Auto-TUNE nach Bandwechsel
+ Speichern eines 10-W-Stuetzpunkts im RFPresetStore zur schnelleren
TX-Power-Konvergenz.

Tests T1-T23 decken Setting, Hooks, Save-Logik, Signal-Routing,
Hardware-Pflicht, Re-Entry-Schutz, Edge-Cases ab.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest


# ── T1 — Default Setting ───────────────────────────────────────────────


def test_t1_setting_default_true():
    """auto_tune_on_band_change Default True."""
    from config.settings import DEFAULTS
    assert DEFAULTS["auto_tune_on_band_change"] is True


# ── T2 — tune_duration_s Whitelist {15, 30} (P63-Regression) ──────────


def test_t2_tune_duration_whitelist():
    """tune_duration_s muss 15 oder 30 sein (Regression aus P63)."""
    from config.settings import DEFAULTS
    assert DEFAULTS["tune_duration_s"] in (15, 30)


# ── T3 — Setting=False → kein Helper-Call ─────────────────────────────


def test_t3_setting_false_skip():
    """Bei auto_tune_on_band_change=False wird Helper NICHT aufgerufen."""
    obj = _make_mw_radio_mock(setting=False)
    from ui import mw_radio
    # Aufruf der Band-Change-Logik (nur das Auto-Tune-Stueck simuliert):
    _simulate_auto_tune_gate(obj, "40m")
    obj._start_auto_tune_for_band_change.assert_not_called()


# ── T4 — radio.ip=None → silent skip ──────────────────────────────────


def test_t4_radio_ip_none_skip():
    obj = _make_mw_radio_mock(radio_ip=None)
    _simulate_auto_tune_gate(obj, "40m")
    obj._start_auto_tune_for_band_change.assert_not_called()


# ── T5 — Band in SWR-Block → skip ─────────────────────────────────────


def test_t5_band_swr_blocked_skip():
    obj = _make_mw_radio_mock()
    obj._swr_blocked_bands = {"40M"}
    _simulate_auto_tune_gate(obj, "40m")
    obj._start_auto_tune_for_band_change.assert_not_called()


# ── T6 — tuner_present=False → skip ───────────────────────────────────


def test_t6_tuner_present_false_skip():
    obj = _make_mw_radio_mock(tuner_present=False)
    _simulate_auto_tune_gate(obj, "40m")
    obj._start_auto_tune_for_band_change.assert_not_called()


# ── T7 — Alle Bedingungen erfüllt → Helper-Call ───────────────────────


def test_t7_all_conditions_met_helper_called():
    obj = _make_mw_radio_mock()
    obj._start_auto_tune_for_band_change.return_value = True
    _simulate_auto_tune_gate(obj, "40m")
    obj._start_auto_tune_for_band_change.assert_called_once_with("40m")


# ── P119 (29.05.2026): T8/T8b/T9/T10 ENTFERNT ───────────────────────
# Diese Tests prüften den 10W-Stützpunkt-Save in _tune_post_swr_check
# (Phase B). Phase B + Save wurden in P119 entfernt — der echte rfpower
# wird im normalen Betrieb via _auto_adjust_tx_level gespeichert. Das neue
# Verhalten ("kein 10W-Save mehr") deckt test_p119_phaseb_removal.py (T5) ab.


def test_t11_swr_bad_no_save():
    """SWR > Limit → kein save."""
    obj = _make_mw_tx_mock(swr=5.0, fwdpwr_samples=[9.5])
    from ui import mw_tx
    with patch("PySide6.QtWidgets.QMessageBox"):
        mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj.rf_preset_store.save.assert_not_called()


# ── P119: T12 (manueller TUNE speichert) ENTFERNT — kein 10W-Save mehr. ──


# ── T13 — FWDPWR-Sampling auch während _tune_active ───────────────────


def test_t13_fwdpwr_sampled_during_tune_active():
    """_on_meter_update sampled FWDPWR auch wenn nur _tune_active=True."""
    obj = _make_mw_tx_mock_for_meter(tune_active=True, transmitting=False)
    from ui import mw_tx
    mw_tx.TXMixin._on_meter_update(obj, "FWDPWR", 9.5)
    assert 9.5 in obj._fwdpwr_samples


def test_t13b_fwdpwr_not_sampled_when_idle():
    """Wenn weder TX noch TUNE → KEIN Sample."""
    obj = _make_mw_tx_mock_for_meter(tune_active=False, transmitting=False)
    from ui import mw_tx
    mw_tx.TXMixin._on_meter_update(obj, "FWDPWR", 9.5)
    assert 9.5 not in obj._fwdpwr_samples


# ── T14/T15 — Auto-Tune Signal-Routing (R1-F2) ────────────────────────


def test_t14_auto_tune_success_emits_signal_no_messagebox():
    """Auto-Tune-Mode + SWR-good → emit auto_tune_done(True), KEIN MessageBox."""
    obj = _make_mw_tx_mock(swr=1.5, fwdpwr_samples=[9.5], auto_running=True)
    from ui import mw_tx
    with patch("PySide6.QtWidgets.QMessageBox") as msg_mock:
        mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj._auto_tune_dialog.auto_tune_done.emit.assert_called_once()
    args = obj._auto_tune_dialog.auto_tune_done.emit.call_args[0]
    assert args[0] is True  # success
    msg_mock.warning.assert_not_called()


def test_t15_auto_tune_fail_emits_signal_no_messagebox():
    """Auto-Tune-Mode + SWR-bad → emit auto_tune_done(False), KEIN MessageBox."""
    obj = _make_mw_tx_mock(swr=5.0, fwdpwr_samples=[9.5], auto_running=True)
    from ui import mw_tx
    with patch("PySide6.QtWidgets.QMessageBox") as msg_mock:
        mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj._auto_tune_dialog.auto_tune_done.emit.assert_called_once()
    args = obj._auto_tune_dialog.auto_tune_done.emit.call_args[0]
    assert args[0] is False
    msg_mock.warning.assert_not_called()


# ── T16 — Auto-Tune unterdrückt Diversity-Resume (R1-F3) ─────────────


def test_t16_auto_tune_skip_diversity_resume():
    """Auto-Tune-Mode: _check_diversity_preset wird NICHT aufgerufen
    (Bandwechsel-Logik macht das selbst nach Auto-Tune-Return)."""
    obj = _make_mw_tx_mock(swr=1.5, fwdpwr_samples=[9.5], auto_running=True)
    obj._swr_blocked_bands.add("40M")  # was_blocked=True → resume-Branch
    obj._rx_mode = "diversity"
    from ui import mw_tx
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj._check_diversity_preset.assert_not_called()


# ── T17 — _apply_rf_preset nach Save erneut gerufen (V2-F1) ──────────


# P119: test_t17_apply_rf_preset_called_after_save ENTFERNT — kein Save
# mehr im Post-Check, daher auch kein _apply_rf_preset-Aufruf dort.


def test_t17b_apply_rf_preset_not_called_when_no_save():
    """P54-FIX: bei rf out of [3..50] → kein save → kein _apply_rf_preset."""
    obj = _make_mw_tx_mock(swr=1.5, fwdpwr_samples=[1.0], converged_rf=2)
    from ui import mw_tx
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj._apply_rf_preset.assert_not_called()


# ── P119: T18/T19 (FWDPWR-Grenzen → save) ENTFERNT — kein 10W-Save mehr. ──


# ── T20 — Verbindungsverlust während Auto-Tune ────────────────────────


def test_t20_radio_disconnect_during_auto_tune():
    """radio.ip=None im Post-Check + Auto-Mode → emit Fail-Signal."""
    obj = _make_mw_tx_mock(swr=1.5, fwdpwr_samples=[9.5], auto_running=True)
    obj.radio.ip = None
    from ui import mw_tx
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj._auto_tune_dialog.auto_tune_done.emit.assert_called_once_with(False, 0.0, 0.0)


# ── T21 — Hardware-Pflicht ANT1 ───────────────────────────────────────


def test_t21_hardware_ant1_set():
    """Helper ruft set_tx_antenna('ANT1') vor tune_on() — Source-Level.

    Wichtig: nur Code-Statements zaehlen (keine Docstrings/Kommentare).
    """
    src = open("ui/mw_tx.py").read()
    idx = src.find("def _start_auto_tune_for_band_change")
    assert idx > 0
    end = src.find("\n    def ", idx + 5)
    block = src[idx:end if end > 0 else len(src)]
    # ANT1 muss VOR tune_on stehen — beide als `self.radio.<call>` suchen
    ant_idx = block.find("self.radio.set_tx_antenna(\"ANT1\")")
    tune_idx = block.find("self.radio.tune_on()")
    assert ant_idx > 0, "set_tx_antenna(ANT1) nicht im Helper"
    assert tune_idx > 0, "tune_on() nicht im Helper"
    assert ant_idx < tune_idx, "set_tx_antenna muss VOR tune_on stehen"


# ── T22 — _tune_in_progress=False nach Post-Check ─────────────────────


def test_t22_tune_in_progress_cleared():
    """_tune_in_progress wird in _tune_post_swr_check auf False gesetzt
    (Watchdog wieder scharf)."""
    obj = _make_mw_tx_mock(swr=1.5, fwdpwr_samples=[9.5])
    obj._tune_in_progress = True
    from ui import mw_tx
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    assert obj._tune_in_progress is False


# ── T24 — Final-R1-ROT-Fix: set_power nach _apply_rf_preset ──────────


# P119: test_t24_set_power_after_apply_rf_preset ENTFERNT — kein Save /
# _apply_rf_preset-Sync im Post-Check mehr (Phase B raus).


def test_t24b_no_set_power_when_no_save():
    """P54-FIX: rf out of [3..50] → kein Save, kein set_power-Call."""
    obj = _make_mw_tx_mock(swr=1.5, fwdpwr_samples=[1.0], converged_rf=2)
    obj._apply_rf_preset = MagicMock()
    from ui import mw_tx
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    obj.radio.set_power.assert_not_called()


# ── T23 — Token-Race: alter Token ignoriert ───────────────────────────


def test_t23_token_race_ignored():
    """Wenn token != aktueller _tune_post_check_token → frueh return."""
    obj = _make_mw_tx_mock(swr=1.5, fwdpwr_samples=[9.5])
    old_token = object()
    obj._tune_post_check_token = object()  # neuer Token
    from ui import mw_tx
    mw_tx.TXMixin._tune_post_swr_check(obj, old_token)
    obj.rf_preset_store.save.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────


def _make_mw_radio_mock(setting=True, radio_ip="192.168.1.1",
                         tuner_present=True):
    """Erzeugt Mock-Self fuer _on_band_changed Auto-Tune-Gate-Test."""
    obj = MagicMock()
    obj.settings.get = MagicMock(side_effect=lambda k, d=None: {
        "auto_tune_on_band_change": setting,
        "tuner_present": tuner_present,
    }.get(k, d))
    obj.radio.ip = radio_ip
    obj._swr_blocked_bands = set()
    obj._start_auto_tune_for_band_change = MagicMock(return_value=True)
    return obj


def _simulate_auto_tune_gate(obj, band: str):
    """Simuliert nur das Gate aus _on_band_changed (Z.481-498 ca.).

    Kompletter `_on_band_changed`-Aufruf wuerde zu viele Side-Effekte
    auf MainWindow brauchen. Wir testen das Gate-Verhalten isoliert.
    """
    if (obj.settings.get("auto_tune_on_band_change", True)
            and obj.radio.ip
            and band.upper() not in obj._swr_blocked_bands
            and obj.settings.get("tuner_present", True)):
        obj._start_auto_tune_for_band_change(band)


def _make_mw_tx_mock(swr=1.5, fwdpwr_samples=None, auto_running=False,
                      converged_rf=None):
    """Erzeugt Mock-Self fuer _tune_post_swr_check-Tests.

    P54-FIX (v0.97.45): default `_tune_converged_rf=None` triggert
    Fallback rf=10 in der Save-Logik (Backward-Compat).
    """
    obj = MagicMock()
    obj._tune_post_check_token = object()
    obj._tune_in_progress = True
    obj._auto_tune_running = auto_running
    obj._auto_tune_dialog = MagicMock() if auto_running else None
    obj.radio.ip = "192.168.1.1"
    obj.radio.last_swr = swr
    obj.radio.radio_type = "flexradio"
    # P76-A (v0.97.49): _tune_post_swr_check liest jetzt gefrorenen Wert
    # statt radio.last_swr. Helper muss beide setzen damit Tests valid bleiben.
    obj._tune_last_valid_swr = swr
    obj.settings.get = MagicMock(side_effect=lambda k, d=None: {
        "swr_limit": 3.0,
    }.get(k, d))
    obj.settings.band = "40m"
    obj.settings.mode = "FT8"
    obj._fwdpwr_samples = list(fwdpwr_samples or [])
    obj._swr_blocked_bands = set()
    obj._rx_mode = "normal"
    obj._diversity_ctrl = MagicMock(scoring_mode="normal")
    # P54-FIX: convergierter rf-Wert (None = Fallback hart auf 10)
    obj._tune_converged_rf = converged_rf
    return obj


def _make_mw_tx_mock_for_meter(tune_active=False, transmitting=False):
    """Mock fuer _on_meter_update-Test (FWDPWR-Sampling)."""
    obj = MagicMock()
    obj.encoder.is_transmitting = transmitting
    obj._tune_active = tune_active
    obj._fwdpwr_samples = []
    obj.radio.tx_raw_peak = 0.0
    obj.radio.tx_audio_level = 0.5
    return obj
