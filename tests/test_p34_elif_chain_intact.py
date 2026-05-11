"""Regression-Test: P34-Hook in mw_cycle._on_cycle_decoded darf die
elif-Kette nicht zerreissen.

Mike-Field-Test 11.05.2026: Diversity DX zeigte nur A1-Stationen weil
mein P34-Hook zwischen `if diversity` und `elif normal` eingefuegt war —
die elif-Kette haengte sich an mein P34-`if` an statt am Diversity-`if`,
sodass _handle_dx_tune_mode in Diversity-Mode-Slots aufgerufen wurde
und RX-Panel mit current_ant="A1" (Default ohne dx_tune_dialog)
ueberschrieb.

Diese Tests verifizieren strukturell:
1. _handle_diversity_operate wird im Diversity-Mode aufgerufen
2. _handle_dx_tune_mode wird NICHT im Diversity-Mode aufgerufen
3. _handle_normal_mode wird im Normal-Mode aufgerufen
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.mw_cycle import CycleMixin


def _make_cycle_mock(rx_mode="diversity", messages_count=3, dynamic_active=False):
    """Minimaler Mock-Setup fuer _on_cycle_decoded."""
    s = MagicMock()
    s._rx_mode = rx_mode
    s._dx_tune_dialog = None
    s.rx_panel = MagicMock()
    s.rx_panel._rx_active = True
    s.control_panel = MagicMock()
    s.decoder = MagicMock()
    s.decoder.dump_last_slot = MagicMock()
    s._audio_dump_enabled = False
    s._diversity_ctrl = MagicMock()
    s._diversity_ctrl.phase = "operate"
    s._pop_diversity_queue = MagicMock(return_value=("A2", "operate"))
    s._resolve_hardware_antenna = MagicMock(side_effect=lambda x: x)
    s._assign_slot_parity = MagicMock()
    s._update_dt_correction = MagicMock()
    s._handle_diversity_measure = MagicMock()
    s._handle_diversity_operate = MagicMock()
    s._handle_normal_mode = MagicMock()
    s._handle_dx_tune_mode = MagicMock()
    s._dynamic_ctrl = MagicMock()
    s._dynamic_ctrl.is_active = MagicMock(return_value=dynamic_active)
    s._dynamic_ctrl.record_slot = MagicMock()
    # FT8-Messages-Mock
    messages = [SimpleNamespace(snr=-15) for _ in range(messages_count)]
    return s, messages


def test_diversity_mode_dx_tune_NOT_called():
    """KRITISCH: Im Diversity-Mode darf _handle_dx_tune_mode NIE aufgerufen
    werden — auch wenn Dynamic AUS. Sonst wird RX-Panel mit A1-Default
    ueberschrieben (Mike-Field-Test 11.05. Bug)."""
    s, msgs = _make_cycle_mock(rx_mode="diversity", dynamic_active=False)
    CycleMixin._on_cycle_decoded(s, msgs)

    s._handle_diversity_operate.assert_called_once()
    s._handle_dx_tune_mode.assert_not_called()
    s._handle_normal_mode.assert_not_called()


def test_diversity_mode_dynamic_active_records_slot():
    """Diversity + Dynamic AN: record_slot wird zusaetzlich gerufen."""
    s, msgs = _make_cycle_mock(rx_mode="diversity", dynamic_active=True)
    CycleMixin._on_cycle_decoded(s, msgs)

    s._handle_diversity_operate.assert_called_once()
    s._dynamic_ctrl.record_slot.assert_called_once()
    # dx_tune wird trotzdem nicht aufgerufen
    s._handle_dx_tune_mode.assert_not_called()


def test_diversity_mode_dynamic_inactive_no_record():
    """Diversity + Dynamic AUS: record_slot NICHT gerufen."""
    s, msgs = _make_cycle_mock(rx_mode="diversity", dynamic_active=False)
    CycleMixin._on_cycle_decoded(s, msgs)

    s._dynamic_ctrl.record_slot.assert_not_called()


def test_normal_mode_normal_handler_called():
    """Normal-Mode: _handle_normal_mode wird gerufen, kein Diversity/dx_tune."""
    s, msgs = _make_cycle_mock(rx_mode="normal", dynamic_active=False)
    CycleMixin._on_cycle_decoded(s, msgs)

    s._handle_normal_mode.assert_called_once()
    s._handle_diversity_operate.assert_not_called()
    s._handle_dx_tune_mode.assert_not_called()
    s._dynamic_ctrl.record_slot.assert_not_called()


def test_dx_tune_mode_dx_tune_handler_called():
    """Sonstiger Mode mit Messages (z.B. dx_tuning): _handle_dx_tune_mode."""
    s, msgs = _make_cycle_mock(rx_mode="dx_tuning", dynamic_active=False)
    CycleMixin._on_cycle_decoded(s, msgs)

    s._handle_dx_tune_mode.assert_called_once()
    s._handle_diversity_operate.assert_not_called()
    s._handle_normal_mode.assert_not_called()
