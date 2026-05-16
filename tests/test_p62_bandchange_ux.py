"""P62 (v0.97.35): Bandwechsel→Gain-Messung UX-Übergang.

Mike-Field-Test P60-F6: bei Bandwechsel auf NEUES Band ohne Preset
startet Gain-Mess-TUNE (10W) DIREKT nach TX-Stop. Visuell wirkt das
wie „80W → 10W" statt „TX aus → neue Messung".

Fix: 1s Pause zwischen TX-Stop und Tune-On. Lock greift sofort
(sperrt UI). Statusbar zeigt Hinweis. Nach 1000ms eigentliche Pipeline.

Pause greift NUR im stale/missing-Gain-Branch von
`_check_diversity_preset` (Bandwechsel-Trigger). KALIBRIEREN-Button
(`_handle_dx_tuning`) ist User-Action und ruft `_start_dx_tuning`
weiterhin direkt ohne Pause.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from unittest.mock import MagicMock, patch

import pytest


def _read_mw_radio() -> str:
    p = Path(__file__).parent.parent / "ui" / "mw_radio.py"
    return p.read_text()


def _get_method_source(method_name: str) -> str:
    """Extrahiert den Source-Body einer Methode aus mw_radio.py per regex."""
    text = _read_mw_radio()
    # Match `def method_name(...):` bis zum nächsten `def ` oder Datei-Ende
    pattern = rf"    def {method_name}\([^)]*\)[^\n]*:.*?(?=\n    def |\nclass |\Z)"
    m = re.search(pattern, text, flags=re.DOTALL)
    if not m:
        raise AssertionError(f"Methode {method_name} nicht gefunden")
    return m.group(0)


# ── T1 — QTimer.singleShot mit 1000ms in _check_diversity_preset ───────────

def test_t1_check_diversity_preset_hat_qtimer_1s():
    """T1: `_check_diversity_preset` ruft `QTimer.singleShot(1000, ...)`
    im stale/missing-Gain-Branch."""
    src = _get_method_source("_check_diversity_preset")
    assert "QTimer.singleShot" in src, "P62: QTimer.singleShot fehlt"
    assert "1000" in src, "P62: 1000ms Pause-Zeit fehlt"


# ── T2 — Lock VOR QTimer ──────────────────────────────────────────────────

def test_t2_lock_vor_qtimer_in_check_diversity_preset():
    """T2: `_set_gain_measure_lock(True)` kommt VOR `QTimer.singleShot`
    in `_check_diversity_preset` — Race-Schutz."""
    src = _get_method_source("_check_diversity_preset")
    idx_lock = src.find("_set_gain_measure_lock(True)")
    idx_timer = src.find("QTimer.singleShot")
    assert idx_lock > 0, "P62: Lock-Aufruf fehlt"
    assert idx_timer > 0, "P62: QTimer-Aufruf fehlt"
    assert idx_lock < idx_timer, (
        "P62: _set_gain_measure_lock(True) MUSS vor QTimer.singleShot stehen"
    )


# ── T3 — Statusbar-Hinweis-Text vorhanden ─────────────────────────────────

def test_t3_statusbar_hinweis_in_check_diversity_preset():
    """T3: Mike sieht „TX gestoppt — Gain-Messung startet in 1s ..."
    in der Statusbar während der 1s Pause."""
    src = _get_method_source("_check_diversity_preset")
    assert "TX gestoppt" in src, "P62: Statusbar-Hinweis-Text fehlt"
    assert "Gain-Messung startet" in src, "P62: Hinweis-Phrase fehlt"


# ── T4 — Gain-fresh-Branch unverändert (kein QTimer) ──────────────────────

def test_t4_gain_fresh_branch_ohne_qtimer():
    """T4: Wenn Gain fresh ist (Cache-Hit), läuft `_enable_diversity`
    direkt — KEINE Pause. Pause ist nur für stale/missing-Branch."""
    src = _get_method_source("_check_diversity_preset")
    # Den fresh-Branch isolieren (vor "Gain stale oder missing"-Kommentar)
    stale_marker = "Gain stale oder missing"
    idx_stale = src.find(stale_marker)
    assert idx_stale > 0, "P62: stale/missing-Branch-Marker fehlt"
    fresh_part = src[:idx_stale]
    assert "QTimer.singleShot" not in fresh_part, (
        "P62: Gain-fresh-Branch darf KEIN QTimer haben — direkter "
        "_enable_diversity-Aufruf"
    )
    assert "_enable_diversity" in fresh_part, (
        "P62: Gain-fresh-Branch ruft _enable_diversity"
    )


# ── T5 — KALIBRIEREN-Pfad unverändert (kein QTimer für Tune-Pause) ────────

def test_t5_handle_dx_tuning_kein_qtimer_pause():
    """T5: `_handle_dx_tuning` (KALIBRIEREN-Button) ruft `_start_dx_tuning`
    direkt OHNE 1s-Pause. User-Action, keine Verwirrung möglich."""
    src = _get_method_source("_handle_dx_tuning")
    # KALIBRIEREN darf KEIN QTimer.singleShot(1000, ...) haben
    # (verallgemeinert: kein 1000ms-Pattern)
    has_qtimer = "QTimer.singleShot" in src
    if has_qtimer:
        # Falls QTimer aus anderem Grund — pruefe explizit kein 1000ms
        assert "1000" not in src, (
            "P62: KALIBRIEREN-Pfad darf KEIN 1000ms-QTimer-Pattern haben"
        )
    # Direkter _start_dx_tuning-Aufruf muss da sein
    assert "_start_dx_tuning" in src, (
        "P62: _handle_dx_tuning muss _start_dx_tuning direkt aufrufen"
    )


# ── T6 — Funktional: monkeypatch QTimer.singleShot, prüfe Aufruf ──────────

def test_t6_qtimer_singleshot_aufruf_funktional(monkeypatch):
    """T6: Funktional — `_check_diversity_preset` ruft tatsächlich
    `QTimer.singleShot(1000, callable)`. Nicht Source-Level sondern
    Live-Verhalten via monkeypatch (ohne Qt-Event-Loop)."""
    import ui.mw_radio as mwr

    # Mock-Aufzeichnung
    calls = []

    def fake_singleshot(msec, callback):
        calls.append((msec, callback))
        # NICHT ausfuehren — wir wollen nur den Aufruf verifizieren

    monkeypatch.setattr(
        "PySide6.QtCore.QTimer.singleShot", fake_singleshot
    )

    # Minimaler RadioMixin-Stub mit ausreichend State
    obj = MagicMock()
    obj.radio = MagicMock()
    obj.radio.ip = "192.168.1.100"  # connected
    obj._assess_gain = MagicMock(return_value="stale")  # erzwinge stale-Pfad
    obj._diversity_ctrl = MagicMock()
    obj._set_gain_measure_lock = MagicMock()
    obj._update_statusbar = MagicMock()
    obj.statusBar = MagicMock()
    obj.statusBar.return_value.showMessage = MagicMock()
    obj._pending_dx_diversity = False
    obj._pending_diversity_scoring = None

    # _check_diversity_preset über Klasse aufrufen (gebundene Methode)
    mwr.RadioMixin._check_diversity_preset(obj, "20m", "FT8", "normal")

    assert len(calls) == 1, f"P62: erwartete genau 1 QTimer-Aufruf, got {len(calls)}"
    msec, cb = calls[0]
    assert msec == 1000, f"P62: erwartete 1000ms Pause, got {msec}"
    assert callable(cb), "P62: QTimer-Callback muss callable sein"
    # Lock-Aufruf vor QTimer
    obj._set_gain_measure_lock.assert_called_with(True)
    # Statusbar-Message gesetzt
    obj.statusBar.return_value.showMessage.assert_called_once()
    msg_args = obj.statusBar.return_value.showMessage.call_args[0]
    assert "TX gestoppt" in msg_args[0]
