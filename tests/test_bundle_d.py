"""Bundle D — UI-Tweaks (v0.97.21).

5 UI-Tweaks nach P50 Field-Test:
A) Settings „Sichtbare Bänder" Padding luftiger
B) DT-Anzeige +0.0/-0.0 → 0.0 (Mike-Feedback: „ist 0.0 :-)")
C) Even/Odd-Anzeige oben → Filter-Buttons (Normal-only)
D) Diversity: Buttons ausgeblendet, QSO/Logbuch füllen Breite
E) Statusbar: 15s-Slot-Progress-Bar mit Cyan/Magenta-Wechsel

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


# ── T1: Settings-Block setSpacing(10) ──────────────────────────────────

def test_t1_settings_bands_grid_spacing(qapp, tmp_settings_file):
    """T1: Bänder-Grid-Layout hat setSpacing(10) statt 6."""
    from config.settings import Settings
    from ui.settings_dialog import SettingsDialog
    s = Settings()
    d = SettingsDialog(s)
    # Wir finden das QGridLayout über die Checkbox-Parent
    cb = d._band_checkboxes["20m"]
    grid = cb.parentWidget().layout()
    assert grid.spacing() == 10, f"Expected 10, got {grid.spacing()}"


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


# ── T6-T7: RXPanel.apply_slot_filter ───────────────────────────────────

def test_t6_rxpanel_slot_filter_state(qapp):
    """T6: apply_slot_filter setzt _slot_filter State korrekt."""
    from ui.rx_panel import RXPanel
    p = RXPanel()
    assert p._slot_filter == "both"
    p.apply_slot_filter("even")
    assert p._slot_filter == "even"
    p.apply_slot_filter("odd")
    assert p._slot_filter == "odd"
    p.apply_slot_filter("both")
    assert p._slot_filter == "both"


def test_t7_rxpanel_slot_filter_defensive(qapp):
    """T7: ungültige Filter-Werte → Fallback 'both'."""
    from ui.rx_panel import RXPanel
    p = RXPanel()
    p.apply_slot_filter("garbage")
    assert p._slot_filter == "both"
    p.apply_slot_filter(None)
    assert p._slot_filter == "both"
    p.apply_slot_filter(42)
    assert p._slot_filter == "both"


# ── T8: QSOPanel Button-Logik ──────────────────────────────────────────

def test_t8_qso_panel_slot_buttons_emit_signal(qapp):
    """T8: Klick auf btn_even emittet slot_filter_changed('even'),
    erneuter Klick (uncheck) emittet 'both'."""
    from ui.qso_panel import QSOPanel
    p = QSOPanel()
    emitted = []
    p.slot_filter_changed.connect(lambda s: emitted.append(s))
    # Klick btn_even (simulieren via setChecked + _on_slot_btn_clicked)
    p._btn_even.setChecked(True)
    p._on_slot_btn_clicked("even")
    assert emitted[-1] == "even"
    # Klick btn_odd → exclusive, btn_even unchecked
    p._btn_odd.setChecked(True)
    p._on_slot_btn_clicked("odd")
    assert emitted[-1] == "odd"
    assert not p._btn_even.isChecked()
    # Klick btn_odd erneut → uncheck → both
    p._btn_odd.setChecked(False)
    p._on_slot_btn_clicked("odd")
    assert emitted[-1] == "both"


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

def test_t10_qso_panel_reset_slot_filter(qapp):
    """T10: reset_slot_filter uncheckt beide Buttons + emittet 'both'."""
    from ui.qso_panel import QSOPanel
    p = QSOPanel()
    emitted = []
    p.slot_filter_changed.connect(lambda s: emitted.append(s))
    # Setup: btn_even aktiv
    p._btn_even.setChecked(True)
    p._on_slot_btn_clicked("even")
    assert p._btn_even.isChecked()
    # Reset
    p.reset_slot_filter()
    assert not p._btn_even.isChecked()
    assert not p._btn_odd.isChecked()
    assert emitted[-1] == "both"


# ── T11: MainWindow Slot-Progress-Bar Style ────────────────────────────

def test_t11_slot_progress_bar_color_switch(qapp):
    """T11: _update_slot_progress_bar wechselt Style zwischen Cyan und
    Magenta je Slot-Parity."""
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
        assert "#FF66CC" in style, f"Expected magenta (#FF66CC) in style: {style}"
    finally:
        _t.time = real_time
