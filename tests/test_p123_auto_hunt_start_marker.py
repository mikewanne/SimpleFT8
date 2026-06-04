"""P123 (28.05.2026, v0.98.37) — Pre-TX-Anzeige beim QSO-Start (Variante A).

Mike-Wunsch: beim QSO-Start kurz signalisieren dass ein QSO anfängt.
Befund: Von den QSO-Start-Pfaden zeigte nur der Auto-Hunt-Pfad NICHTS im
QSO-Log (nur debug_log) — manueller Klick (`mw_qso.py:266`) und CQ-Antwort
zeigen schon „Rufe/Antworte X". Mike-Wahl Variante A (von 3 vorgelegten):
kurzer Start-Marker, kein neues Format, keine persistente Anzeige.

Fix: `_run_auto_hunt` (mw_cycle.py) fügt VOR `start_qso` einen
`qso_panel.add_info(f"Rufe {call}...{antenna_label}")`-Eintrag ein —
1:1 wie der manuelle Klick-Pfad.

DeepSeek-R1 (V4-pro): PUSH FREIGEBEN, 0 Blocker. Scope bestätigt:
nur Auto-Hunt (OMNI-Listener ist deaktiviert → KISS, nicht anfassen;
CQ-Edge-Fall nicht umbauen — Mike-Wahl war „kurzer Marker").

Tests:
- T1: Source-Inspektion — add_info mit "Rufe" + _antenna_pref_label im
       _run_auto_hunt-Body, VOR start_qso
- T2: dynamisch — _run_auto_hunt ruft qso_panel.add_info mit "Rufe X..."
- T3: OMNI-Listener-Pfad bleibt bewusst ohne Marker (Doku-Anker, KISS)
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parent.parent
MW_CYCLE_SRC = (REPO / "ui" / "mw_cycle.py").read_text()


def _run_auto_hunt_body() -> str:
    m = re.search(r"def _run_auto_hunt\(self, messages.*?(?=\n    def )",
                  MW_CYCLE_SRC, re.S)
    assert m is not None, "_run_auto_hunt nicht gefunden"
    return m.group(0)


def test_t1_marker_in_source_before_start_qso():
    """T1: add_info('Rufe ...{label}') steht im _run_auto_hunt-Body VOR
    start_qso."""
    body = _run_auto_hunt_body()
    assert "qso_panel.add_info(" in body, (
        "P123: Auto-Hunt soll einen Start-Marker ins QSO-Log schreiben")
    assert "Rufe " in body, "P123: Marker-Text 'Rufe X...' (wie manueller Klick)"
    assert "_antenna_pref_label(_candidate.call)" in body, (
        "P123: Antennen-Label mitnehmen (Konsistenz zum manuellen Klick)")
    i_info = body.find("qso_panel.add_info(")
    i_start = body.find("self.qso_sm.start_qso(")
    assert i_info != -1 and i_start != -1
    assert i_info < i_start, (
        "P123: Marker VOR start_qso (wie manueller Klick)")


def test_t2_run_auto_hunt_calls_add_info():
    """T2: _run_auto_hunt ruft qso_panel.add_info mit 'Rufe <call>...'."""
    from ui.mw_cycle import CycleMixin
    from core.qso_state import QSOState

    candidate = SimpleNamespace(
        call="SX20RCK", grid="KM50", freq_hz=1234, snr=-15, tx_even=False)

    auto_hunt = MagicMock()
    auto_hunt.active = True
    auto_hunt.select_next.return_value = candidate

    qso_sm = MagicMock()
    qso_sm.state = QSOState.IDLE

    qso_panel = MagicMock()
    settings = MagicMock()
    settings.get.return_value = 5
    settings.mode = "FT8"

    fake = SimpleNamespace(
        _auto_hunt=auto_hunt,
        qso_sm=qso_sm,
        _active_qso_targets=set(),
        rx_panel=MagicMock(),
        settings=settings,
        encoder=MagicMock(),
        qso_panel=qso_panel,
        presence_can_tx=lambda: True,
        _antenna_pref_label=lambda call: " (ANT1)",
        # v0.99.7: _run_auto_hunt baut jetzt den Pool via _build_auto_hunt_pool
        # (select_next ist gemockt → Pool-Inhalt egal). Pool-Logik separat in
        # test_autohunt_pool.py; hier nur den Start-Marker pruefen.
        _build_auto_hunt_pool=lambda: [],
    )

    CycleMixin._run_auto_hunt(fake, messages=[])

    qso_panel.add_info.assert_called_once()
    info_text = qso_panel.add_info.call_args[0][0]
    assert "Rufe" in info_text
    assert "SX20RCK" in info_text
    assert "(ANT1)" in info_text
    # Marker muss VOR start_qso gefeuert haben (beide aufgerufen)
    qso_sm.start_qso.assert_called_once()


def test_t3_omni_listener_path_intentionally_no_marker():
    """T3 (Doku-Anker): Der OMNI-Listener-Pfad (mw_cycle, deaktiviertes
    Privat-Feature) bekommt bewusst KEINEN Marker (DeepSeek-R1: KISS, nicht
    anfassen). Falls OMNI je reaktiviert + ein Marker gewünscht wird, hier
    bewusst nachziehen."""
    # Der OMNI-Listener-Zweig ruft start_qso aus on_message_decoded heraus;
    # dort gibt es absichtlich keinen "Rufe"-add_info. Wir prüfen nur, dass
    # der Auto-Hunt-Marker NICHT versehentlich in den OMNI-Zweig kopiert
    # wurde (kein doppeltes "Rufe" in on_message_decoded).
    m = re.search(r"def on_message_decoded\(self.*?(?=\n    def )",
                  MW_CYCLE_SRC, re.S)
    assert m is not None
    # Im OMNI-Zweig (start_qso mit their_call=msg.caller) kein "Rufe"-Marker.
    omni_section = m.group(0)
    assert omni_section.count('add_info(\n            f"Rufe ') == 0, (
        "P123: OMNI-Listener soll bewusst KEINEN 'Rufe'-Marker haben")
