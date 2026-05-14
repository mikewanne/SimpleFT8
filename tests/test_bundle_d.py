"""Bundle D — UI-Tweaks (v0.97.21).

5 UI-Tweaks nach P50 Field-Test:
A) Settings „Sichtbare Bänder" Padding luftiger
B) DT-Anzeige +0.0/-0.0 → 0.0 (Mike-Feedback: „ist 0.0 :-)")
C) Even/Odd-Anzeige oben → Filter-Buttons (Normal-only)
D) Diversity: Buttons ausgeblendet, QSO/Logbuch füllen Breite
E) Statusbar: 15s-Slot-Progress-Bar mit Cyan/Orange-Wechsel
   (Bundle F: Magenta → Orange umgestellt)

11 Tests T1-T11.
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    """Qt Application Instance — module-scoped."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def tmp_settings_file(monkeypatch, tmp_path):
    """Pro Test eigene config.json."""
    cfg_dir = tmp_path / ".simpleft8"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr("config.settings.CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("config.settings.CONFIG_FILE", cfg_file)
    return cfg_file


# ── T1: Settings-Block luftiges Spacing (Bundle I: 10 → 16) ────────────

def test_t1_settings_bands_grid_spacing(qapp, tmp_settings_file):
    """T1: Bänder-Grid-Layout hat luftiges Spacing.
    Bundle D (v0.97.21) hob 6→10, Bundle I (v0.97.26) auf 16 weiter."""
    from config.settings import Settings
    from ui.settings_dialog import SettingsDialog
    s = Settings()
    d = SettingsDialog(s)
    cb = d._band_checkboxes["20m"]
    grid = cb.parentWidget().layout()
    assert grid.spacing() >= 16, f"Expected ≥16, got {grid.spacing()}"


# ── T2-T5: DT-Format ───────────────────────────────────────────────────

def test_t2_dt_format_zero():
    """T2: _format_dt(0.0) → '0.0' (kein Vorzeichen)."""
    from ui.rx_panel import _format_dt
    assert _format_dt(0.0) == "0.0"
    assert _format_dt(-0.0) == "0.0"


def test_t3_dt_format_near_zero():
    """T3: kleine Werte (±0.04) → '0.0' (rundet auf 0)."""
    from ui.rx_panel import _format_dt
    assert _format_dt(0.04) == "0.0"
    assert _format_dt(-0.04) == "0.0"


def test_t4_dt_format_positive():
    """T4: positive Werte ≥ 0.05 → mit Vorzeichen '+0.X'."""
    from ui.rx_panel import _format_dt
    assert _format_dt(0.05) == "+0.1"
    assert _format_dt(0.2) == "+0.2"
    assert _format_dt(2.5) == "+2.5"


def test_t5_dt_format_negative_and_large():
    """T5: negative Werte mit '-' Prefix; ≥10s ganzzahlig."""
    from ui.rx_panel import _format_dt
    assert _format_dt(-0.5) == "-0.5"
    assert _format_dt(-1.2) == "-1.2"
    assert _format_dt(12.5) == "12"
    assert _format_dt(-15.0) == "-15"


# ── T6-T7: Bundle-E Rollback — RX-Filter existiert nicht mehr ──────────

def test_t6_rxpanel_slot_filter_removed(qapp):
    """T6 (Bundle E Rollback): apply_slot_filter wurde entfernt."""
    from ui.rx_panel import RXPanel
    p = RXPanel()
    assert not hasattr(p, "apply_slot_filter"), \
        "apply_slot_filter sollte mit Bundle E entfernt sein"
    assert not hasattr(p, "_slot_filter"), \
        "_slot_filter State sollte mit Bundle E entfernt sein"


def test_t7_qsopanel_slot_filter_signal_removed(qapp):
    """T7 (Bundle E Rollback): slot_filter_changed Signal wurde umbenannt."""
    from ui.qso_panel import QSOPanel
    p = QSOPanel()
    # Bundle E: Signal wurde umbenannt zu tx_slot_lock_changed
    assert not hasattr(p, "slot_filter_changed"), \
        "slot_filter_changed sollte zu tx_slot_lock_changed umbenannt sein"
    assert hasattr(p, "tx_slot_lock_changed"), \
        "tx_slot_lock_changed muss existieren"


# ── T8: QSOPanel Button-Logik (Bundle E Signal-Rename) ─────────────────

def test_t8_qso_panel_slot_buttons_emit_lock_signal(qapp):
    """T8: Klick auf btn_even emittet tx_slot_lock_changed('even'),
    erneuter Klick (uncheck) emittet 'none' (Bundle E)."""
    from ui.qso_panel import QSOPanel
    p = QSOPanel()
    emitted = []
    p.tx_slot_lock_changed.connect(lambda s: emitted.append(s))
    # Klick btn_even
    p._btn_even.setChecked(True)
    p._on_slot_btn_clicked("even")
    assert emitted[-1] == "even"
    # Klick btn_odd → exclusive, btn_even unchecked
    p._btn_odd.setChecked(True)
    p._on_slot_btn_clicked("odd")
    assert emitted[-1] == "odd"
    assert not p._btn_even.isChecked()
    # Klick btn_odd erneut → uncheck → none
    p._btn_odd.setChecked(False)
    p._on_slot_btn_clicked("odd")
    assert emitted[-1] == "none"


# ── T9: QSOPanel set_slot_buttons_visible ──────────────────────────────

def test_t9_qso_panel_buttons_visibility(qapp):
    """T9: set_slot_buttons_visible(False) versteckt den Container."""
    from ui.qso_panel import QSOPanel
    p = QSOPanel()
    assert not p._slot_container.isHidden()
    p.set_slot_buttons_visible(False)
    assert p._slot_container.isHidden()
    p.set_slot_buttons_visible(True)
    assert not p._slot_container.isHidden()


# ── T10: QSOPanel reset_slot_filter ────────────────────────────────────

def test_t10_qso_panel_set_tx_slot_lock_buttons(qapp):
    """T10 (Bundle E): set_tx_slot_lock_buttons setzt Buttons aus Settings-Wert
    ohne Signal-Emit (blockSignals)."""
    from ui.qso_panel import QSOPanel
    p = QSOPanel()
    emitted = []
    p.tx_slot_lock_changed.connect(lambda s: emitted.append(s))
    # Initial: keiner
    p.set_tx_slot_lock_buttons("even")
    assert p._btn_even.isChecked()
    assert not p._btn_odd.isChecked()
    assert len(emitted) == 0, "Signal sollte BEI set_tx_slot_lock_buttons NICHT emit'n"
    p.set_tx_slot_lock_buttons("odd")
    assert not p._btn_even.isChecked()
    assert p._btn_odd.isChecked()
    p.set_tx_slot_lock_buttons("none")
    assert not p._btn_even.isChecked()
    assert not p._btn_odd.isChecked()
    # Defensiver Filter
    p.set_tx_slot_lock_buttons("garbage")
    assert not p._btn_even.isChecked()
    assert not p._btn_odd.isChecked()


# ── T11: MainWindow Slot-Progress-Bar Style ────────────────────────────

def test_t11_slot_progress_bar_color_switch(qapp):
    """T11: _update_slot_progress_bar wechselt Style zwischen Cyan und
    Orange je Slot-Parity (Bundle F: war Magenta)."""
    # Wir simulieren _update_slot_progress_bar isoliert ohne MainWindow,
    # weil MainWindow zu schwer aufzubauen ist.
    from PySide6.QtWidgets import QProgressBar
    from unittest.mock import MagicMock
    import time

    # Mock self mit QProgressBar + Timer
    self_mock = MagicMock()
    self_mock._slot_progress_bar = QProgressBar()
    self_mock._slot_progress_bar.setRange(0, 1000)
    self_mock._slot_progress_is_even = True
    self_mock.timer = MagicMock()
    self_mock.timer.cycle_duration = 15.0

    # Echte Methode aufrufen — bound an Mock-self
    from ui.main_window import MainWindow
    bound_method = MainWindow._update_slot_progress_bar.__get__(self_mock)

    # Forcieren: Parity-Wechsel durch is_even ändern
    self_mock._slot_progress_is_even = False
    # Mock time.time() → setze t so dass is_even=True (cycle_num gerade)
    # cycle_num = int(t / 15); is_even = cycle_num % 2 == 0
    # Wir nehmen t = 0 → cycle_num=0 (even=True)
    import time as _t
    real_time = _t.time
    _t.time = lambda: 0.5  # 0.5s im Slot 0 (even)
    try:
        bound_method()
        assert self_mock._slot_progress_is_even is True
        style = self_mock._slot_progress_bar.styleSheet()
        assert "#00CCFF" in style, f"Expected cyan (#00CCFF) in style: {style}"
        # Jetzt umschalten auf odd
        _t.time = lambda: 15.5  # 0.5s im Slot 1 (odd)
        bound_method()
        assert self_mock._slot_progress_is_even is False
        style = self_mock._slot_progress_bar.styleSheet()
        assert "#FFAA00" in style, f"Expected orange (#FFAA00) in style: {style}"
    finally:
        _t.time = real_time
