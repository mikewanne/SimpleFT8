"""Bundle G (14.05.2026, v0.97.23 → v0.97.24) — Diversity Sub-Mode-Toggle.

Mike-Spec: bei Bandpilot=Aus soll 2. Klick auf DIVERSITY direkt zwischen
Standard und DX wechseln (kein Dialog). Bei Bandpilot=Auto/Manual:
no-op (Bandpilot entscheidet).

Logik-Matrix:
| Aktueller Modus | Klick | Aktion |
|---|---|---|
| Div Standard | DIVERSITY | → Div DX (Toggle) |
| Div DX | DIVERSITY | → Div Standard (Toggle) |
| Normal | DIVERSITY | Dialog Std/DX (unverändert) |
| Bandpilot=Auto+Div | DIVERSITY | no-op |
| Bandpilot=Manual+Div | DIVERSITY | no-op |
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_radio_mixin(*, bp_mode: str = "off",
                      current_scoring: str = "normal",
                      gain_locked: bool = False,
                      radio_ip: str = "192.168.1.68",
                      omni_active: bool = False,
                      hunt_active: bool = False):
    """Test-Setup: minimaler Mock-Objekt mit RadioMixin-Pfaden."""
    from ui.mw_radio import RadioMixin
    obj = MagicMock(spec=RadioMixin)
    obj._on_diversity_subtoggle_requested = (
        RadioMixin._on_diversity_subtoggle_requested.__get__(obj))
    obj.settings = MagicMock()
    obj.settings.get = MagicMock(
        side_effect=lambda key, default=None:
            bp_mode if key == "bandpilot_mode" else default
    )
    obj._gain_measure_locked = gain_locked
    obj.radio = MagicMock()
    obj.radio.ip = radio_ip
    obj._diversity_ctrl = MagicMock()
    obj._diversity_ctrl.scoring_mode = current_scoring
    obj._omni_cq = MagicMock()
    obj._omni_cq.is_active = MagicMock(return_value=omni_active)
    obj._omni_cq.stop = MagicMock()
    obj._auto_hunt = MagicMock()
    obj._auto_hunt.active = hunt_active
    obj._auto_hunt.stop_auto_hunt = MagicMock()
    obj._activate_diversity_with_scoring = MagicMock()
    return obj


# ── T1: Toggle Std → DX bei bp=off ─────────────────────────────────


def test_toggle_standard_to_dx_when_bandpilot_off(app):
    """T1: Klick Div während Std + bp=off → activate('dx')."""
    obj = _make_radio_mixin(bp_mode="off", current_scoring="normal")
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_called_once_with("dx")


# ── T2: Toggle DX → Std ────────────────────────────────────────────


def test_toggle_dx_to_standard_when_bandpilot_off(app):
    """T2: Klick Div während DX + bp=off → activate('normal')."""
    obj = _make_radio_mixin(bp_mode="off", current_scoring="dx")
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_called_once_with("normal")


# ── T3: bp=auto → no-op ────────────────────────────────────────────


def test_no_toggle_when_bandpilot_auto(app):
    """T3: Bandpilot=auto → kein Toggle (Bandpilot entscheidet)."""
    obj = _make_radio_mixin(bp_mode="auto", current_scoring="normal")
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_not_called()


# ── T4: bp=manual → no-op ──────────────────────────────────────────


def test_no_toggle_when_bandpilot_manual(app):
    """T4: Bandpilot=manual → kein Toggle."""
    obj = _make_radio_mixin(bp_mode="manual", current_scoring="dx")
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_not_called()


# ── T5: Gain-Lock → no-op ──────────────────────────────────────────


def test_no_toggle_when_gain_measure_locked(app):
    """T5: Pipeline läuft → Toggle ignoriert."""
    obj = _make_radio_mixin(bp_mode="off", gain_locked=True)
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_not_called()


# ── T6: keine Radio-IP → no-op ─────────────────────────────────────


def test_no_toggle_without_radio_ip(app):
    """T6: Radio nicht verbunden → Toggle ignoriert."""
    obj = _make_radio_mixin(bp_mode="off", radio_ip=None)
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_not_called()


# ── T7: Signal-Emit aus control_panel ──────────────────────────────


def test_control_panel_emits_subtoggle_signal_on_repeat_div_click(app):
    """T7: 2. Klick DIVERSITY emit'd diversity_subtoggle_requested."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._current_rx_mode = "diversity"
    emitted = []
    cp.diversity_subtoggle_requested.connect(lambda: emitted.append(True))
    cp._on_rx_mode_clicked("diversity")
    assert len(emitted) == 1, (
        "2. Klick auf DIVERSITY soll diversity_subtoggle_requested "
        "emit'en, hat aber nicht (Bundle G AC1 broken).")


def test_control_panel_no_emit_for_normal_click_when_already_normal(app):
    """T7b: 2. Klick NORMAL emit'd KEIN Signal (nur Diversity-Toggle)."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp._current_rx_mode = "normal"
    emitted = []
    cp.diversity_subtoggle_requested.connect(lambda: emitted.append(True))
    cp._on_rx_mode_clicked("normal")
    assert len(emitted) == 0, (
        "2. Klick auf NORMAL darf KEIN diversity_subtoggle_requested "
        "emit'en (nur Diversity-Toggle).")


# ── T8: Integration mit ECHTEM DiversityController ─────────────────


def test_real_diversity_controller_scoring_mode_toggle():
    """T8: Echter DiversityController.scoring_mode wechselt korrekt.

    Memory-Lesson `feedback_test_critical_path_not_mock.md`:
    mindestens 1 Test mit echtem Objekt, kein MagicMock-Cocoon.
    """
    from core.diversity import DiversityController
    d = DiversityController(scoring_mode="normal")
    assert d.scoring_mode == "normal"
    d.scoring_mode = "dx"
    assert d.scoring_mode == "dx"
    d.scoring_mode = "normal"
    assert d.scoring_mode == "normal"


# ── T9: OMNI gestoppt beim Toggle ──────────────────────────────────


def test_omni_stopped_on_toggle(app):
    """T9 (R1-K1+K2): OMNI-CQ aktiv + Toggle → omni.stop gerufen."""
    obj = _make_radio_mixin(bp_mode="off", omni_active=True)
    obj._on_diversity_subtoggle_requested()
    obj._omni_cq.stop.assert_called_once_with("scoring_toggle")


# ── T10: Auto-Hunt gestoppt beim Toggle ────────────────────────────


def test_auto_hunt_stopped_on_toggle(app):
    """T10 (R1-K1+K2): Auto-Hunt aktiv + Toggle → hunt.stop gerufen."""
    obj = _make_radio_mixin(bp_mode="off", hunt_active=True)
    obj._on_diversity_subtoggle_requested()
    obj._auto_hunt.stop_auto_hunt.assert_called_once_with("scoring_toggle")
