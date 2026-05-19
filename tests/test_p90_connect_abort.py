"""P90 — Connect-Worker hart abbrechen bei „ohne Radio weiter" (v0.97.60)

Mike-Field-Test 19.05.2026 nach v0.97.59-Start: Trotz „ohne Radio weiter"
hat der FlexRadio-Worker die komplette Connect-Sequenz durchlaufen
(Discovery → Phase 1 SmartSDR-Disconnect → Phase 2 TCP-Connect → Meter
Learning → Panadapter + Slice → TX-Config). P82-Slot-Guards greifen
zwar danach (verhindern Hardware-Setup), aber die Sockets/Slice
bleiben kurz „eingerichtet" — Risiko fuer Code-Pfade die auf das
Radio zugreifen.

Fix P90: `_abort_connect`-Flag analog `_abort_reconnect` in
`radio/flexradio.py` mit Setter `abort_connect()`. Check-Punkte in
`auto_connect()` (5x) + `connect()` (4x). Bei Abort: `disconnect()`
+ `return False`. `mw_radio._start_radio` Cleanup-Block ruft
`abort_connect()` VOR `abort_reconnect()` VOR `disconnect()` VOR
`thread.join(timeout=2.0)`.

Tests T1-T8 (alle ohne Radio):
- T1: `_abort_connect`-Flag im __init__ False
- T2: Setter `abort_connect()` setzt Flag auf True
- T3: `auto_connect()` reset Flag am Anfang (frischer Start)
- T4: `auto_connect()` bricht nach 1. Check sofort ab wenn Flag gesetzt
- T5: `connect()` Abort-Check nach SmartSDR-Disconnect ruft disconnect+return
- T6: `_connect_thread` ist Instance-Var (P90 join-fähig)
- T7: Cleanup-Reihenfolge im was_user_cancelled-Block korrekt
- T8: APP_VERSION-Bump auf 0.97.60+
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ── T1 — Flag im __init__ False ───────────────────────────────────────


def test_t1_abort_connect_default_false():
    """`_abort_connect` muss im __init__ False sein."""
    from radio.flexradio import FlexRadio
    radio = FlexRadio()
    assert radio._abort_connect is False


# ── T2 — Setter setzt Flag ────────────────────────────────────────────


def test_t2_abort_connect_setter():
    """`abort_connect()` setzt `_abort_connect` auf True."""
    from radio.flexradio import FlexRadio
    radio = FlexRadio()
    assert radio._abort_connect is False
    radio.abort_connect()
    assert radio._abort_connect is True


# ── T3 — auto_connect reset Flag am Anfang ────────────────────────────


def test_t3_auto_connect_resets_flag_at_start():
    """`auto_connect()` muss `_abort_connect = False` setzen damit
    alter Abort-Wunsch nicht den naechsten Start blockiert.
    """
    from radio.flexradio import FlexRadio
    radio = FlexRadio()
    radio._abort_connect = True  # Simuliere alten Abort-Wunsch
    # Patch discover + connect damit kein echtes Radio noetig
    with patch.object(radio, "discover", return_value=[]), \
         patch.object(radio, "disconnect"):
        radio.auto_connect(max_retries=1, retry_delay=0.0)
    # Flag MUSS reseted worden sein (Mike will frischen Start)
    # Hinweis: max_retries=1 ohne IP → keine Connection → Flag bleibt False
    assert radio._abort_connect is False, \
        "auto_connect muss _abort_connect am Anfang resetten"


# ── T4 — auto_connect bricht sofort ab wenn Flag gesetzt wird ─────────


def test_t4_auto_connect_aborts_on_flag():
    """Wenn `_abort_connect` mitten in auto_connect gesetzt wird,
    muss die naechste Iteration ohne Discovery/Connect aussteigen.
    """
    from radio.flexradio import FlexRadio
    radio = FlexRadio()

    def fake_on_attempt(attempt, max_retries):
        # Simuliere: User klickt waehrend des Callbacks „ohne Radio weiter"
        radio.abort_connect()

    with patch.object(radio, "discover") as m_discover, \
         patch.object(radio, "connect") as m_connect, \
         patch.object(radio, "disconnect") as m_disconnect:
        result = radio.auto_connect(
            max_retries=5, retry_delay=0.0, on_attempt=fake_on_attempt
        )
    assert result is False
    # discover/connect duerfen NICHT mehr aufgerufen worden sein
    # (Check-Punkt nach Callback greift)
    m_discover.assert_not_called()
    m_connect.assert_not_called()


# ── T5 — connect() Abort-Check nach Phase 1 ──────────────────────────


def test_t5_connect_aborts_after_smartsdr_disconnect():
    """`connect()` muss nach `_disconnect_smartsdr()` `_abort_connect`
    pruefen, `disconnect()` aufrufen und False returnen.
    """
    from radio.flexradio import FlexRadio
    radio = FlexRadio(ip="192.168.1.99")  # Fake-IP

    def set_abort_during_phase1():
        # Simuliere: User klickt wahrend Phase 1
        radio._abort_connect = True

    # _disconnect_smartsdr mocken, dabei Flag setzen
    with patch.object(radio, "_disconnect_smartsdr",
                      side_effect=set_abort_during_phase1), \
         patch.object(radio, "disconnect") as m_disconnect:
        result = radio.connect()

    assert result is False, "connect() muss bei Abort False returnen"
    m_disconnect.assert_called(), \
        "connect() muss disconnect() bei Abort aufrufen"


# ── T6 — _connect_thread als Instance-Var ─────────────────────────────


def test_t6_connect_thread_instance_var():
    """P90: `_connect_thread` MUSS als Instance-Var gesetzt werden,
    damit der Cleanup-Block sein Ende abwarten kann (join).
    """
    import inspect
    from ui import mw_radio
    src = inspect.getsource(mw_radio.RadioMixin._start_radio)
    assert "self._connect_thread = threading.Thread(" in src, \
        "P90: Worker-Thread MUSS als self._connect_thread gespeichert sein"
    assert "self._connect_thread.start()" in src, \
        "P90: self._connect_thread.start() muss aufgerufen werden"


# ── T7 — Cleanup-Reihenfolge im Cancel-Block korrekt ──────────────────


def test_t7_cleanup_order_correct():
    """P90 Cleanup im was_user_cancelled-Block: abort_connect VOR
    abort_reconnect VOR disconnect VOR thread.join.
    """
    import inspect
    from ui import mw_radio
    src = inspect.getsource(mw_radio.RadioMixin._start_radio)

    # Reihenfolge im Source-Code pruefen via Position
    pos_abort_connect = src.find("self.radio.abort_connect()")
    pos_abort_reconnect = src.find("self.radio.abort_reconnect()")
    pos_disconnect = src.find("self.radio.disconnect()")
    pos_join = src.find(".join(timeout=2.0)")

    assert pos_abort_connect > 0, "abort_connect-Aufruf muss existieren"
    assert pos_abort_reconnect > 0, "abort_reconnect-Aufruf muss existieren"
    assert pos_disconnect > 0, "disconnect-Aufruf muss existieren"
    assert pos_join > 0, "thread.join muss existieren"

    assert pos_abort_connect < pos_abort_reconnect, \
        "P90: abort_connect MUSS vor abort_reconnect kommen"
    assert pos_abort_reconnect < pos_disconnect, \
        "P90: abort_reconnect MUSS vor disconnect kommen"
    assert pos_disconnect < pos_join, \
        "P90: disconnect MUSS vor thread.join kommen"


# ── T8 — APP_VERSION-Bump ─────────────────────────────────────────────


def test_t8_app_version_bump():
    """APP_VERSION muss >= 0.97.60 sein (P90)."""
    import main
    assert main.APP_VERSION >= "0.97.60", \
        f"APP_VERSION ist {main.APP_VERSION}, erwartet >= 0.97.60"
