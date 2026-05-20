"""P73-A (20.05.2026, v0.97.64) — Settings-UX TUNE-Einstellungen
konsolidiert in eigener GroupBox unter Tab „TX & Schutz".

Mike-Wunsch 18.05.2026: TUNE-bezogene Settings unter einem Tab
zusammenfassen. Heute auf 2 Tabs verteilt (Tune-Leistung in
„TX & Schutz", Tuner-CB + TUNE-Dauer + Auto-TUNE in „FT8 & Diversity")
→ User muss zwischen Tabs springen.

Fix: QGroupBox „TUNE-Einstellungen" innerhalb Tab „TX & Schutz" mit
QFormLayout, enthält in Reihenfolge:
 1. Antennen-Tuner verwenden (Master-Switch)
 2. TUNE-Dauer (5/10/15 s)
 3. Tune-Leistung (5/10/20 W Buttons)
 4. Auto-TUNE bei Bandwechsel

Plus R1-F1: Master-Switch — Tuner-Checkbox de/aktiviert die
3 abhängigen TUNE-Widgets.

Test-Coverage:
- T1 GroupBox „TUNE-Einstellungen" existiert
- T2 Tuner-CB, TUNE-Dauer-Combo, Auto-TUNE-CB in GroupBox
- T3 Tune-Power-Buttons 5/10/20 W in GroupBox
- T4 SWR-Limit NICHT in GroupBox (bleibt in TX-Schutz-Hauptform)
- T5 Settings-Keys Save/Load unverändert
- T6 Reset-Defaults setzt TUNE-Widgets korrekt
- T7 Master-Switch (R1-F1): Tuner-CB uncheck → abhängige disabled
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication, QComboBox, QCheckBox, QGroupBox, QPushButton, QWidget
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _new_dialog(app, tmp_path):
    """Erzeugt einen echten SettingsDialog mit echtem Settings-Objekt
    (isolierte Datei via tmp_path)."""
    import config.settings as _settings_mod
    from ui.settings_dialog import SettingsDialog
    # Settings mit isolierter Datei
    s = _settings_mod.Settings()
    s._path = tmp_path / "settings.json"
    return SettingsDialog(s, parent=None), s


def _find_tune_groupbox(dialog) -> QGroupBox:
    for gb in dialog.findChildren(QGroupBox):
        if gb.title() == "TUNE-Einstellungen":
            return gb
    return None


# ── T1: GroupBox existiert ─────────────────────────────────────────


def test_tune_groupbox_exists_with_correct_title(app, tmp_path):
    """T1: GroupBox mit Titel „TUNE-Einstellungen" im Tab „TX & Schutz"."""
    dialog, _ = _new_dialog(app, tmp_path)
    gb = _find_tune_groupbox(dialog)
    assert gb is not None, (
        "GroupBox 'TUNE-Einstellungen' nicht gefunden — P73-A AC1 broken")


# ── T2: TUNE-Widgets in GroupBox ───────────────────────────────────


def test_tune_widgets_in_tune_groupbox_via_findchild(app, tmp_path):
    """T2 (R1-F2): tuner_present_cb, tune_duration_combo,
    auto_tune_band_cb sind Kinder der GroupBox (rekursiv).
    """
    dialog, _ = _new_dialog(app, tmp_path)
    gb = _find_tune_groupbox(dialog)
    cbs = gb.findChildren(QCheckBox)
    combos = gb.findChildren(QComboBox)
    assert dialog.tuner_present_cb in cbs, (
        "tuner_present_cb nicht in TUNE-GroupBox")
    assert dialog.tune_duration_combo in combos, (
        "tune_duration_combo nicht in TUNE-GroupBox")
    assert dialog.auto_tune_band_cb in cbs, (
        "auto_tune_band_cb nicht in TUNE-GroupBox")


# ── T3: Tune-Power-Buttons in GroupBox ─────────────────────────────


def test_tune_power_buttons_in_tune_groupbox(app, tmp_path):
    """T3: _tune_btns 5W/10W/20W sind Kinder der GroupBox."""
    dialog, _ = _new_dialog(app, tmp_path)
    gb = _find_tune_groupbox(dialog)
    btns = gb.findChildren(QPushButton)
    for watt in (5, 10, 20):
        assert dialog._tune_btns[watt] in btns, (
            f"Tune-Button {watt}W nicht in TUNE-GroupBox")


# ── T4: SWR-Limit NICHT in GroupBox (R1-F7) ───────────────────────


def test_swr_limit_not_in_tune_groupbox(app, tmp_path):
    """T4 (R1-F7): SWR-Limit-ComboBox bleibt in TX-Schutz-Hauptform,
    nicht in TUNE-GroupBox.
    """
    dialog, _ = _new_dialog(app, tmp_path)
    gb = _find_tune_groupbox(dialog)
    combos_in_gb = gb.findChildren(QComboBox)
    assert dialog.swr_limit not in combos_in_gb, (
        "SWR-Limit darf NICHT in TUNE-GroupBox sein (P73-A AC4)")


# ── T5: Settings-Save/Load unverändert ─────────────────────────────


def test_settings_save_load_unchanged_for_tune_keys(app, tmp_path):
    """T5: Save/Load-Cycle für TUNE-Settings-Keys (AC5)."""
    dialog, settings = _new_dialog(app, tmp_path)
    # Setze Werte
    dialog.tuner_present_cb.setChecked(False)
    _idx10 = dialog.tune_duration_combo.findData(10)
    dialog.tune_duration_combo.setCurrentIndex(_idx10)
    dialog.auto_tune_band_cb.setChecked(False)
    dialog._current_tune_power = 5
    # Save (via _save_and_close — accept gemockt damit Dialog nicht schließt)
    dialog.accept = lambda: None
    dialog._save_and_close()
    # Verifikation: alle Keys gesetzt
    assert settings.get("tuner_present") is False
    assert settings.get("tune_duration_s") == 10
    assert settings.get("auto_tune_on_band_change") is False
    assert settings.get("tune_power") == 5


# ── T6: Reset-Defaults ─────────────────────────────────────────────


def test_reset_defaults_resets_tune_widgets(app, tmp_path, monkeypatch):
    """T6: _reset_defaults setzt TUNE-Widgets auf Default.

    Reset zeigt eine QMessageBox-Bestätigung. monkeypatch ersetzt
    exec durch No-Op + clickedButton liefert den AcceptRole-Button
    damit der Reset-Pfad durchläuft.
    """
    from PySide6.QtWidgets import QMessageBox
    dialog, _ = _new_dialog(app, tmp_path)
    # Werte ändern
    dialog.tuner_present_cb.setChecked(False)
    dialog._current_tune_power = 5

    captured = {}
    _orig_add_button = QMessageBox.addButton

    def _patched_add_button(self, text, role):
        btn = _orig_add_button(self, text, role)
        if role == QMessageBox.ButtonRole.AcceptRole:
            captured["yes"] = btn
        return btn

    monkeypatch.setattr(QMessageBox, "exec", lambda self: None)
    monkeypatch.setattr(QMessageBox, "addButton", _patched_add_button)
    monkeypatch.setattr(
        QMessageBox, "clickedButton",
        lambda self: captured.get("yes"))

    # Reset
    dialog._reset_defaults()
    assert dialog.tuner_present_cb.isChecked() is True, (
        "tuner_present Default nach Reset = True")
    assert dialog.tune_duration_combo.currentData() == 15
    assert dialog._current_tune_power == 10


# ── T7: Master-Switch (R1-F1) ──────────────────────────────────────


def test_tuner_master_switch_disables_dependent_widgets(app, tmp_path):
    """T7 (R1-F1): Tuner-CB uncheck → abhängige TUNE-Widgets disabled."""
    dialog, _ = _new_dialog(app, tmp_path)
    # Initial: Tuner checked → alle enabled
    dialog.tuner_present_cb.setChecked(True)
    assert dialog.tune_duration_combo.isEnabled() is True
    assert dialog.auto_tune_band_cb.isEnabled() is True
    for btn in dialog._tune_btns.values():
        assert btn.isEnabled() is True

    # Uncheck → alle disabled
    dialog.tuner_present_cb.setChecked(False)
    assert dialog.tune_duration_combo.isEnabled() is False, (
        "tune_duration_combo sollte disabled sein bei Tuner=off")
    assert dialog.auto_tune_band_cb.isEnabled() is False, (
        "auto_tune_band_cb sollte disabled sein bei Tuner=off")
    for watt, btn in dialog._tune_btns.items():
        assert btn.isEnabled() is False, (
            f"Tune-Btn {watt}W sollte disabled sein bei Tuner=off")

    # Recheck → wieder enabled
    dialog.tuner_present_cb.setChecked(True)
    assert dialog.tune_duration_combo.isEnabled() is True
    assert dialog.auto_tune_band_cb.isEnabled() is True
    for btn in dialog._tune_btns.values():
        assert btn.isEnabled() is True
