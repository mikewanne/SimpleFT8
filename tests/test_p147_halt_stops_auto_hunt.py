"""P147 (27.05.2026) - HALT-Button stoppt Auto-Hunt SOFORT.

Mike-Field-Bug 27.05. 04:42-04:43: HALT-Button hat NUR die aktuelle
Station gestoppt, Auto-Hunt-Session lief weiter und picked nächste
Stationen (YO4NT, TA3ZZ, R9MW). Mike-Spec: "halt ist aber notknopf
und müsste wie der name sagt alles anhalten" -- Hardware-Sicherheits-
Notbremse, MUSS zuverlässig stoppen.

Root Cause: ui/mw_qso.py:_on_cancel rief on_manual_qso_end() -- das
setzt nur _manual_override=False, _active bleibt True -> select_next
läuft weiter.

Fix: stop_auto_hunt("manual_halt") aufrufen (SOFORT-Reason seit P122).

Diese Tests prüfen:
- T1: Source-Inspektion _on_cancel ruft stop_auto_hunt("manual_halt")
- T2: Funktional: AutoHunt aktiv, HALT -> active=False
- T3: Regression: nach HALT + Re-Start funktioniert Auto-Hunt
- T4: on_manual_qso_end bleibt für QSO-Confirmed/Timeout-Pfade
- T5: stop_auto_hunt mit "manual_halt" cleart _cooldown
"""

from __future__ import annotations

from pathlib import Path


MW_QSO_SRC = (Path(__file__).resolve().parent.parent
              / "ui" / "mw_qso.py").read_text()
AUTO_HUNT_SRC = (Path(__file__).resolve().parent.parent
                 / "core" / "auto_hunt.py").read_text()


# ---------------------------------------------------------------------------
# T1: Source-Inspektion - _on_cancel ruft den richtigen Stop-Pfad
# ---------------------------------------------------------------------------


def test_t1_on_cancel_calls_stop_auto_hunt_with_manual_halt():
    """T1: _on_cancel (HALT) ruft stop_auto_hunt('manual_halt'),
    NICHT mehr on_manual_qso_end() als echten Aufruf.

    Kommentar-Erwähnung von on_manual_qso_end() ist OK (P147-Doku),
    aber kein `self._auto_hunt.on_manual_qso_end()`-Aufruf mehr.
    """
    import re
    m = re.search(
        r"def _execute_full_halt\(self\).*?(?=\n    @?Slot|\n    def )",
        MW_QSO_SRC, re.S)
    assert m is not None, "_on_cancel nicht gefunden"
    body = m.group(0)
    assert 'stop_auto_hunt("manual_halt")' in body, (
        "P147: _on_cancel MUSS stop_auto_hunt('manual_halt') rufen "
        "-- nicht on_manual_qso_end() (Mike-Field-Bug 27.05.).")
    # Alter falscher Aufruf darf NICHT mehr als echter Call dastehen
    # (Kommentare die das Wort enthalten OK -- Erklärung warum es weg ist)
    assert "self._auto_hunt.on_manual_qso_end()" not in body, (
        "P147: self._auto_hunt.on_manual_qso_end() darf NICHT mehr "
        "im HALT-Pfad als Aufruf stehen -- setzt nur "
        "_manual_override, Session läuft weiter.")


# ---------------------------------------------------------------------------
# T2: Funktional - HALT setzt active=False
# ---------------------------------------------------------------------------


def test_t2_halt_stops_active_session():
    """T2: AutoHunt aktiv, stop_auto_hunt('manual_halt') -> active=False.

    Direkter Test von stop_auto_hunt mit manual_halt-Reason.
    """
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    hunt.start_auto_hunt(duration_sec=600)
    assert hunt.active is True

    hunt.stop_auto_hunt("manual_halt")
    assert hunt.active is False, (
        "P147: stop_auto_hunt('manual_halt') MUSS active=False setzen "
        "(SOFORT-Stop, kein Defer).")


# ---------------------------------------------------------------------------
# T3: Regression - nach HALT + Re-Start läuft Auto-Hunt wieder
# ---------------------------------------------------------------------------


def test_t3_restart_after_halt_works():
    """T3: Nach HALT-Stop + erneutem start_auto_hunt läuft Session
    wieder normal. start_auto_hunt setzt _manual_override automatisch
    zurück (auto_hunt.py:199) -- darum kein on_manual_qso_end nötig."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")

    # 1. Session
    hunt.start_auto_hunt(duration_sec=600)
    hunt.stop_auto_hunt("manual_halt")
    assert hunt.active is False

    # 2. Session (Re-Start nach HALT)
    hunt.start_auto_hunt(duration_sec=600)
    assert hunt.active is True
    assert hunt._manual_override is False, (
        "P147: start_auto_hunt MUSS _manual_override resetten, "
        "sonst hängt der Override aus dem alten on_manual_qso_end-"
        "Pfad fort.")


# ---------------------------------------------------------------------------
# T4: on_manual_qso_end bleibt erhalten für andere Pfade (R1-F3)
# ---------------------------------------------------------------------------


def test_t4_on_manual_qso_end_still_used_in_other_paths():
    """T4: on_manual_qso_end() wird weiterhin in _on_qso_confirmed
    und _on_qso_timeout aufgerufen -- da soll die Session weiterleben,
    nur _manual_override zurück."""
    # Funktion muss in auto_hunt.py bestehen bleiben
    assert "def on_manual_qso_end(self):" in AUTO_HUNT_SRC, (
        "on_manual_qso_end MUSS in core/auto_hunt.py bleiben "
        "(wird in _on_qso_confirmed/_on_qso_timeout genutzt).")

    # Funktion muss noch von mw_qso.py irgendwo gerufen werden
    # (NICHT im HALT-Pfad, aber in den anderen QSO-End-Pfaden)
    assert "on_manual_qso_end()" in MW_QSO_SRC, (
        "on_manual_qso_end() MUSS noch irgendwo in mw_qso.py "
        "verwendet werden (Confirmed/Timeout-Pfade). Falls leer "
        "-> Funktion ist tot und kann raus.")


# ---------------------------------------------------------------------------
# T5: manual_halt cleart Cooldown + tx_even (R1-F1 Cleanup-Logik)
# ---------------------------------------------------------------------------


def test_t5_manual_halt_clears_cooldown_and_tx_even():
    """T5: stop_auto_hunt('manual_halt') gehört zur Cleanup-Gruppe
    die _cooldown.clear() + _last_tx_even=None macht
    (auto_hunt.py:237-242 Cleanup-Logik)."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    hunt.start_auto_hunt(duration_sec=600)
    # Setze stale Werte
    hunt._cooldown["TESTCALL"] = 12345.0
    hunt._last_tx_even = True
    assert hunt._cooldown
    assert hunt._last_tx_even is True

    hunt.stop_auto_hunt("manual_halt")

    assert hunt._cooldown == {}, (
        "P147: manual_halt MUSS _cooldown clearen -- saubere "
        "Notbremse, danach Re-Start ohne Altlasten.")
    assert hunt._last_tx_even is None, (
        "P147: manual_halt MUSS _last_tx_even=None setzen.")


# ---------------------------------------------------------------------------
# T6: Defensive Idempotenz - 2. HALT-Klick schadet nicht (R1-F5)
# ---------------------------------------------------------------------------


def test_t6_double_halt_is_safe():
    """T6: User klickt HALT 2x hintereinander (Mike's Screenshot
    zeigte 3 HALT-Klicks). Beide müssen safe sein, keine Exception.

    P122 R1-F3 Idempotenz-Check: wenn nicht active UND kein Pending,
    return sofort.
    """
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    hunt.start_auto_hunt(duration_sec=600)

    hunt.stop_auto_hunt("manual_halt")
    assert hunt.active is False

    # Zweiter HALT-Klick -> kein Crash, immer noch inactive
    hunt.stop_auto_hunt("manual_halt")
    assert hunt.active is False

    # Dritter HALT-Klick -> immer noch safe
    hunt.stop_auto_hunt("manual_halt")
    assert hunt.active is False


# ---------------------------------------------------------------------------
# T7: P147-Kommentar dokumentiert Bug-Geschichte
# ---------------------------------------------------------------------------


def test_t7_p147_comment_in_on_cancel():
    """T7: _on_cancel hat P147-Kommentar mit Mike-Field-Bug-Datum
    und Erklärung warum on_manual_qso_end nicht reicht."""
    import re
    m = re.search(
        r"def _execute_full_halt\(self\).*?(?=\n    @?Slot|\n    def )",
        MW_QSO_SRC, re.S)
    body = m.group(0)
    assert "P147" in body, (
        "P147-Kommentar fehlt in _on_cancel -- Doku-Pflicht.")
    assert "manual_halt" in body, (
        "Kommentar muss manual_halt-Reason erwähnen.")
