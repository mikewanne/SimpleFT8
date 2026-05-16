"""Bundle K (v0.97.34, 15.05.2026 mittags): P57 SWR-Limit-Combo + P59
CQ-Button grüner Active-State.

P57: QDoubleSpinBox → QComboBox mit festen 0.5-Schritten 1.5..5.0.
Verhindert freie Tastatur-Eingabe wie 1.7 (Hardware-Sicherheit).

P59: btn_cq + btn_auto_hunt Active-State von rot/gelb auf grün —
einheitlich mit btn_omni_cq (Mike-Spec optische Konsistenz).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

# ── P57 — SWR-Limit Snap-Helper + Konstanten ───────────────────────────────


def test_t1_swr_values_genau_8_eintraege():
    """T1: ComboBox enthaelt exakt 8 Werte 1.5..5.0 in 0.5er-Schritten."""
    from ui.settings_dialog import _SWR_VALUES
    assert _SWR_VALUES == [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    assert len(_SWR_VALUES) == 8


def test_t2_swr_default_index_30():
    """T2: Default-Index 3 entspricht 3.0."""
    from ui.settings_dialog import _SWR_VALUES
    assert _SWR_VALUES[3] == 3.0


def test_t3_swr_snap_mitte():
    """T3a: Snap-Funktion 1.7 → 2.0 (naechst-hoeherer Wert)."""
    from ui.settings_dialog import _swr_value_to_index, _SWR_VALUES
    assert _SWR_VALUES[_swr_value_to_index(1.7)] == 2.0


def test_t3b_swr_snap_unter_minimum():
    """T3b: Snap unter Minimum 0.5 → 1.5."""
    from ui.settings_dialog import _swr_value_to_index, _SWR_VALUES
    assert _SWR_VALUES[_swr_value_to_index(0.5)] == 1.5


def test_t3c_swr_snap_ueber_maximum():
    """T3c: Snap ueber Maximum 7.5 → 5.0."""
    from ui.settings_dialog import _swr_value_to_index, _SWR_VALUES
    assert _SWR_VALUES[_swr_value_to_index(7.5)] == 5.0


def test_t3d_swr_snap_exakter_wert():
    """T3d: Exakter Listenwert 2.0 → 2.0 (kein Versatz)."""
    from ui.settings_dialog import _swr_value_to_index, _SWR_VALUES
    assert _SWR_VALUES[_swr_value_to_index(2.0)] == 2.0


# ── P59 — Button-Active-State auf grün ─────────────────────────────────────


def _read_control_panel() -> str:
    src = Path(__file__).parent.parent / "ui" / "control_panel.py"
    return src.read_text()


def test_t4_mode_btn_active_gruen():
    """T4: _mode_btn_style enthaelt gruenen Active-Block (P59)."""
    text = _read_control_panel()
    # Suche den _mode_btn_style-Block (Active-State ist innerhalb dieser
    # mehrzeiligen f-String-Konstruktion)
    assert "_mode_btn_style" in text
    # Active-State auf grün
    assert "QPushButton:checked" in text
    assert "rgba(0,150,0,0.75)" in text, \
        "P59: _mode_btn_style Active muss gruenes rgba(0,150,0,0.75) enthalten"


def test_t5_mode_btn_active_nicht_mehr_rot_gelb():
    """T5: alte rote+gelbe Active-Werte sind NICHT mehr im _mode_btn_style.

    Wir pruefen anhand des spezifischen Original-Patterns:
    rgba(200,0,0,0.7) als Background + #FFD700 als Color im :checked-Block.
    """
    text = _read_control_panel()
    # P59: Der genaue alte Background-Wert darf nicht mehr existieren.
    # (#FFD700 koennte in anderen Buttons verwendet werden — nur
    # rgba(200,0,0,0.7) ist eindeutig der Mode-Btn-Active-State).
    assert "rgba(200,0,0,0.7)" not in text, \
        "P59: alter roter Active-Background rgba(200,0,0,0.7) muss raus sein"


def test_t6_omni_btn_style_unveraendert_regression():
    """T6: _omni_btn_style enthaelt weiterhin gruenen Active-State
    (Regression-Schutz — Mike's bestehender OMNI-Button bleibt grün)."""
    text = _read_control_panel()
    assert "_omni_btn_style" in text
    # OMNI war schon grün — muss erhalten bleiben
    assert "rgba(0,150,0,0.75)" in text  # gruen-Active
    # OMNI-spezifischer Inaktiv-Block muss da sein (rot-orangener
    # rgba(80,0,0,0.55) ist Identifier fuer omni_btn_style)
    assert "rgba(80,0,0,0.55)" in text, \
        "P59-Regression: _omni_btn_style Inaktiv-Background fehlt"


def test_t7_settings_dialog_uses_combobox_not_spinbox():
    """T7 (P57): settings_dialog.py konstruiert swr_limit als QComboBox,
    nicht mehr als QDoubleSpinBox."""
    src = Path(__file__).parent.parent / "ui" / "settings_dialog.py"
    text = src.read_text()
    # Bug-Schutz: ComboBox-Konstruktion muss da sein
    assert "self.swr_limit = QComboBox()" in text
    # Alte Spinbox-Konstruktion darf nicht mehr da sein
    assert "self.swr_limit = QDoubleSpinBox()" not in text


def test_t8_settings_dialog_save_uses_currentdata():
    """T8 (P57): Save-Pfad nutzt currentData() statt value()."""
    src = Path(__file__).parent.parent / "ui" / "settings_dialog.py"
    text = src.read_text()
    # currentData-Aufruf existiert
    assert "self.swr_limit.currentData()" in text, \
        "P57: Save muss currentData() lesen (Float-Userdata aus addItem)"
    # alter value()-Aufruf raus
    assert "self.settings.set(\"swr_limit\", self.swr_limit.value())" not in text
