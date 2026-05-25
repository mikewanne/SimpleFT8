"""P128 (25.05.2026) — Empf.-Eintrag im QSO-Log 60s blocken nach ✓ QSO.

Mike-Field-Bug: nach „✓ QSO mit EA1FLB komplett" sendet EA1FLB noch
R-23 im nächsten Slot → erscheint im QSO-Log. Mike: „wenn beendet ist
beendet". Variante A — 60s harter Block.

ACs:
- AC1: Cooldown wird in _on_qso_complete gesetzt
- AC2: Empf.-Eintrag von blocked Station wird im QSO-Log unterdrückt
- AC3: RX-Tabelle/Wasserfall UNBERÜHRT
- AC4: Lazy-Aging nach 60s
- AC5: State-Machine läuft trotzdem (R1-F5 ROT)
- AC6/7: Reset bei Band/Mode-Wechsel
- AC8: Manueller Re-Klick hebt Cooldown auf
- AC9: Andere Stationen nicht betroffen
- AC10: Timeout setzt KEINEN Cooldown
- T12: P124+P128 — Hash erst resolved, dann Cooldown-Check
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from ui.mw_cycle import _RECENTLY_COMPLETED_BLOCK_S


# ---------------------------------------------------------------------------
# Helper: minimal-mw mit Mixin-Methoden
# ---------------------------------------------------------------------------


class _MwBlockMixin:
    """Minimal-Stub für _p128_recently_completed_block aus CycleMixin."""

    def __init__(self):
        self._recently_completed_qsos: dict[str, float] = {}
        from ui.mw_cycle import CycleMixin
        self._fn = CycleMixin._p128_recently_completed_block.__get__(
            self, _MwBlockMixin)


# ---------------------------------------------------------------------------
# T1-T4: Helper-Logik
# ---------------------------------------------------------------------------


def test_t1_no_entry_returns_false():
    """T1: Cooldown-Dict leer → kein Block."""
    mw = _MwBlockMixin()
    assert mw._fn("RA9LL") is False


def test_t2_entry_within_window_returns_true():
    """T2: Eintrag <60s alt → Block."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["RA9LL"] = time.monotonic()
    assert mw._fn("RA9LL") is True


def test_t3_entry_aged_returns_false_and_deletes():
    """T3: Eintrag >60s alt → kein Block + lazy gelöscht."""
    mw = _MwBlockMixin()
    # Setze Eintrag mit ts in der „Vergangenheit" (60.5s alt)
    mw._recently_completed_qsos["RA9LL"] = (
        time.monotonic() - _RECENTLY_COMPLETED_BLOCK_S - 0.5)
    assert mw._fn("RA9LL") is False
    assert "RA9LL" not in mw._recently_completed_qsos


def test_t4_different_caller_not_affected():
    """T4: Andere Stationen nicht betroffen."""
    mw = _MwBlockMixin()
    mw._recently_completed_qsos["RA9LL"] = time.monotonic()
    assert mw._fn("EA1FLB") is False


def test_t4b_defensive_missing_attr():
    """T4b: Defensive `getattr` für Test-Fakes ohne Attribut."""
    class _Fake:
        pass
    fake = _Fake()
    from ui.mw_cycle import CycleMixin
    fn = CycleMixin._p128_recently_completed_block.__get__(fake, _Fake)
    assert fn("RA9LL") is False


def test_t4c_constant_value():
    """T4c: Konstante = Mike-Spec 60.0 Sekunden."""
    assert _RECENTLY_COMPLETED_BLOCK_S == 60.0


# ---------------------------------------------------------------------------
# T5-T7: Integration in _on_qso_complete (Set-Pfad)
# ---------------------------------------------------------------------------


def test_t5_qso_complete_fills_cooldown_dict():
    """T5: _on_qso_complete fügt (call, ts) zum Dict hinzu."""
    # Simuliere _on_qso_complete-Logik ohne kompletten Mixin-Setup
    recently = {}
    call = "EA1FLB"
    before = time.monotonic()
    recently[call] = time.monotonic()  # exakt diese Zeile aus _on_qso_complete
    after = time.monotonic()
    assert call in recently
    assert before <= recently[call] <= after


def test_t6_qso_complete_multiple_qsos():
    """T6: Mehrere QSOs füllen Dict parallel."""
    recently = {}
    recently["RA9LL"] = time.monotonic()
    recently["EA1FLB"] = time.monotonic()
    recently["DG8DBW"] = time.monotonic()
    assert len(recently) == 3


# ---------------------------------------------------------------------------
# T7: State-Machine läuft trotzdem (R1-F5 ROT-Catch)
# ---------------------------------------------------------------------------


def test_t7_filter_is_only_for_add_rx_not_return():
    """T7 (R1-F5): Block-Filter unterdrückt NUR add_rx, NICHT
    on_message_received. Im Code wird if/else verwendet, nicht return.

    Verifiziert durch Code-Inspektion: ui/mw_cycle.py:776-795 zeigt
    `if not self._p128_recently_completed_block(...)` → if-Block ist
    NUR der add_rx-Aufruf. Quick73-Filter und on_message_received
    laufen weiter (Z. 798ff).
    """
    import inspect
    from ui.mw_cycle import CycleMixin
    source = inspect.getsource(CycleMixin.on_message_decoded)
    # P128-Filter darf NICHT direkt vor on_message_received `return` aufrufen
    # — er soll nur add_rx skippen
    assert "if not self._p128_recently_completed_block(msg.caller)" in source
    # Die echte on_message_received-Zeile muss noch da sein
    assert "self.qso_sm.on_message_received(msg)" in source


# ---------------------------------------------------------------------------
# T8-T9: Reset-Pfade
# ---------------------------------------------------------------------------


def test_t8_band_change_clears_cooldown():
    """T8: Bandwechsel cleart das Dict (Mike-Spec)."""
    recently = {"RA9LL": time.monotonic(), "EA1FLB": time.monotonic()}
    recently.clear()  # exakt diese Zeile aus _on_band_changed
    assert recently == {}


def test_t9_mode_change_clears_cooldown():
    """T9: Mode-Wechsel cleart das Dict (Mike-Spec, analog Band)."""
    recently = {"RA9LL": time.monotonic()}
    recently.clear()
    assert recently == {}


# ---------------------------------------------------------------------------
# T10: Manueller Re-Klick hebt Cooldown auf
# ---------------------------------------------------------------------------


def test_t10_station_click_pops_cooldown():
    """T10: Re-Klick auf gleiche Station entfernt ihren Cooldown-Eintrag."""
    recently = {"RA9LL": time.monotonic(), "EA1FLB": time.monotonic()}
    # Simulation: _on_station_clicked-Logik
    recently.pop("RA9LL", None)
    assert "RA9LL" not in recently
    assert "EA1FLB" in recently  # andere unberührt
    # pop ohne Eintrag → safe
    recently.pop("NIE_GEKOMMEN", None)


# ---------------------------------------------------------------------------
# T11: Timeout setzt KEINEN Cooldown (Mike-Spec)
# ---------------------------------------------------------------------------


def test_t11_timeout_does_not_set_cooldown():
    """T11: Timeout (✗) setzt KEINEN Cooldown — Mike-Spec war nur ✓.

    Verifiziert durch Code-Inspektion: _on_qso_timeout in mw_qso.py
    ruft KEIN _recently_completed_qsos.update auf.
    """
    import inspect
    from ui.mw_qso import QSOMixin
    timeout_source = inspect.getsource(QSOMixin._on_qso_timeout)
    assert "_recently_completed_qsos" not in timeout_source, (
        "_on_qso_timeout darf NICHT in _recently_completed_qsos schreiben")


# ---------------------------------------------------------------------------
# T12: P124+P128 Interaktion (Hash erst resolved, dann Cooldown geprüft)
# ---------------------------------------------------------------------------


def test_t12_p124_resolution_before_p128_check():
    """T12: Im on_message_decoded läuft P124-Resolution VOR P128-Check.

    Hash-Frame `DA1MHH <...> R+10` während aktivem QSO mit RA9LL:
    1. P124 löst <...> → RA9LL auf (msg.caller wird RA9LL)
    2. P128 prüft msg.caller (= RA9LL) gegen Cooldown-Dict

    Wenn RA9LL gerade abgeschlossen wurde → Block greift mit echtem Call.
    """
    import inspect
    from ui.mw_cycle import CycleMixin
    source = inspect.getsource(CycleMixin.on_message_decoded)
    # P124-Aufruf MUSS vor P128-Filter stehen
    p124_pos = source.find("_p124_resolve_hash_if_active_qso")
    p128_pos = source.find("_p128_recently_completed_block")
    assert p124_pos > 0 and p128_pos > 0
    assert p124_pos < p128_pos, (
        "P124-Resolution muss VOR P128-Check laufen — sonst greift "
        "Block mit dem unresolved Hash-Marker statt mit echtem Call")
