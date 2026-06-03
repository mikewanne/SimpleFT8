"""v0.99.3 — PSK-Timer spinnt nicht mehr bei Intervall 0 (4GB-Log-Flut-Fix).

Field-Bug 03.06.2026: `_reset_psk_polling_on_change` startet `_psk_timer` mit
`start(0)` (Sofort-Fetch). Ein QTimer mit Intervall 0 feuert so schnell wie die
Event-Loop kann. Lag die Intervall-Umschaltung hinter dem `_has_sent_cq`-Return,
blieb der Timer bei 0 solange kein CQ raus war → tausende SKIP-Logzeilen/s → 4GB/Tag.

Fix: Intervall-Umschaltung VOR den `_has_sent_cq`-Return. Test ueber die
unbound-Method mit Fake-Self (kein schwergewichtiges MainWindow noetig).
"""
from __future__ import annotations

import inspect
import types


class _FakeTimer:
    def __init__(self, iv):
        self._iv = iv

    def interval(self):
        return self._iv

    def setInterval(self, v):
        self._iv = v


class _FakeLabel:
    def setText(self, t):
        self.text = t

    def setStyleSheet(self, s):
        pass


def _fake_self(first_fetch, interval, has_cq):
    return types.SimpleNamespace(
        _psk_first_fetch=first_fetch,
        _psk_timer=_FakeTimer(interval),
        _psk_repeat_interval=300000,
        _has_sent_cq=has_cq,
        control_panel=types.SimpleNamespace(psk_label=_FakeLabel()),
    )


def test_no_cq_first_tick_normalizes_interval():
    """Kern-Fix: erster Tick (Intervall 0, kein CQ) → Intervall auf 5 Min →
    kein Spin mehr."""
    from ui.main_window import MainWindow
    fake = _fake_self(first_fetch=True, interval=0, has_cq=False)
    MainWindow._fetch_psk_stats(fake)
    assert fake._psk_timer.interval() == 300000, "Intervall muss vom 0-Spin weg"
    assert fake._psk_first_fetch is False


def test_no_cq_subsequent_tick_stable():
    """Folge-Tick ohne CQ: Intervall bleibt beim Ruhe-Wert (kein erneutes
    Umschalten, kein Spin)."""
    from ui.main_window import MainWindow
    fake = _fake_self(first_fetch=False, interval=300000, has_cq=False)
    MainWindow._fetch_psk_stats(fake)
    assert fake._psk_timer.interval() == 300000


def test_flood_skip_log_removed():
    """Die per-Tick-Flut-Logzeile (`SKIP — _has_sent_cq`) ist entfernt."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._fetch_psk_stats)
    assert "SKIP — _has_sent_cq" not in src
    # Intervall-Umschaltung steht VOR dem _has_sent_cq-Guard
    idx_interval = src.index("setInterval")
    idx_guard = src.index("if not self._has_sent_cq")
    assert idx_interval < idx_guard, "setInterval muss vor dem no-CQ-Return stehen"
