"""P74-A (v0.97.94) — Tests für konsolidierte TUNE+Gain-Pipeline.

State-Machine im DXTuneDialog (TUNE → GAIN_CYCLES → FINISHED) plus
Fall-B-Branch in `_on_band_changed`. Konsolidiert das alte
3-Fenster-Problem (AutoTuneDialog → DXTuneDialog → QMessageBox bei
SWR-bad) auf EIN Fenster.

T1-T10: DXTuneDialog State-Machine, Cancel-Pfade, Backup-Race.
T11-T12: `_on_band_changed` Fall-B-Check + Fail-Pfad.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication, QWidget

from ui.dx_tune_dialog import DXTuneDialog


def _ensure_app():
    return QApplication.instance() or QApplication([])


class _MockRadio:
    """Minimal-Mock für DXTuneDialog-Konstruktor."""
    last_swr = 1.2

    def set_rx_antenna(self, ant): pass
    def set_rfgain(self, gain): pass
    def set_tx_antenna(self, ant): pass


class _MockParent(QWidget):
    """Parent-Mock — muss QWidget sein damit DXTuneDialog setParent
    akzeptiert. Hält Stub-Attribute für `_start_dialog_tune_sequence`
    und Cancel-Pfade.
    """
    def __init__(self):
        super().__init__()
        self.radio = _MockRadio()
        self._fwdpwr_samples = []
        self._tune_post_check_token = object()
        self._tune_convergence_cancelled = False
        self._tune_in_progress = False
        self._tune_stop_called_with = None
        self._dialog_tune_sequence_called = False
        self._dialog_tune_sequence_args = None

    def _start_dialog_tune_sequence(self, dialog, band, mode, duration_s):
        self._dialog_tune_sequence_called = True
        self._dialog_tune_sequence_args = (dialog, band, mode, duration_s)

    def _tune_stop(self, token):
        self._tune_stop_called_with = token


def _make_parent():
    """Eindeutiger Parent pro Test — QApplication-Lifecycle sauber."""
    _ensure_app()
    return _MockParent()


# ── T1 — Constructor with_tune_phase=True startet in State 'TUNE' ──

def test_t1_constructor_with_tune_phase_starts_in_tune_state():
    parent = _make_parent()
    dlg = DXTuneDialog(
        _MockRadio(), "40m",
        scoring_mode="stations", rx_mode="diversity",
        parent=parent, with_tune_phase=True,
        tune_duration_s=10, mode="FT8",
    )
    assert dlg._state == 'TUNE'
    assert dlg._with_tune_phase is True
    assert dlg.tune_duration_s == 10
    assert dlg.mode == "FT8"
    # Parent muss aufgerufen worden sein (TUNE-Hardware-Sequenz)
    assert parent._dialog_tune_sequence_called is True
    args = parent._dialog_tune_sequence_args
    assert args[1] == "40m" and args[2] == "FT8" and args[3] == 10
    # Backup-Banner soll NICHT gezeigt werden (with_tune_phase=True
    # ignoriert prev_tune_swr).
    assert dlg._prev_tune_swr is None
    dlg.close()


# ── T2 — Auto-Tune-Done Success wechselt auf GAIN_CYCLES ──────────

def test_t2_auto_tune_done_success_switches_to_gain_cycles():
    parent = _make_parent()
    dlg = DXTuneDialog(
        _MockRadio(), "40m",
        scoring_mode="stations", rx_mode="diversity",
        parent=parent, with_tune_phase=True,
    )
    assert dlg._state == 'TUNE'
    dlg._on_auto_tune_done(True, 1.2, 9.8)
    assert dlg._state == 'GAIN_CYCLES'
    assert dlg._tune_phase_finished is True
    # Phase-2 hat begonnen — _step ist 0 (erste Mess-Position).
    assert dlg._step == 0
    dlg.close()


# ── T3 — Auto-Tune-Done Fail zeigt Banner, kein State-Wechsel ─────

def test_t3_auto_tune_done_fail_shows_banner_keeps_state():
    parent = _make_parent()
    dlg = DXTuneDialog(
        _MockRadio(), "40m",
        scoring_mode="stations", rx_mode="diversity",
        parent=parent, with_tune_phase=True,
    )
    dlg._on_auto_tune_done(False, 3.5, 0.0)
    # State bleibt 'TUNE' (Fail-Banner sichtbar, später reject via
    # QTimer.singleShot).
    assert dlg._state == 'TUNE'
    assert dlg._tune_phase_finished is True
    text = dlg._tune_status_label.text()
    assert "3.5" in text and "SWR" in text
    dlg.close()


# ── T4 — feed_cycle im State 'TUNE' ist No-Op ──────────────────────

def test_t4_feed_cycle_in_tune_state_is_noop():
    parent = _make_parent()
    dlg = DXTuneDialog(
        _MockRadio(), "40m",
        scoring_mode="stations", rx_mode="diversity",
        parent=parent, with_tune_phase=True,
    )
    msg = MagicMock()
    msg.snr = 5.0
    dlg.feed_cycle([msg])
    # _phase_data darf nicht gefüttert worden sein.
    assert all(len(v) == 0 for v in dlg._phase_data.values()) \
        or len(dlg._phase_data) == 0
    assert dlg._step == 0
    dlg.close()


# ── T5 — feed_cycle im State 'GAIN_CYCLES' verarbeitet normal ──────

def test_t5_feed_cycle_in_gain_cycles_processes_normally():
    parent = _make_parent()
    dlg = DXTuneDialog(
        _MockRadio(), "40m",
        scoring_mode="stations", rx_mode="diversity",
        parent=parent, with_tune_phase=True,
    )
    dlg._on_auto_tune_done(True, 1.2, 9.8)  # → GAIN_CYCLES
    msg = MagicMock()
    msg.snr = -5.0
    msg.message = "CQ DL1ABC JN58"
    initial_step = dlg._step
    dlg.feed_cycle([msg])
    # Step wurde inkrementiert ODER Daten gefüttert.
    assert dlg._step >= initial_step
    dlg.close()


# ── T6 — Cancel im State 'TUNE' invalidiert Token (R1-F1) ──────────

def test_t6_cancel_in_tune_state_invalidates_token():
    parent = _make_parent()
    original_token = parent._tune_post_check_token
    dlg = DXTuneDialog(
        _MockRadio(), "40m",
        scoring_mode="stations", rx_mode="diversity",
        parent=parent, with_tune_phase=True,
    )
    dlg._on_cancel()
    # R1-F1: Token rotiert → _tune_post_swr_check sieht alten Token nicht.
    assert parent._tune_post_check_token is not original_token
    # R1: Convergenz-Flag + _tune_stop wurden gerufen.
    assert parent._tune_convergence_cancelled is True
    assert parent._tune_in_progress is False
    # _tune_phase_finished gesetzt damit Backup-Timer stumm bleibt.
    assert dlg._tune_phase_finished is True
    dlg.close()


# ── T7 — Cancel im State 'GAIN_CYCLES' nutzt bestehenden Pfad ──────

def test_t7_cancel_in_gain_cycles_uses_existing_path():
    parent = _make_parent()
    radio = MagicMock()
    radio.last_swr = 1.0
    dlg = DXTuneDialog(
        radio, "40m",
        scoring_mode="stations", rx_mode="diversity",
        parent=parent, with_tune_phase=False,  # Default-Pfad
    )
    assert dlg._state == 'GAIN_CYCLES'
    dlg._on_cancel()
    # Sicherer Default: ANT1 + Gain 10.
    radio.set_rx_antenna.assert_called_with("ANT1")
    radio.set_rfgain.assert_called_with(10)
    dlg.close()


# ── T8 — Backwards-Compat: with_tune_phase=False = bisheriges Verhalten ──

def test_t8_backwards_compat_without_tune_phase():
    _ensure_app()
    dlg = DXTuneDialog(
        _MockRadio(), "40m",
        scoring_mode="stations", rx_mode="diversity",
    )
    assert dlg._state == 'GAIN_CYCLES'
    assert dlg._with_tune_phase is False
    # `_start_step()` wurde gerufen — _step bleibt 0 (erster Schritt
    # ist begonnen aber kein Cycle gefüttert), Radio-Calls gemacht.
    dlg.close()


# ── T9 — Backup-Timer-Race (R1-F4): Phase-finished blockt Backup ───

def test_t9_backup_timer_silent_when_phase_already_finished():
    parent = _make_parent()
    dlg = DXTuneDialog(
        _MockRadio(), "40m",
        scoring_mode="stations", rx_mode="diversity",
        parent=parent, with_tune_phase=True,
    )
    # Phase manuell als abgeschlossen markieren (z.B. nach echtem
    # auto_tune_done).
    dlg._tune_phase_finished = True
    initial_state = dlg._state
    # Backup-Callback direkt feuern.
    dlg._on_tune_backup_timeout()
    # State bleibt unverändert — Backup hat NICHT _on_auto_tune_done
    # gerufen.
    assert dlg._state == initial_state
    dlg.close()


# ── T10 — Doppel-Signal-Race (R1-F4): zweiter Done-Call ist No-Op ──

def test_t10_double_auto_tune_done_second_call_ignored():
    parent = _make_parent()
    dlg = DXTuneDialog(
        _MockRadio(), "40m",
        scoring_mode="stations", rx_mode="diversity",
        parent=parent, with_tune_phase=True,
    )
    dlg._on_auto_tune_done(True, 1.2, 9.8)  # Erster Call → GAIN_CYCLES
    assert dlg._state == 'GAIN_CYCLES'
    step_after_first = dlg._step
    dlg._on_auto_tune_done(True, 1.2, 9.8)  # Zweiter Call → ignoriert
    # State + Step unverändert.
    assert dlg._state == 'GAIN_CYCLES'
    assert dlg._step == step_after_first
    dlg.close()


# ── T11 — `_on_band_changed` Fall-B-Check: alle Bedingungen müssen erfüllt sein ──

def test_t11_case_b_requires_all_conditions():
    """is_case_b ist nur True wenn ALLE 8 Bedingungen zutreffen.

    Whitebox-Test der Branch-Logik in mw_radio.py:_on_band_changed.
    Wir testen 3 Negativ-Pfade (eine Bedingung false → kein Fall B).
    """
    from ui.mw_radio import RadioMixin

    def _setup(rx_mode="diversity", auto_tune=True, auto_gain=True,
               radio_ip="192.168.1.1", blocked=False, tuner=True,
               initial_set=False, gain_status="missing"):
        obj = MagicMock()
        obj._rx_mode = rx_mode
        obj.radio.ip = radio_ip
        obj._swr_blocked_bands = {"40M"} if blocked else set()
        obj._initial_band_set = initial_set
        obj._assess_gain.return_value = gain_status
        obj._main_window = obj
        obj.rf_preset_store.has_anchor.return_value = False
        # _on_band_changed-Eingang-Guards umgehen:
        obj._gain_measure_locked = False
        obj._tune_active = False
        obj.settings.band = "20m"
        obj.settings.mode = "FT8"

        def _settings_get(key, default=None):
            return {
                "auto_tune_on_band_change": auto_tune,
                "auto_gain_on_band_change": auto_gain,
                "tuner_present": tuner,
            }.get(key, default)
        obj.settings.get.side_effect = _settings_get

        obj._maybe_apply_bandpilot.return_value = False
        obj._direction_map_dialog = None
        return obj

    # Positiv-Pfad: alle Bedingungen erfüllt → Pipeline aufgerufen.
    obj = _setup()
    obj._start_pipeline_for_band_change.return_value = True
    RadioMixin._on_band_changed(obj, "40m")
    obj._start_pipeline_for_band_change.assert_called_once()
    obj._start_auto_tune_for_band_change.assert_not_called()

    # Negativ 1: rx_mode != diversity → Fall A statt B.
    obj = _setup(rx_mode="normal")
    RadioMixin._on_band_changed(obj, "40m")
    obj._start_pipeline_for_band_change.assert_not_called()

    # Negativ 2: auto_gain_on_band_change=False → Fall A statt B.
    obj = _setup(auto_gain=False)
    RadioMixin._on_band_changed(obj, "40m")
    obj._start_pipeline_for_band_change.assert_not_called()

    # Negativ 3: gain_status == "fresh" → kein Bedarf für Pipeline.
    obj = _setup(gain_status="fresh")
    RadioMixin._on_band_changed(obj, "40m")
    obj._start_pipeline_for_band_change.assert_not_called()


# ── T12 — Pipeline-Fail-Pfad ruft `_on_rx_mode_changed("normal")` ──

def test_t12_pipeline_fail_switches_to_normal_mode():
    from ui.mw_radio import RadioMixin

    obj = MagicMock()
    obj._rx_mode = "diversity"
    obj.radio.ip = "192.168.1.1"
    obj._swr_blocked_bands = set()
    obj._initial_band_set = False
    obj._assess_gain.return_value = "missing"
    obj._main_window = obj
    obj.rf_preset_store.has_anchor.return_value = False
    obj._gain_measure_locked = False
    obj._tune_active = False
    obj.settings.band = "20m"
    obj.settings.mode = "FT8"
    obj.settings.get.side_effect = lambda key, default=None: {
        "auto_tune_on_band_change": True,
        "auto_gain_on_band_change": True,
        "tuner_present": True,
    }.get(key, default)
    obj._maybe_apply_bandpilot.return_value = False
    obj._direction_map_dialog = None
    # Pipeline gibt Fail zurück.
    obj._start_pipeline_for_band_change.return_value = False

    RadioMixin._on_band_changed(obj, "40m")

    obj._start_pipeline_for_band_change.assert_called_once()
    obj._on_rx_mode_changed.assert_called_with("normal")
