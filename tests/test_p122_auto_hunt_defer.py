"""P122 — Auto-Hunt-Stop bei laufendem QSO defern (3 Defer-Reasons).

13 Tests decken alle Defer/Sofort-Pfade + Edge-Cases ab:
- 3 Defer-Reasons (timer_expired, mouse_inactive_5min, totmann_expired)
- 4 Sofort-Reasons (manual_halt, swr_block, band_change, weitere)
- Flush-Pfad bei QSO-Ende
- First-Wins-FIFO bei multiple Defers
- Reset bei sofortigem Stop
- Backward-compat (legacy-Konstruktor ohne Callback)
- Defensive Idempotenz (Doppel-Stop)
"""
from __future__ import annotations

import pytest


def _make_auto_hunt(is_qso_active=False):
    """Helper: AutoHunt mit Callback + active=True (= 'läuft gerade')."""
    from core.auto_hunt import AutoHunt
    ah = AutoHunt(is_qso_active_callback=lambda: is_qso_active)
    ah.active = True   # simuliere laufende Session
    return ah


def _captured_signal_count(ah):
    """Helper: zähle wie oft auto_hunt_stopped emittiert wurde."""
    captured = []
    ah.auto_hunt_stopped.connect(lambda r: captured.append(r))
    return captured


# ── Defer-Pfad ───────────────────────────────────────────────────


def test_timer_expired_defers_when_qso_active(qapp):
    ah = _make_auto_hunt(is_qso_active=True)
    captured = _captured_signal_count(ah)
    ah.stop_auto_hunt("timer_expired")
    assert ah.active is True, "Defer: active darf NICHT False werden"
    assert ah._pending_stop_reason == "timer_expired"
    assert captured == [], "Defer: kein Signal-Emit"


def test_timer_expired_immediate_when_qso_idle(qapp):
    ah = _make_auto_hunt(is_qso_active=False)
    captured = _captured_signal_count(ah)
    ah.stop_auto_hunt("timer_expired")
    assert ah.active is False, "Sofort: active=False"
    assert ah._pending_stop_reason is None
    assert captured == ["timer_expired"], "Sofort: Signal-Emit"


def test_mouse_inactive_defers_when_qso_active(qapp):
    ah = _make_auto_hunt(is_qso_active=True)
    ah.stop_auto_hunt("mouse_inactive_5min")
    assert ah.active is True
    assert ah._pending_stop_reason == "mouse_inactive_5min"


def test_totmann_expired_defers_when_qso_active(qapp):
    ah = _make_auto_hunt(is_qso_active=True)
    ah.stop_auto_hunt("totmann_expired")
    assert ah.active is True
    assert ah._pending_stop_reason == "totmann_expired"


# ── Sofort-Pfad (Hardware-Safety / Kontext-Wechsel) ───────────────


def test_manual_halt_immediate_even_with_qso_active(qapp):
    """User-Notbremse greift sofort, auch wenn QSO läuft."""
    ah = _make_auto_hunt(is_qso_active=True)
    captured = _captured_signal_count(ah)
    ah.stop_auto_hunt("manual_halt")
    assert ah.active is False
    assert ah._pending_stop_reason is None
    assert captured == ["manual_halt"]


def test_swr_block_immediate_even_with_qso_active(qapp):
    """SWR-Watchdog = Hardware-Safety, niemals defern."""
    ah = _make_auto_hunt(is_qso_active=True)
    captured = _captured_signal_count(ah)
    ah.stop_auto_hunt("swr_block")
    assert ah.active is False
    assert captured == ["swr_block"]


def test_band_change_immediate_even_with_qso_active(qapp):
    """Band-Wechsel = Hardware-Kontext-Wechsel, laufender Ruf wäre obsolet."""
    ah = _make_auto_hunt(is_qso_active=True)
    captured = _captured_signal_count(ah)
    ah.stop_auto_hunt("band_change")
    assert ah.active is False
    assert captured == ["band_change"]


# ── Flush-Pfad ───────────────────────────────────────────────────


def test_flush_pending_stop_completes_deferred_stop(qapp):
    """QSO endet → flush_pending_stop führt echten Stop aus."""
    from core.auto_hunt import AutoHunt
    # AutoHunt mit Callback der erst True, dann False liefert
    qso_active = [True]
    ah = AutoHunt(is_qso_active_callback=lambda: qso_active[0])
    ah.active = True

    captured = _captured_signal_count(ah)

    # Defer-Stop während QSO aktiv
    ah.stop_auto_hunt("timer_expired")
    assert ah._pending_stop_reason == "timer_expired"
    assert ah.active is True

    # QSO endet
    qso_active[0] = False
    ah.flush_pending_stop()

    # Echter Stop läuft jetzt durch
    assert ah.active is False
    assert ah._pending_stop_reason is None
    assert captured == ["timer_expired"]


def test_flush_pending_stop_no_op_when_no_pending(qapp):
    ah = _make_auto_hunt(is_qso_active=False)
    captured = _captured_signal_count(ah)
    ah.flush_pending_stop()
    assert ah.active is True
    assert captured == []


# ── Edge-Cases ───────────────────────────────────────────────────


def test_first_defer_reason_wins_fifo(qapp):
    """Multiple Defers → erster gewinnt (FIFO), zweiter wird verworfen."""
    ah = _make_auto_hunt(is_qso_active=True)
    ah.stop_auto_hunt("timer_expired")
    assert ah._pending_stop_reason == "timer_expired"
    ah.stop_auto_hunt("mouse_inactive_5min")
    assert ah._pending_stop_reason == "timer_expired", \
        "First-Wins: zweiter Defer darf nicht überschreiben"


def test_immediate_stop_resets_pending(qapp):
    """HALT während Defer-Pending → Pending wird geleert, kein Folge-Flush."""
    ah = _make_auto_hunt(is_qso_active=True)
    captured = _captured_signal_count(ah)

    # Erst Defer
    ah.stop_auto_hunt("timer_expired")
    assert ah._pending_stop_reason == "timer_expired"

    # User klickt HALT (sofort)
    ah.stop_auto_hunt("manual_halt")
    assert ah.active is False
    assert ah._pending_stop_reason is None, \
        "Sofort-Stop muss Pending leeren"
    assert captured == ["manual_halt"]

    # Folge-Flush ist no-op
    ah.flush_pending_stop()
    assert captured == ["manual_halt"], "Kein zweiter Signal-Emit"


def test_legacy_constructor_no_callback_never_defers(qapp):
    """AutoHunt() ohne Callback → Default-Fallback `lambda: False` →
    Backward-Compat: alle alten Tests + Legacy-Init bleiben funktional.
    """
    from core.auto_hunt import AutoHunt
    ah = AutoHunt()   # KEIN Callback
    ah.active = True

    captured = _captured_signal_count(ah)
    # Defer-Reason kommt, aber Callback liefert False (kein QSO) → sofort Stop
    ah.stop_auto_hunt("timer_expired")
    assert ah.active is False
    assert captured == ["timer_expired"]


def test_defensive_idempotency_double_stop(qapp):
    """Schon inaktiv + kein Pending → stop_auto_hunt ist no-op, kein Signal."""
    ah = _make_auto_hunt(is_qso_active=False)
    captured = _captured_signal_count(ah)

    ah.stop_auto_hunt("manual_halt")
    assert captured == ["manual_halt"]

    # Zweiter Stop-Aufruf (Race / Doppel-Click)
    ah.stop_auto_hunt("manual_halt")
    assert captured == ["manual_halt"], \
        "Defensive: kein zweites Signal bei bereits inaktivem AutoHunt"


# ── pytest qapp Fixture ─────────────────────────────────────────


@pytest.fixture(scope="module")
def qapp():
    """Minimal QApplication für QObject/Signal-Lifecycle."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
