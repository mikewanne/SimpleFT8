"""P86 — KALIBRIEREN-Button nur in Diversity sichtbar (v0.97.56)

Mike-Spec 19.05.2026: KALIBRIEREN ist Diversity-only Feature. Normal-Mode
liest ANT1-Gain aus Unified Store (P80) — keine eigene Mess-Routine.
Vermeidet UX-Verwirrung (Mike-Beobachtung „normal kalibrieren ist kacke
weil ich nur einen wert für ant1 bekomme").

DeepSeek-Brainstorm-R1 (V4-pro) bestätigte Variante A 🟢 + Hinweis
„→ DIVERSITY" im dx_info bei Re-Mess fällig im Normal.

Tests T1-T6:
- T1: rx_mode=normal → btn_einmessen.isHidden() == True
- T2: rx_mode=diversity → btn_einmessen.isHidden() == False
- T3: _format_gain_status stale + rx_mode=normal → HTML enthält "→ DIVERSITY"
- T4: _format_gain_status stale + rx_mode=diversity → KEIN "→ DIVERSITY"
- T5: _show_normal_preset_age_info Dialog-Text enthält "DIVERSITY"
- T6: _handle_dx_tuning im Normal-Mode → Defensive return, KEIN
       _start_dx_tuning Aufruf, KEIN _pending_dx_diversity gesetzt
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── T1 — Normal-Mode: btn_einmessen hidden ────────────────────────────


def test_t1_update_button_visibility_normal_hides_kalibrieren():
    """rx_mode=normal → btn_einmessen.setHidden(True)."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._rx_mode = "normal"
    obj.control_panel = MagicMock()

    mw_mod.MainWindow._update_button_visibility(obj)

    obj.control_panel.btn_einmessen.setHidden.assert_called_with(True)


# ── T2 — Diversity-Mode: btn_einmessen sichtbar ───────────────────────


def test_t2_update_button_visibility_diversity_shows_kalibrieren():
    """rx_mode=diversity → btn_einmessen.setHidden(False)."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._rx_mode = "diversity"
    obj.control_panel = MagicMock()

    mw_mod.MainWindow._update_button_visibility(obj)

    obj.control_panel.btn_einmessen.setHidden.assert_called_with(False)


# ── T3 — _format_gain_status: stale + normal → "→ DIVERSITY" Hinweis ──


def test_t3_format_gain_status_stale_normal_zeigt_diversity_hinweis():
    """Stale (>6h) + rx_mode=normal → HTML enthält '→ DIVERSITY'."""
    from ui import mw_radio

    obj = MagicMock()
    obj._gain_store = MagicMock()
    # >6h alt (Schwelle 6h überschritten)
    stale_ts = time.time() - (7 * 3600)
    obj._gain_store.get.return_value = {
        "ant1_gain": 10,
        "ant2_gain": 20,
        "ant2_calibrated": True,
        "gain_timestamp": stale_ts,
    }

    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "normal")

    assert "Re-Mess fällig" in html
    assert "→ DIVERSITY" in html, f"Expected '→ DIVERSITY' im Normal-Mode-Stale, got: {html}"


# ── T4 — _format_gain_status: stale + diversity → KEIN Pfeil-Hinweis ──


def test_t4_format_gain_status_stale_diversity_kein_pfeil():
    """Stale + rx_mode=diversity → HTML enthält NICHT '→ DIVERSITY'.

    KALIBRIEREN-Button ist in Diversity sichtbar — User sieht ihn direkt.
    """
    from ui import mw_radio

    obj = MagicMock()
    obj._gain_store = MagicMock()
    stale_ts = time.time() - (7 * 3600)
    obj._gain_store.get.return_value = {
        "ant1_gain": 10,
        "ant2_gain": 20,
        "ant2_calibrated": True,
        "gain_timestamp": stale_ts,
    }

    html = mw_radio.RadioMixin._format_gain_status(obj, "20m", "diversity")

    assert "Re-Mess fällig" in html
    assert "→ DIVERSITY" not in html, \
        f"Diversity-Mode darf NICHT '→ DIVERSITY' enthalten, got: {html}"


# ── T5 — _show_normal_preset_age_info Dialog-Text ─────────────────────


def test_t5_show_normal_preset_age_info_text_erwaehnt_diversity():
    """30-Tage-Dialog: Hinweis-Text muss DIVERSITY erwähnen."""
    import inspect
    from ui import mw_radio

    src = inspect.getsource(mw_radio.RadioMixin._show_normal_preset_age_info)

    assert "DIVERSITY" in src, \
        "P86: Dialog-Text muss auf DIVERSITY hinweisen (Button-Pfad)"
    # KALIBRIEREN-Button-Hinweis sollte ersetzt sein durch Wechsel-Hinweis
    assert "Wechsle" in src or "wechsle" in src, \
        "P86: Dialog soll Wechsel-Anweisung enthalten"


# ── T6 — _handle_dx_tuning: Defensive Return im Normal-Mode ───────────


def test_t6_handle_dx_tuning_normal_mode_defensive_return():
    """rx_mode=normal → frühes Return, KEIN _start_dx_tuning,
    KEIN _pending_dx_diversity gesetzt.
    """
    from ui.mw_radio import RadioMixin

    obj = MagicMock()
    obj._rx_mode = "normal"
    obj._pending_dx_diversity = False
    obj._diversity_ctrl = MagicMock()
    obj._diversity_ctrl.scoring_mode = "normal"
    obj._start_dx_tuning = MagicMock()

    RadioMixin._handle_dx_tuning(obj)

    obj._start_dx_tuning.assert_not_called()
    # _pending_dx_diversity darf NICHT gesetzt werden
    assert obj._pending_dx_diversity is False


# ── T6b — Diversity-Mode läuft Standard-Pipeline ──────────────────────


def test_t6b_handle_dx_tuning_diversity_standard():
    """rx_mode=diversity + scoring=normal → Phase 2 + Phase 3 mit
    scoring_mode='stations'.
    """
    from ui.mw_radio import RadioMixin

    obj = MagicMock()
    obj._rx_mode = "diversity"
    obj._pending_dx_diversity = False
    obj._diversity_ctrl = MagicMock()
    obj._diversity_ctrl.scoring_mode = "normal"
    obj._start_dx_tuning = MagicMock()

    RadioMixin._handle_dx_tuning(obj)

    obj._start_dx_tuning.assert_called_once_with(scoring_mode="stations")
    assert obj._pending_dx_diversity is True
    assert obj._pending_diversity_scoring == "normal"


# ── T6c — Diversity-DX läuft Phase 2 mit scoring=snr ──────────────────


def test_t6c_handle_dx_tuning_diversity_dx():
    """rx_mode=diversity + scoring=dx → scoring_mode='snr'."""
    from ui.mw_radio import RadioMixin

    obj = MagicMock()
    obj._rx_mode = "diversity"
    obj._pending_dx_diversity = False
    obj._diversity_ctrl = MagicMock()
    obj._diversity_ctrl.scoring_mode = "dx"
    obj._start_dx_tuning = MagicMock()

    RadioMixin._handle_dx_tuning(obj)

    obj._start_dx_tuning.assert_called_once_with(scoring_mode="snr")
    assert obj._pending_dx_diversity is True
    assert obj._pending_diversity_scoring == "dx"
