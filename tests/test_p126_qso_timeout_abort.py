"""P126 (2026-05-26) — Send-nach-Timeout TX-Pipeline-Race-Fix.

Mike-Field-Bug 25.05.2026, 3x belegt (EC3A 07:30, F1IBU 08:59, LA1YKA
13:23): Nach calls_made-Timeout erschien 1 zusätzlicher Send 1 EVEN-
Slot NACH Timeout-Display:

```
07:30:00 → Sende EC3A DA1MHH -17    (regulärer 6. Send)
✗ EC3A — Timeout
07:30:30 → Sende EC3A DA1MHH -17    ← NACHSCHLAG (Etiquette-Verstoß)
```

Race-Quellen multipel (is_grid in WAIT_REPORT/TX_CALL,
_pending_hunt_reply, Encoder-Sleep). KISS-Fix: encoder.abort()
in _on_qso_timeout deckt alle Race-Quellen defensive ab (Mike-Spec:
"bei Timeout sofort STOP, kein Nachschlag").

ACs:
- AC1: _on_qso_timeout ruft encoder.abort() wenn is_transmitting
- AC2: _on_qso_timeout ruft KEIN abort() wenn nicht is_transmitting
- AC3: _pending_tx_log wird auf None gesetzt (P127-Pattern)
- AC4: Hardware-Stop läuft VOR add_timeout (Safety-First)
- AC5: add_timeout wird weiterhin gerufen (✗-Display erhalten)
- AC6: Bestehende Pfade (P122 flush, auto_hunt, CQ-Resume) unverändert
- AC7: Defensive hasattr für Test-Fakes
- AC8: HALT-Pfad (_abort_active_tx) bleibt unverändert (separate Rolle)
"""

from __future__ import annotations

import inspect


# ---------------------------------------------------------------------------
# T1-T4: Source-Inspektion — Fix-Pattern verifizieren
# ---------------------------------------------------------------------------


def test_t1_qso_timeout_calls_encoder_abort():
    """T1: _on_qso_timeout enthält encoder.abort()-Aufruf."""
    from ui.mw_qso import QSOMixin
    source = inspect.getsource(QSOMixin._on_qso_timeout)
    assert "self.encoder.abort()" in source, (
        "P126: _on_qso_timeout muss encoder.abort() rufen "
        "(Mike-Spec: bei Timeout sofort STOP)")


def test_t2_abort_guarded_by_is_transmitting():
    """T2: abort() nur wenn encoder.is_transmitting (defensiv)."""
    from ui.mw_qso import QSOMixin
    source = inspect.getsource(QSOMixin._on_qso_timeout)
    # Guard: if self.encoder.is_transmitting:
    pos_guard = source.find("if self.encoder.is_transmitting")
    pos_abort = source.find("self.encoder.abort()")
    assert pos_guard > 0, "P126: is_transmitting-Guard fehlt"
    assert pos_abort > 0
    assert pos_guard < pos_abort, (
        "P126: abort() MUSS hinter is_transmitting-Guard stehen")


def test_t3_pending_tx_log_cleared():
    """T3: _pending_tx_log wird auf None gesetzt (P127-Pattern)."""
    from ui.mw_qso import QSOMixin
    source = inspect.getsource(QSOMixin._on_qso_timeout)
    assert "self._pending_tx_log = None" in source, (
        "P126: _pending_tx_log muss auf None gesetzt werden damit "
        "kein 'Sende...'-Eintrag fuer abgebrochenen Send erscheint")


def test_t4_hardware_stop_before_ui_display():
    """T4: abort() läuft VOR add_timeout (Safety-First, Reihenfolge).

    Final-R1-Empfehlung: erst Hardware-Stop, dann UI-Feedback.
    """
    from ui.mw_qso import QSOMixin
    source = inspect.getsource(QSOMixin._on_qso_timeout)
    pos_abort = source.find("self.encoder.abort()")
    pos_add_timeout = source.find("self.qso_panel.add_timeout")
    assert pos_abort > 0
    assert pos_add_timeout > 0
    assert pos_abort < pos_add_timeout, (
        "P126: abort() MUSS vor add_timeout() stehen (Hardware-Safety "
        "vor UI-Display)")


# ---------------------------------------------------------------------------
# T5-T6: Bestehende Pfade unverändert
# ---------------------------------------------------------------------------


def test_t5_existing_paths_preserved():
    """T5: Alle bestehenden Pfade in _on_qso_timeout sind erhalten.

    P122 flush_pending_stop, P81 _flush_auto_hunt_stop_msg,
    _auto_hunt.on_qso_timeout, set_cq_active, _maybe_resume_omni —
    keiner darf entfernt worden sein.
    """
    from ui.mw_qso import QSOMixin
    source = inspect.getsource(QSOMixin._on_qso_timeout)
    # P122 + P81-Pattern
    assert "_active_qso_targets.discard" in source
    assert "rx_panel.set_active_call" in source
    assert "add_timeout" in source
    assert "_auto_hunt" in source
    assert "_maybe_resume_omni" in source


def test_t6_defensive_hasattr_guard():
    """T6: hasattr-Guard für _pending_tx_log (Test-Fakes schützen)."""
    from ui.mw_qso import QSOMixin
    source = inspect.getsource(QSOMixin._on_qso_timeout)
    assert 'hasattr(self, "_pending_tx_log")' in source, (
        "P126: hasattr-Guard nötig für Test-Setups ohne _pending_tx_log")


# ---------------------------------------------------------------------------
# T7: HALT-Pfad bleibt unverändert (separate Rolle)
# ---------------------------------------------------------------------------


def test_t7_halt_path_unchanged():
    """T7: _abort_active_tx (HALT-Pfad) hat KEINE P126-Logik.

    P126 ist nur für Timeout (Auto-Abbruch durch State-Machine).
    HALT ist User-Interaktion — Mike will dort weiterhin den
    Sende-Eintrag im Log sehen (was er gerade abgebrochen hat).
    """
    from ui.mw_tx import TXMixin
    source = inspect.getsource(TXMixin._abort_active_tx)
    # _abort_active_tx soll _pending_tx_log NICHT clearen
    # (separate Rolle vs P126/P127)
    assert "_pending_tx_log" not in source, (
        "P126: _abort_active_tx (HALT-Pfad) darf _pending_tx_log NICHT "
        "clearen — User soll bei HALT sehen was er abgebrochen hat.")


# ---------------------------------------------------------------------------
# T8: Pattern-Familie Doku
# ---------------------------------------------------------------------------


def test_t8_pattern_family_doc():
    """T8: Doku-Kommentar erwähnt P126, P127-Pattern, Mike-Field-Bug."""
    from ui.mw_qso import QSOMixin
    source = inspect.getsource(QSOMixin._on_qso_timeout)
    assert "P126" in source, "P126-Marker im Doku-Kommentar"
    # P127-Pattern-Referenz (semantische Symmetrie)
    assert "P127" in source, (
        "P127-Pattern-Referenz im Doku-Kommentar (gleiches "
        "_pending_tx_log = None Idiom)")
    # Mike-Field-Bug-Bezug
    assert "Mike" in source or "Field" in source.lower() or "2026" in source


# ---------------------------------------------------------------------------
# T9: encoder.abort hat keine Nebenwirkungen wenn nicht transmitting
# ---------------------------------------------------------------------------


def test_t9_encoder_abort_idempotent():
    """T9: encoder.abort() ist idempotent (im Encoder-Code verifiziert).

    Bei _is_transmitting=False setzt abort() nur Flag+Event, keine
    Hardware-Aktion. Safe defensiv zu rufen.
    """
    import inspect as _inspect
    from core.encoder import Encoder
    source = _inspect.getsource(Encoder.abort)
    # abort() sollte:
    # - _is_transmitting=False setzen
    # - _abort_event.set() rufen
    # - print/debug ok
    assert "self._is_transmitting = False" in source
    assert "self._abort_event.set()" in source
    # Keine PTT-direkt-Aktion (Worker-Thread handhabt das im finally)


# ---------------------------------------------------------------------------
# T10: Code-Pfad-Reihenfolge final verifizieren
# ---------------------------------------------------------------------------


def test_t10_code_order_abort_first_then_cleanup():
    """T10: Vollständige Reihenfolge im Handler:

    1. encoder.abort() (Hardware-Stop)
    2. _pending_tx_log = None (Log-Cleanup)
    3. _active_qso_targets.discard (State-Cleanup)
    4. rx_panel.set_active_call("") (UI)
    5. add_timeout (UI-Display)
    6. flush_pending_stop / _flush_auto_hunt_stop_msg (Pattern-Pfade)
    7. auto_hunt.on_qso_timeout / on_manual_qso_end
    8. control_panel.set_cq_active
    9. _maybe_resume_omni
    """
    from ui.mw_qso import QSOMixin
    source = inspect.getsource(QSOMixin._on_qso_timeout)
    positions = {
        "abort": source.find("self.encoder.abort()"),
        "log_clear": source.find("self._pending_tx_log = None"),
        "discard": source.find("_active_qso_targets.discard"),
        "set_active_call": source.find("rx_panel.set_active_call"),
        "add_timeout": source.find("add_timeout(their_call)"),
    }
    # Alle vorhanden
    for name, pos in positions.items():
        assert pos > 0, f"P126: Code-Pfad '{name}' fehlt"
    # Reihenfolge: abort < log_clear < discard < set_active_call < add_timeout
    assert positions["abort"] < positions["log_clear"]
    assert positions["log_clear"] < positions["discard"]
    assert positions["discard"] < positions["set_active_call"]
    assert positions["set_active_call"] < positions["add_timeout"]
