"""P60 (v0.97.32): User-Stop-Pfade brechen TX-Slot sofort ab + Click-Puffer.

Bug-Wurzel: OMNI/Auto-Hunt/Normal-CQ Toggle-Off ruft nur State-Stop
(Flags), kein encoder.abort + ptt_off. Resultat: 15s-Slot läuft komplett
durch trotz Button-Wechsel.

Plus R1-V4-pro-F1: gepufferter Station-Click (_pending_station_click)
muss bei Stop verworfen werden — sonst startet er nach tx_finished ein
ungewünschtes QSO.

Fix: zentraler Helper `_abort_active_tx()` in mw_tx.py, nutzt von:
- OMNI Toggle-Off (main_window.py)
- Auto-Hunt Toggle-Off (main_window.py)
- Normal-CQ Toggle-Off (mw_qso.py)
- HALT-Button (mw_qso.py:_on_cancel, refactor von Inline-Block)

NICHT genutzt von:
- SWR-Watchdog (eigener Spike-Schutz-Flow)
- Bandwechsel/Mode-Wechsel (eigene Cleanup-Sequenzen)
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


# ─────────────────────────────────────────────────────────────────────
# Behavior-Tests des Helpers (Unit)
# ─────────────────────────────────────────────────────────────────────

def _make_mock_self_with_helper():
    """Baut ein SimpleNamespace-Self mit dem Helper-Code."""
    obj = SimpleNamespace()
    obj.encoder = SimpleNamespace(
        is_transmitting=True,
        abort=MagicMock(),
    )
    obj.radio = SimpleNamespace(
        ip="1.2.3.4",
        ptt_off=MagicMock(),
    )
    obj._pending_station_click = "some_msg"
    # Bind helper from real source
    from ui.mw_tx import TXMixin
    obj._abort_active_tx = TXMixin._abort_active_tx.__get__(obj)
    return obj


def test_t1_helper_aborts_and_ptts_off_when_tx_active():
    """T1: encoder.is_transmitting=True + radio.ip set → abort+ptt_off."""
    obj = _make_mock_self_with_helper()
    obj._abort_active_tx()
    obj.encoder.abort.assert_called_once()
    obj.radio.ptt_off.assert_called_once()


def test_t2_helper_is_noop_when_not_transmitting():
    """T2: encoder.is_transmitting=False → no-op (idempotent)."""
    obj = _make_mock_self_with_helper()
    obj.encoder.is_transmitting = False
    obj._abort_active_tx()
    obj.encoder.abort.assert_not_called()
    obj.radio.ptt_off.assert_not_called()


def test_t3_helper_skips_ptt_off_when_radio_ip_none():
    """T3: encoder.is_transmitting=True + radio.ip=None → abort, kein ptt_off."""
    obj = _make_mock_self_with_helper()
    obj.radio.ip = None
    obj._abort_active_tx()
    obj.encoder.abort.assert_called_once()
    obj.radio.ptt_off.assert_not_called()


def test_t9_helper_clears_pending_station_click():
    """T9 (R1-F1): _pending_station_click wird auf None gesetzt."""
    obj = _make_mock_self_with_helper()
    obj._pending_station_click = "buffered_msg"
    obj._abort_active_tx()
    assert obj._pending_station_click is None


def test_t10_helper_safe_without_pending_click_attr():
    """T10 (R1-F1): kein Crash wenn _pending_station_click-Attribut fehlt."""
    obj = SimpleNamespace()
    obj.encoder = SimpleNamespace(is_transmitting=False, abort=MagicMock())
    obj.radio = SimpleNamespace(ip=None, ptt_off=MagicMock())
    from ui.mw_tx import TXMixin
    obj._abort_active_tx = TXMixin._abort_active_tx.__get__(obj)
    obj._abort_active_tx()  # darf nicht crashen


# ─────────────────────────────────────────────────────────────────────
# Source-Level-Tests (Bug-Schutz)
# ─────────────────────────────────────────────────────────────────────

def test_t4_omni_toggle_off_calls_helper():
    """T4: _on_btn_omni_cq_toggled Stop-Pfad ruft _abort_active_tx."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "main_window.py").read_text()
    method_start = src.find("def _on_btn_omni_cq_toggled")
    method_end = src.find("\n    def ", method_start + 10)
    body = src[method_start:method_end]
    # Helper muss VOR omni_cq.stop("manual_halt") aufgerufen werden
    helper_idx = body.find("_abort_active_tx")
    stop_idx = body.find('_omni_cq.stop("manual_halt")')
    assert helper_idx > 0, "P60: _on_btn_omni_cq_toggled muss _abort_active_tx aufrufen"
    assert helper_idx < stop_idx, "P60: _abort_active_tx muss VOR _omni_cq.stop kommen"


def test_t5_auto_hunt_toggle_off_calls_helper():
    """T5: _on_btn_auto_hunt_toggled Stop-Pfad ruft _abort_active_tx."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "main_window.py").read_text()
    method_start = src.find("def _on_btn_auto_hunt_toggled")
    method_end = src.find("\n    def ", method_start + 10)
    body = src[method_start:method_end]
    helper_idx = body.find("_abort_active_tx")
    stop_idx = body.find('stop_auto_hunt("manual_halt")')
    assert helper_idx > 0, "P60: _on_btn_auto_hunt_toggled muss _abort_active_tx aufrufen"
    assert helper_idx < stop_idx, "P60: _abort_active_tx muss VOR stop_auto_hunt kommen"


def test_t6_normal_cq_stop_calls_helper():
    """T6: _on_cq_clicked Else-Branch ruft _abort_active_tx."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "mw_qso.py").read_text()
    method_start = src.find("def _on_cq_clicked")
    method_end = src.find("\n    @Slot", method_start + 10)
    if method_end < 0:
        method_end = src.find("\n    def ", method_start + 10)
    body = src[method_start:method_end]
    assert "_abort_active_tx" in body, (
        "P60: _on_cq_clicked Else-Branch muss _abort_active_tx aufrufen"
    )
    # Helper-Call muss VOR qso_sm.stop_cq() stehen
    helper_idx = body.find("_abort_active_tx")
    stop_idx = body.find("qso_sm.stop_cq()")
    assert helper_idx < stop_idx, (
        "P60: _abort_active_tx muss VOR qso_sm.stop_cq() kommen"
    )


def test_t7_swr_watchdog_unchanged():
    """T7: _on_swr_alarm bleibt mit eigenem Inline-Block (NICHT Helper).

    SWR-Watchdog hat eigenen Spike-Schutz-Flow mit add_info + Modal —
    Inline-Block bleibt für Lesbarkeit.
    """
    src = (Path(__file__).resolve().parent.parent / "ui" / "mw_tx.py").read_text()
    method_start = src.find("def _on_swr_alarm")
    method_end = src.find("\n    def ", method_start + 10)
    if method_end < 0:
        method_end = len(src)
    body = src[method_start:method_end]
    # SWR-Watchdog ruft NICHT _abort_active_tx
    assert "_abort_active_tx" not in body, (
        "P60: _on_swr_alarm darf NICHT _abort_active_tx aufrufen — "
        "eigener Spike-Schutz-Flow"
    )
    # Aber direkter encoder.abort + ptt_off muss erhalten bleiben
    assert "self.encoder.abort()" in body, (
        "P60: _on_swr_alarm muss eigenen encoder.abort() behalten"
    )
    assert "self.radio.ptt_off()" in body, (
        "P60: _on_swr_alarm muss eigenen radio.ptt_off() behalten"
    )


def test_t8_helper_does_not_change_antenna():
    """T8 (Hardware-Pflicht): _abort_active_tx greift NICHT in Antennen-Wahl.

    ANT1-Pflicht (TX immer ANT1) — Helper darf set_tx_antenna NICHT aufrufen.
    Source-Test prüft nach Method-Aufruf-Pattern, NICHT nach Kommentar-Text.
    """
    src = (Path(__file__).resolve().parent.parent / "ui" / "mw_tx.py").read_text()
    method_start = src.find("def _abort_active_tx")
    method_end = src.find("\n    def ", method_start + 10)
    body = src[method_start:method_end]
    # Kommentare entfernen, dann nach Method-Aufrufen suchen
    code_lines = [ln for ln in body.split("\n") if not ln.lstrip().startswith("#")]
    code_only = "\n".join(code_lines)
    # Docstring auch raus (zwischen """ ... """)
    if '"""' in code_only:
        parts = code_only.split('"""')
        # Behalte nur Code außerhalb von Docstrings (jeder 2. Block)
        code_only = "".join(parts[::2])
    # Aufruf-Pattern suchen: .set_tx_antenna( oder set_tx_antenna(
    assert ".set_tx_antenna(" not in code_only, (
        "P60: _abort_active_tx darf .set_tx_antenna(...) NICHT aufrufen "
        "(ANT1-Pflicht-Hardware-Schutz)"
    )


def test_halt_uses_helper():
    """Konsistenz: _on_cancel (HALT) nutzt Helper statt Inline-Block."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "mw_qso.py").read_text()
    method_start = src.find("def _on_cancel")
    method_end = src.find("\n    def ", method_start + 10)
    body = src[method_start:method_end]
    assert "_abort_active_tx" in body, (
        "P60: _on_cancel sollte _abort_active_tx nutzen (Konsistenz mit "
        "Toggle-Stop-Pfaden)"
    )
