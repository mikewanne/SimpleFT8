"""P92 (20.05.2026, v0.97.62) — Diversity-Sub-Toggle auch bei Bandpilot=AN.

Mike-Spec: 2. Klick auf DIVERSITY toggled Std↔DX in ALLEN
Bandpilot-Modi (off/auto/manual). Manueller Override gilt bis zum
nächsten Bandwechsel — Bandpilot ist Empfehlung, kein Zwang.

Vor P92 war der Toggle bei bp=auto/manual gesperrt (mw_radio.py:895-897).
Mike musste den Umweg DX → NORMAL → DIVERSITY → Wahl-Dialog → STANDARD
nehmen.

Test-Coverage (V3 §6):
- T1, T2  : Sub-Toggle bei bp=auto/manual (P92 Kern-Verhalten)
- T3, T4  : Pipeline-Lock / radio.ip=None blockt weiterhin (alle bp-Modi)
- T5      : OMNI + Auto-Hunt werden gestoppt (R1-K1+K2 aus Bundle G)
- T6      : Code-Inspection-Wächter für AC2 (kein Override-Persistenz-State)
- T7      : Integration — Bandpilot übernimmt nach Bandwechsel wieder
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
    """Minimaler Mock analog tests/test_bundle_g.py (gleiches Pattern)."""
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


# ── T1: bp=auto Toggle Std → DX ────────────────────────────────────


def test_toggle_standard_to_dx_when_bandpilot_auto(app):
    """T1: bp=auto + Std → activate('dx')."""
    obj = _make_radio_mixin(bp_mode="auto", current_scoring="normal")
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_called_once_with("dx")


# ── T2: bp=manual Toggle DX → Std ──────────────────────────────────


def test_toggle_dx_to_standard_when_bandpilot_manual(app):
    """T2: bp=manual + DX → activate('normal')."""
    obj = _make_radio_mixin(bp_mode="manual", current_scoring="dx")
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_called_once_with("normal")


# ── T3: Pipeline-Lock blockt in allen bp-Modi ──────────────────────


@pytest.mark.parametrize("bp_mode", ["off", "auto", "manual"])
def test_pipeline_lock_blocks_toggle_in_all_bp_modes(app, bp_mode):
    """T3: _gain_measure_locked=True → kein Toggle (alle bp-Modi)."""
    obj = _make_radio_mixin(bp_mode=bp_mode, gain_locked=True)
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_not_called()


# ── T4: radio.ip=None blockt in allen bp-Modi ──────────────────────


@pytest.mark.parametrize("bp_mode", ["off", "auto", "manual"])
def test_no_radio_ip_blocks_toggle_in_all_bp_modes(app, bp_mode):
    """T4: radio.ip=None → kein Toggle (alle bp-Modi)."""
    obj = _make_radio_mixin(bp_mode=bp_mode, radio_ip=None)
    obj._on_diversity_subtoggle_requested()
    obj._activate_diversity_with_scoring.assert_not_called()


# ── T5: OMNI + Auto-Hunt gestoppt beim Toggle in bp-Modi ───────────


@pytest.mark.parametrize("bp_mode", ["auto", "manual"])
def test_omni_and_auto_hunt_stopped_on_toggle_in_bp_modes(app, bp_mode):
    """T5 (R1-K1+K2 + P92): OMNI + Auto-Hunt stoppen bei bp != off."""
    obj = _make_radio_mixin(bp_mode=bp_mode, current_scoring="normal",
                            omni_active=True, hunt_active=True)
    obj._on_diversity_subtoggle_requested()
    obj._omni_cq.stop.assert_called_once_with("scoring_toggle")
    obj._auto_hunt.stop_auto_hunt.assert_called_once_with("scoring_toggle")
    # Und Toggle wurde gemacht
    obj._activate_diversity_with_scoring.assert_called_once_with("dx")


# ── T6: AC2-Wächter — kein Override-Persistenz-State ───────────────


def test_maybe_apply_bandpilot_does_not_read_override_flag():
    """T6: Code-Inspection für AC2.

    _maybe_apply_bandpilot bzw. _on_band_changed dürfen KEINEN
    User-Override-State lesen — sonst kippt AC2 (Bandpilot übernimmt
    automatisch wieder beim Bandwechsel ohne Persistenz-Mechanismus).
    """
    src = Path(__file__).resolve().parent.parent / "ui" / "mw_radio.py"
    text = src.read_text()
    forbidden = ["_override", "last_user_choice", "sticky_scoring",
                 "_user_override", "manual_override"]
    found = [w for w in forbidden if w in text]
    assert found == [], (
        f"P92 AC2-Wächter: gefundene Override-Persistenz-Tokens {found}. "
        "Bandpilot soll stateless bzgl. User-Override bleiben.")


# ── T7: Integration — Bandpilot übernimmt nach Bandwechsel ─────────


def test_bandpilot_takes_over_on_bandchange_after_manual_override(app):
    """T7 (R1-F5): Manueller Sub-Toggle → Bandwechsel → Bandpilot übernimmt.

    Szenario 1: Bandpilot liefert Empfehlung → übernimmt.
    Szenario 2: rec=None → manuell gewählter Modus bleibt aktiv.

    Test verifiziert AC2 als Integration und ergänzt T6
    (statische Inspection).
    """
    from ui.mw_radio import RadioMixin

    # Szenario 1: rec=switch → _set_rx_mode_direct wird aufgerufen
    obj = MagicMock(spec=RadioMixin)
    obj._maybe_apply_bandpilot = (
        RadioMixin._maybe_apply_bandpilot.__get__(obj))
    obj.settings = MagicMock()
    obj.settings.get = MagicMock(
        side_effect=lambda key, default=None:
            "auto" if key == "bandpilot_mode" else default
    )
    obj._current_rx_mode_string = MagicMock(return_value="diversity_dx")
    obj._bandpilot = MagicMock()
    obj._bandpilot.recommend = MagicMock(return_value={
        "decision": "switch",
        "decision_mode": "diversity_normal",
    })
    obj._apply_bandpilot_auto = MagicMock(return_value=True)

    result = obj._maybe_apply_bandpilot("40m")
    assert result is True, (
        "P92 AC2: Bandpilot soll bei rec=switch übernehmen, hat nicht.")
    obj._apply_bandpilot_auto.assert_called_once()

    # Szenario 2: rec=None → manueller Modus bleibt
    obj2 = MagicMock(spec=RadioMixin)
    obj2._maybe_apply_bandpilot = (
        RadioMixin._maybe_apply_bandpilot.__get__(obj2))
    obj2.settings = MagicMock()
    obj2.settings.get = MagicMock(
        side_effect=lambda key, default=None:
            "auto" if key == "bandpilot_mode" else default
    )
    obj2._current_rx_mode_string = MagicMock(return_value="diversity_dx")
    obj2._bandpilot = MagicMock()
    obj2._bandpilot.recommend = MagicMock(return_value=None)
    obj2._show_bandpilot_insufficient_data = MagicMock()
    obj2._apply_bandpilot_auto = MagicMock()

    result2 = obj2._maybe_apply_bandpilot("40m")
    assert result2 is False, (
        "P92 AC2: bei rec=None soll Bandpilot NICHT übernehmen, hat aber.")
    obj2._apply_bandpilot_auto.assert_not_called()


# ── T8: Tooltip-Korrektur (AC7 / R1-F2) ────────────────────────────


def test_tooltip_no_bandpilot_off_hint(app):
    """T8 (AC7 / R1-F2): Tooltip enthält keinen 'nur bei Bandpilot=Aus'-Hinweis.

    Vor P92 stand im Tooltip 'wechselt zwischen Standard und DX
    (nur bei Bandpilot=Aus).' — nach P92 muss dieser Hinweis weg sein.
    """
    src = Path(__file__).resolve().parent.parent / "ui" / "control_panel.py"
    text = src.read_text()
    assert "nur bei Bandpilot=Aus" not in text, (
        "P92 Tooltip-Korrektur fehlt: 'nur bei Bandpilot=Aus' steht "
        "noch im Code.")
