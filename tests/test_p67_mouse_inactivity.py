"""P67 (v0.97.43) — Auto-Hunt Mouse-Inactivity-Schicht.

Mike-Spec Variante C: 10-Min-Hard-Cap bleibt, zusaetzliche Schicht
„5 Min ohne Mausbewegung → Auto-Hunt stoppt". Was zuerst greift, gewinnt.

Tests:
- T1: Konstante _AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S == 300.
- T2: _init_presence_watchdog initialisiert _auto_hunt_last_mouse_t.
- T3: _poll_mouse_activity setzt Anker bei Mausbewegung.
- T4: _on_btn_auto_hunt_toggled(True) setzt Anker.
- T5: Polling-Tick stoppt bei delta > 300.
- T6: Polling-Tick stoppt NICHT bei delta = 299 (Grenz-Test).
- T7: Polling-Tick stoppt NICHT bei active=False.
- T8: stop_auto_hunt("mouse_inactive_5min") raeumt cooldowns auf
       (DEFAULT-Branch, NICHT totmann-Branch).
- T9: Polling-Tick ruft NICHT _abort_active_tx (kein TX-Abbruch,
       Hardware-Pflicht).
- T10: stop_auto_hunt Docstring enthaelt mouse_inactive_5min.
- T11: Mehrfach-Reset — Mausbewegung mittendrin verhindert Stop.
- T12: Race timer_expired + mouse_inactive — mouse-Pfad kommt zuerst.
- T13: Reihenfolge — Anker MUSS vor start_auto_hunt gesetzt sein.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── T1 — Konstante ────────────────────────────────────────────────────


def test_t1_konstante_300():
    """Klassen-Konstante _AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S == 300."""
    from ui.main_window import MainWindow
    assert MainWindow._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S == 300


# ── T2 — Init initialisiert Anker auf 0.0 ─────────────────────────────


def test_t2_init_setzt_anker_default():
    """_init_presence_watchdog initialisiert _auto_hunt_last_mouse_t = 0.0.

    Source-Level-Check: greppt in der Methode nach der Zuweisung.
    """
    src = Path("ui/main_window.py").read_text()
    # Block ab _init_presence_watchdog bis naechste def
    idx = src.find("def _init_presence_watchdog(self)")
    assert idx > 0, "_init_presence_watchdog nicht gefunden"
    end = src.find("\n    def ", idx + 5)
    block = src[idx:end if end > 0 else len(src)]
    assert "self._auto_hunt_last_mouse_t" in block
    assert "0.0" in block or ": float = 0.0" in block


# ── T3 — _poll_mouse_activity setzt Anker bei Bewegung ────────────────


def test_t3_poll_setzt_anker_bei_bewegung():
    """Wenn Cursor sich bewegt, wird _auto_hunt_last_mouse_t auf monotonic()
    gesetzt (zusaetzlich zum existierenden _reset_presence)."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._presence_last_mouse_pos = (0, 0)
    obj._auto_hunt_last_mouse_t = 0.0
    obj._reset_presence = MagicMock()

    fake_t = 1234.567

    with patch.object(mw_mod, "time") as time_mock, \
         patch("PySide6.QtGui.QCursor") as cursor_mock:
        time_mock.monotonic.return_value = fake_t
        cursor_mock.pos.return_value = (50, 50)

        mw_mod.MainWindow._poll_mouse_activity(obj)

    obj._reset_presence.assert_called_once()
    assert obj._auto_hunt_last_mouse_t == fake_t


def test_t3b_poll_kein_anker_ohne_bewegung():
    """Cursor stillgehalten → Anker bleibt unveraendert."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._presence_last_mouse_pos = (50, 50)
    obj._auto_hunt_last_mouse_t = 100.0
    obj._reset_presence = MagicMock()

    with patch("PySide6.QtGui.QCursor") as cursor_mock:
        cursor_mock.pos.return_value = (50, 50)
        mw_mod.MainWindow._poll_mouse_activity(obj)

    obj._reset_presence.assert_not_called()
    assert obj._auto_hunt_last_mouse_t == 100.0


# ── T4 — _on_btn_auto_hunt_toggled(True) setzt Anker ──────────────────


def test_t4_toggle_setzt_anker():
    """_on_btn_auto_hunt_toggled(True) setzt Anker vor start_auto_hunt."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._auto_hunt = MagicMock(active=False)
    obj._auto_hunt_last_mouse_t = 0.0
    obj._omni_cq = MagicMock()
    obj._omni_cq.is_active.return_value = False
    obj.settings.band = "20m"
    obj._swr_blocked_bands = set()
    obj._on_auto_hunt_polling_tick = MagicMock()
    obj._auto_hunt_polling_timer = MagicMock()

    fake_t = 9999.5
    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = fake_t
        mw_mod.MainWindow._on_btn_auto_hunt_toggled(obj, True)

    assert obj._auto_hunt_last_mouse_t == fake_t
    obj._auto_hunt.start_auto_hunt.assert_called_once_with(600)


# ── T5 — Polling-Tick stoppt bei delta > 300 ─────────────────────────


def test_t5_polling_tick_stoppt_bei_inactivity():
    """delta = 301 → stop_auto_hunt("mouse_inactive_5min") + add_info."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300
    obj._auto_hunt = MagicMock(active=True)
    obj._auto_hunt_polling_timer = MagicMock()
    obj._auto_hunt_last_mouse_t = 0.0
    obj._abort_active_tx = MagicMock()
    obj.qso_panel = MagicMock()
    obj.control_panel = MagicMock()

    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 301.0
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)

    obj._auto_hunt.stop_auto_hunt.assert_called_once_with("mouse_inactive_5min")
    obj.qso_panel.add_info.assert_called_once()
    # Text-Update darf NICHT laufen (early return)
    obj.control_panel.btn_auto_hunt.setText.assert_not_called()


# ── T6 — Grenz-Test: delta = 299 → kein Stop ──────────────────────────


def test_t6_polling_tick_kein_stop_bei_299():
    """delta = 299 (knapp drunter) → KEIN Stop, Text-Update laeuft."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300
    obj._auto_hunt = MagicMock(active=True)
    obj._auto_hunt.seconds_remaining.return_value = 120
    obj._auto_hunt_polling_timer = MagicMock()
    obj._auto_hunt_last_mouse_t = 1.0
    obj.qso_panel = MagicMock()
    obj.control_panel = MagicMock()

    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 300.0  # delta = 299
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)

    obj._auto_hunt.stop_auto_hunt.assert_not_called()
    obj.qso_panel.add_info.assert_not_called()
    # Text-Update muss laufen
    obj.control_panel.btn_auto_hunt.setText.assert_called_once()


# ── T7 — active=False → Pre-Guard greift, kein Stop ───────────────────


def test_t7_polling_tick_kein_stop_wenn_inactive():
    """Wenn _auto_hunt.active=False → frueher Return, kein Mouse-Check."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300
    obj._auto_hunt = MagicMock(active=False)
    obj._auto_hunt_polling_timer = MagicMock()
    obj._auto_hunt_last_mouse_t = 0.0  # delta wuerde riesig sein
    obj.qso_panel = MagicMock()

    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 99999.0
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)

    obj._auto_hunt.stop_auto_hunt.assert_not_called()
    obj.qso_panel.add_info.assert_not_called()
    obj._auto_hunt_polling_timer.stop.assert_called_once()


# ── T8 — Cleanup-Logik bei mouse_inactive_5min (DEFAULT-Branch) ───────


def test_t8_cleanup_default_branch():
    """stop_auto_hunt("mouse_inactive_5min") → _cooldown.clear + last_tx_even=None."""
    from core.auto_hunt import AutoHunt

    h = AutoHunt()
    h.active = True
    h._cooldown = {"DL1AAA": time.time()}
    h._last_tx_even = True

    h.stop_auto_hunt("mouse_inactive_5min")

    assert h.active is False
    assert h._cooldown == {}  # DEFAULT-Branch: gecleart
    assert h._last_tx_even is None


def test_t8b_totmann_branch_unverändert():
    """totmann_expired behaelt cooldowns + last_tx_even (Regression-Schutz)."""
    from core.auto_hunt import AutoHunt

    h = AutoHunt()
    h.active = True
    now = time.time()
    h._cooldown = {"DL1AAA": now}
    h._last_tx_even = True

    h.stop_auto_hunt("totmann_expired")

    assert h.active is False
    assert "DL1AAA" in h._cooldown  # behaelt
    assert h._last_tx_even is True  # behaelt


# ── T9 — Hardware-Pflicht: kein _abort_active_tx bei Mouse-Stop ───────


def test_t9_kein_abort_active_tx():
    """Polling-Tick darf bei mouse_inactive NICHT _abort_active_tx rufen.

    Hardware-Pflicht (CLAUDE.md): laufender TX/QSO darf zu Ende laufen.
    """
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300
    obj._auto_hunt = MagicMock(active=True)
    obj._auto_hunt_polling_timer = MagicMock()
    obj._auto_hunt_last_mouse_t = 0.0
    obj._abort_active_tx = MagicMock()
    obj.qso_panel = MagicMock()

    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 500.0
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)

    obj._abort_active_tx.assert_not_called()


# ── T10 — Docstring enthaelt mouse_inactive_5min ──────────────────────


def test_t10_docstring_enthaelt_reason():
    """stop_auto_hunt Docstring listet mouse_inactive_5min."""
    from core.auto_hunt import AutoHunt
    doc = AutoHunt.stop_auto_hunt.__doc__ or ""
    assert "mouse_inactive_5min" in doc


# ── T11 — Mehrfach-Reset: Bewegung mittendrin verhindert Stop ────────


def test_t11_mehrfach_reset_verhindert_stop():
    """4 Min still, dann Bewegung, dann 4 Min still → kein Stop."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300
    obj._auto_hunt = MagicMock(active=True)
    obj._auto_hunt.seconds_remaining.return_value = 120
    obj._auto_hunt_polling_timer = MagicMock()
    obj.qso_panel = MagicMock()
    obj.control_panel = MagicMock()
    obj._presence_last_mouse_pos = (0, 0)
    obj._reset_presence = MagicMock()

    # Anker = 0.0 (frischer Init). Erster Tick simuliert t=240 (4 Min).
    obj._auto_hunt_last_mouse_t = 0.0
    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 240.0  # delta=240 < 300
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)
    obj._auto_hunt.stop_auto_hunt.assert_not_called()

    # Mausbewegung bei t=250 setzt Anker neu.
    with patch.object(mw_mod, "time") as time_mock, \
         patch("PySide6.QtGui.QCursor") as cursor_mock:
        time_mock.monotonic.return_value = 250.0
        cursor_mock.pos.return_value = (10, 10)
        mw_mod.MainWindow._poll_mouse_activity(obj)
    assert obj._auto_hunt_last_mouse_t == 250.0

    # Naechster Tick bei t=500 (4:10 nach Reset, < 5 Min) → kein Stop.
    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 500.0  # delta=250 < 300
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)
    obj._auto_hunt.stop_auto_hunt.assert_not_called()


# ── T12 — Race timer+mouse: mouse-Pfad kommt zuerst ──────────────────


def test_t12_race_timer_und_mouse_inactive():
    """Wenn beide Bedingungen gleichzeitig erfuellt: mouse-Pfad gewinnt
    (Check kommt VOR Text-Update). 10-Min-Hard-Cap wuerde im naechsten
    Tick durch _on_timer_expired in AutoHunt feuern, aber wir simulieren
    den ersten Tick danach."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._AUTO_HUNT_MOUSE_INACTIVITY_TIMEOUT_S = 300
    obj._auto_hunt = MagicMock(active=True)
    obj._auto_hunt_polling_timer = MagicMock()
    obj._auto_hunt_last_mouse_t = 0.0
    obj.qso_panel = MagicMock()

    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = 700.0  # > 10 Min UND > 5 Min Maus
        mw_mod.MainWindow._on_auto_hunt_polling_tick(obj)

    obj._auto_hunt.stop_auto_hunt.assert_called_once_with("mouse_inactive_5min")


# ── T13 — Reihenfolge: Anker VOR start_auto_hunt ─────────────────────


def test_t13_reihenfolge_anker_vor_start():
    """Sicherstellen dass Anker gesetzt ist BEVOR start_auto_hunt feuert
    (sonst koennte der initiale Polling-Tick mit Default 0.0 sofort die
    5-Min-Schicht ausloesen)."""
    from ui import main_window as mw_mod

    obj = MagicMock()
    obj._auto_hunt = MagicMock(active=False)
    obj._auto_hunt_last_mouse_t = 0.0
    obj._omni_cq = MagicMock()
    obj._omni_cq.is_active.return_value = False
    obj.settings.band = "20m"
    obj._swr_blocked_bands = set()
    obj._on_auto_hunt_polling_tick = MagicMock()
    obj._auto_hunt_polling_timer = MagicMock()

    captured = {}

    def capture_when_started(duration):
        captured["last_t_at_start"] = obj._auto_hunt_last_mouse_t

    obj._auto_hunt.start_auto_hunt = MagicMock(side_effect=capture_when_started)

    fake_t = 1500.0
    with patch.object(mw_mod, "time") as time_mock:
        time_mock.monotonic.return_value = fake_t
        mw_mod.MainWindow._on_btn_auto_hunt_toggled(obj, True)

    assert captured["last_t_at_start"] == fake_t, \
        "Anker muss vor start_auto_hunt gesetzt sein (sonst Default 0.0)"
