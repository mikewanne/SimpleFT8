"""FT-Modus-Wechsel bricht laufendes QSO/TX ab (v0.98.64, 03.06.2026).

Field-Bug (Mike): Auto-Hunt lief auf FT8 (rief Station LY7Z). Mike klickt direkt
auf FT4 (Modus-Wechsel, KEIN HALT). Auto-Hunt stoppt korrekt, ABER die
QSO-State-Machine sendet danach noch 3x weiter — auf dem neuen Modus/Band.

Ursache: `_on_mode_changed` stoppte nur Auto-Hunt + OMNI, brach aber das laufende
QSO + TX nicht ab — im Gegensatz zu `_on_band_changed` + `_on_rx_mode_changed`,
die das tun. Fix: gemeinsamer Helper `_abort_qso_and_tx()`, von allen drei
Wechsel-Pfaden gerufen (DRY → „mode-aware Symmetrie"-Bug-Klasse strukturell weg).
DeepSeek-R1 GO + Final-R1.

Test-Pattern analog test_bundle_i: echte RadioMixin-Methode an MagicMock binden.
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


@pytest.fixture(autouse=True)
def _isolate_ntp(monkeypatch):
    """`_on_mode_changed` ruft das echte `ntp_time.set_mode(mode, band)`
    (globaler Modul-State). Im Test no-op, sonst leakt `_mode='FT4'` in
    nachfolgende Tests (z.B. test_modules::test_ntp_reset → −0.3-Delta)."""
    import core.ntp_time as _ntp
    monkeypatch.setattr(_ntp, "set_mode", lambda *a, **k: None)


def _make(*, cq_mode: bool = False, qso_state_name: str = "IDLE",
          is_transmitting: bool = False, radio_ip: str = "192.168.1.68",
          has_pending_log: bool = True):
    """Mock mit echtem `_abort_qso_and_tx` gebunden."""
    from ui.mw_radio import RadioMixin
    from core.qso_state import QSOState

    obj = MagicMock()
    obj._abort_qso_and_tx = RadioMixin._abort_qso_and_tx.__get__(obj)

    obj.radio = MagicMock()
    obj.radio.ip = radio_ip
    obj.qso_sm = MagicMock()
    obj.qso_sm.cq_mode = cq_mode
    obj.qso_sm.state = getattr(QSOState, qso_state_name)
    obj.encoder = MagicMock()
    obj.encoder.is_transmitting = is_transmitting
    obj.control_panel = MagicMock()
    if has_pending_log:
        obj._pending_tx_log = {"message": "LY7Z DA1MHH -17"}
    return obj


def _make_mode(*, current_mode: str = "FT8", locked: bool = False):
    """Mock mit echtem `_on_mode_changed`, `_abort_qso_and_tx` als Spy.

    `_rx_mode='diversity'` → `_on_mode_changed` nimmt nach dem Abbruch den
    frühen `return` (Diversity-Preset-Pfad) → kompakter, robuster Durchlauf.
    """
    from ui.mw_radio import RadioMixin

    obj = MagicMock()
    obj._on_mode_changed = RadioMixin._on_mode_changed.__get__(obj)
    obj._abort_qso_and_tx = MagicMock()  # Spy
    obj._gain_measure_locked = locked
    obj._rx_mode = "diversity"
    obj.settings = MagicMock()
    obj.settings.mode = current_mode
    obj.settings.band = "20m"
    obj.radio = MagicMock()
    obj.radio.ip = "192.168.1.68"
    obj._auto_hunt = MagicMock()
    obj._auto_hunt.active = False
    obj._omni_cq = MagicMock()
    obj._omni_cq.is_active = MagicMock(return_value=False)
    return obj


# ── _abort_qso_and_tx: Kern-Logik ───────────────────────────────────────────

def test_abort_cancels_active_qso(app):
    """Aktives QSO (State != IDLE) + TX → stop_cq, cancel, abort, ptt_off."""
    obj = _make(qso_state_name="WAIT_REPORT", is_transmitting=True)
    obj._abort_qso_and_tx()
    obj.qso_sm.stop_cq.assert_called_once()
    obj.qso_sm.cancel.assert_called_once()
    obj.control_panel.set_cq_active.assert_called_once_with(False)
    obj.encoder.abort.assert_called_once()
    obj.radio.ptt_off.assert_called_once()


def test_abort_cancels_cq_mode(app):
    """Reiner CQ-Ruf (cq_mode=True, State IDLE) wird auch abgebrochen."""
    obj = _make(cq_mode=True, qso_state_name="IDLE", is_transmitting=False)
    obj._abort_qso_and_tx()
    obj.qso_sm.stop_cq.assert_called_once()
    obj.qso_sm.cancel.assert_called_once()


def test_abort_idle_no_cancel(app):
    """IDLE + kein CQ + kein TX → KEIN cancel, KEIN abort (kein no-op-Spam)."""
    obj = _make(cq_mode=False, qso_state_name="IDLE", is_transmitting=False)
    obj._abort_qso_and_tx()
    obj.qso_sm.cancel.assert_not_called()
    obj.encoder.abort.assert_not_called()
    obj.radio.ptt_off.assert_not_called()


def test_abort_no_ptt_without_radio_ip(app):
    """Kein Radio verbunden → abort ja, ptt_off NICHT (radio.ip leer)."""
    obj = _make(qso_state_name="WAIT_REPORT", is_transmitting=True, radio_ip="")
    obj._abort_qso_and_tx()
    obj.encoder.abort.assert_called_once()
    obj.radio.ptt_off.assert_not_called()


def test_abort_discards_pending_tx_log(app):
    """P131-Pattern: vorgemerkter Sende-Log-Eintrag wird verworfen."""
    obj = _make(qso_state_name="WAIT_REPORT", is_transmitting=True,
                has_pending_log=True)
    assert obj._pending_tx_log is not None
    obj._abort_qso_and_tx()
    assert obj._pending_tx_log is None


def test_abort_pending_log_discarded_even_when_idle(app):
    """Pending-TX-Log-Discard läuft UNABHÄNGIG von is_transmitting (P131)."""
    obj = _make(qso_state_name="IDLE", is_transmitting=False, has_pending_log=True)
    obj._abort_qso_and_tx()
    assert obj._pending_tx_log is None


# ── _on_mode_changed: ruft Abbruch + Early-Returns ──────────────────────────

def test_mode_change_aborts_qso(app):
    """DER FIX: echter Modus-Wechsel (FT8→FT4) ruft _abort_qso_and_tx."""
    obj = _make_mode(current_mode="FT8")
    obj._on_mode_changed("FT4")
    obj._abort_qso_and_tx.assert_called_once()


def test_mode_change_same_mode_no_abort(app):
    """Re-Klick auf den schon aktiven Modus → Early-Return, KEIN Abbruch."""
    obj = _make_mode(current_mode="FT8")
    obj._on_mode_changed("FT8")
    obj._abort_qso_and_tx.assert_not_called()
    obj.settings.set.assert_not_called()  # auch kein settings-Write


def test_mode_change_pipeline_locked_no_abort(app):
    """Während Kalibrier-Pipeline (_gain_measure_locked) → kein Abbruch."""
    obj = _make_mode(current_mode="FT8", locked=True)
    obj._on_mode_changed("FT4")
    obj._abort_qso_and_tx.assert_not_called()
