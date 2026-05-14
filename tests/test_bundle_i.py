"""Bundle I (14.05.2026, v0.97.25 → v0.97.26) — OMNI-CQ-Race + Stop-Block.

Mike-Field-Test 14.05.2026 nachmittags: OMNI-CQ aktiv, Mode-Wechsel,
OMNI-Schalter geht aus, aber ein verzögerter CQ-Slot wird trotzdem
gesendet (aus normalem CQ-Pfad qso_sm.cq_mode).

R1-V4-pro Finding 1: encoder.abort() + ptt_off() ist nötig damit
kein armed-er Slot durchrutscht. Bundle-I-Fix: Stop-Block in
_on_rx_mode_changed analog Bandwechsel-Pattern (Z.404-414).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_mw_radio(*, cq_mode: bool = False,
                   qso_state_name: str = "IDLE",
                   is_transmitting: bool = False,
                   radio_ip: str = "192.168.1.68",
                   omni_active: bool = False,
                   hunt_active: bool = False,
                   current_rx_mode: str = "normal"):
    """Test-Setup: minimaler Mock fuer _on_rx_mode_changed Stop-Block."""
    from ui.mw_radio import RadioMixin
    from core.qso_state import QSOState

    # Kein spec= weil RadioMixin-Methoden während Mode-Wechsel auto-magisch
    # gerufen werden (z.B. _update_button_visibility) — strict-Spec wäre
    # zu eng für den Stop-Block-Test.
    obj = MagicMock()
    obj._on_rx_mode_changed = (
        RadioMixin._on_rx_mode_changed.__get__(obj))

    # Pipeline-Lock-Check und radio.ip-Guard
    obj._gain_measure_locked = False
    obj._rx_mode = current_rx_mode

    obj.radio = MagicMock()
    obj.radio.ip = radio_ip
    obj.radio.ptt_off = MagicMock()
    obj.radio.set_tx_antenna = MagicMock()

    # qso_sm
    obj.qso_sm = MagicMock()
    obj.qso_sm.cq_mode = cq_mode
    obj.qso_sm.state = getattr(QSOState, qso_state_name)
    obj.qso_sm.stop_cq = MagicMock()
    obj.qso_sm.cancel = MagicMock()

    # control_panel
    obj.control_panel = MagicMock()
    obj.control_panel.set_cq_active = MagicMock()
    obj.control_panel.set_rx_mode = MagicMock()
    obj.control_panel._freq_hist = MagicMock()
    obj.control_panel.btn_diversity = MagicMock()
    obj.control_panel.update_decode_count = MagicMock()

    # encoder
    obj.encoder = MagicMock()
    obj.encoder.is_transmitting = is_transmitting
    obj.encoder.abort = MagicMock()

    # omni + hunt
    obj._omni_cq = MagicMock()
    obj._omni_cq.is_active = MagicMock(return_value=omni_active)
    obj._omni_cq.stop = MagicMock()
    obj._auto_hunt = MagicMock()
    obj._auto_hunt.active = hunt_active
    obj._auto_hunt.stop_auto_hunt = MagicMock()

    # diversity / decoder / panels
    obj._easter_egg_active = True
    obj._stats_warmup_cycles = 0
    obj._normal_stations = {}
    obj.rx_panel = MagicMock()
    obj.rx_panel.table = MagicMock()
    obj.rx_panel.table.setRowCount = MagicMock()
    obj.qso_panel = MagicMock()
    obj.qso_panel.log_view = MagicMock()
    obj.qso_panel.log_view.clear = MagicMock()
    obj.qso_panel.set_slot_buttons_visible = MagicMock()
    obj.qso_panel.set_tx_slot_lock_buttons = MagicMock()
    obj.decoder = MagicMock()
    obj.decoder.set_quality = MagicMock()

    # settings (für mode-Wechsel-Pfad in diversity-branch)
    obj.settings = MagicMock()
    obj.settings.get = MagicMock(return_value="off")  # bandpilot off
    obj.settings.band = "20m"
    obj.settings.get_tx_slot_lock = MagicMock(return_value="none")

    obj._disable_diversity = MagicMock()
    obj._apply_normal_mode = MagicMock()
    obj._activate_diversity_with_scoring = MagicMock()
    obj._show_diversity_choice_dialog = MagicMock()
    obj._bandpilot = None

    return obj


# ── T4.1: Stop-Block stoppt qso_sm.cq_mode ────────────────────────────

def test_t4_1_stops_normal_cq_on_mode_change(app):
    """T4.1: cq_mode=True + Mode-Wechsel → qso_sm.stop_cq + cancel 1×."""
    obj = _make_mw_radio(cq_mode=True, qso_state_name="CQ_CALLING")
    obj._on_rx_mode_changed("diversity")
    obj.qso_sm.stop_cq.assert_called_once()
    obj.qso_sm.cancel.assert_called_once()
    obj.control_panel.set_cq_active.assert_any_call(False)


# ── T4.2: Realistisches Encoder-Armed-Szenario (R1-Finding 3) ─────────

def test_t4_2_full_stop_with_encoder_armed(app):
    """T4.2 (R1-Finding 3): cq_mode=True + State=CQ_CALLING +
    encoder.is_transmitting=True → kompletter Stop-Block läuft durch.

    Erwartete Calls: stop_cq, cancel, encoder.abort, ptt_off.
    """
    obj = _make_mw_radio(
        cq_mode=True,
        qso_state_name="CQ_CALLING",
        is_transmitting=True,
    )
    obj._on_rx_mode_changed("diversity")

    obj.qso_sm.stop_cq.assert_called_once()
    obj.qso_sm.cancel.assert_called_once()
    obj.encoder.abort.assert_called_once()
    obj.radio.ptt_off.assert_called_once()


# ── T4.3: Mode-Wechsel ohne aktiven CQ — kein no-op-Spam ──────────────

def test_t4_3_no_stop_when_idle(app):
    """T4.3: cq_mode=False, State=IDLE → stop_cq NICHT aufgerufen."""
    obj = _make_mw_radio(cq_mode=False, qso_state_name="IDLE")
    obj._on_rx_mode_changed("diversity")
    obj.qso_sm.stop_cq.assert_not_called()
    obj.qso_sm.cancel.assert_not_called()


# ── T4.4: OMNI + cq_mode beide an → beide gestoppt ────────────────────

def test_t4_4_omni_and_cq_both_stopped(app):
    """T4.4: OMNI aktiv + cq_mode True → beide gestoppt."""
    obj = _make_mw_radio(
        cq_mode=True,
        qso_state_name="CQ_CALLING",
        omni_active=True,
    )
    obj._on_rx_mode_changed("diversity")
    obj._omni_cq.stop.assert_called_once_with("rx_mode_change")
    obj.qso_sm.stop_cq.assert_called_once()


# ── T4.5: ANT1=TX-Pflicht — keine Antennen-Umschaltung im Stop-Block ──

def test_t4_5_no_antenna_switch_during_stop(app):
    """T4.5: set_tx_antenna wird im Stop-Block NICHT aufgerufen
    (Hardware-Sicherheit ANT1=TX, CLAUDE.md HARDWARE-WARNUNG)."""
    obj = _make_mw_radio(
        cq_mode=True,
        qso_state_name="CQ_CALLING",
        is_transmitting=True,
    )
    obj._on_rx_mode_changed("diversity")
    obj.radio.set_tx_antenna.assert_not_called()


# ── T4.6: Bandpilot-Pfad (programmatischer Mode-Wechsel) — auch Stop ──

def test_t4_6_bandpilot_path_also_stops_cq(app):
    """T4.6: _on_rx_mode_changed wird auch von _apply_bandpilot_auto
    programmatisch aufgerufen — Stop-Block läuft auch dort.
    Mike-Spec: OK (auto-Mode ist User-getriggert)."""
    obj = _make_mw_radio(cq_mode=True, qso_state_name="CQ_CALLING")
    # Simuliert Bandpilot-Auto-Pfad (egal wer ruft, gleicher Code-Pfad)
    obj._on_rx_mode_changed("diversity")
    obj.qso_sm.stop_cq.assert_called_once()


# ── T4.7: encoder.is_transmitting=False — abort NICHT aufgerufen ──────

def test_t4_7_no_encoder_abort_when_not_transmitting(app):
    """T4.7: is_transmitting=False → encoder.abort wird nicht aufgerufen
    (Guard greift), ptt_off wird auch nicht aufgerufen."""
    obj = _make_mw_radio(
        cq_mode=True,
        qso_state_name="CQ_CALLING",
        is_transmitting=False,
    )
    obj._on_rx_mode_changed("diversity")
    obj.encoder.abort.assert_not_called()
    obj.radio.ptt_off.assert_not_called()
    # Aber stop_cq wurde trotzdem gerufen (CQ ist aktiv)
    obj.qso_sm.stop_cq.assert_called_once()


# ── T4.8: Mode-Wechsel zum gleichen Modus (no-op) ─────────────────────

def test_t4_8_no_stop_when_same_mode(app):
    """T4.8: mode == old_mode → Stop-Block läuft NICHT (mode != old_mode
    Guard greift). cq_mode bleibt aktiv."""
    obj = _make_mw_radio(
        cq_mode=True,
        qso_state_name="CQ_CALLING",
        current_rx_mode="normal",
    )
    obj._on_rx_mode_changed("normal")  # gleicher Modus
    obj.qso_sm.stop_cq.assert_not_called()
    obj._omni_cq.stop.assert_not_called()
