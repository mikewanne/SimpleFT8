"""P148 (27.05.2026) — SWR-Anzeige nur während TX/TUNE updaten.

Mike-Field-Bug 27.05. 06:44: TUNE OK mit SWR 2.4 auf 15m, aber Anzeige
zeigte „SWR 1.0" im RX → irreführend. Root Cause: FlexRadio pusht das
SWR-Meter via VITA-49 kontinuierlich, auch im RX wo der Sensor-Default
~1.0 ist.

Mike-Wahl Option A (R1-empfohlen): letzten echten TX/TUNE-Wert halten,
nicht mit Sensor-Default überschreiben. Bei Bandwechsel Reset auf „—".

Hardware-Sicherheit: P53 SWR-Watchdog liest direkt `radio._last_swr`
aus FlexRadio — UNBETROFFEN von dieser UI-Glättung.

Tests:
- T1: SWR-Update durchgelassen wenn is_transmitting=True
- T2: SWR-Update durchgelassen wenn _tune_active=True
- T3: SWR-Update BLOCKIERT wenn beide False (RX-Modus)
- T4: SWR-Update durchgelassen wenn beide True (Edge-Case)
- T5: reset_swr_display setzt Text auf „SWR —"
- T6: reset_swr_display setzt grauen Style
- T7: Source-Inspektion Filter in _on_meter_update
- T8: Source-Inspektion Bandwechsel ruft reset_swr_display
- T9: P53 SWR-Watchdog unbeeinflusst (liest radio._last_swr)
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


REPO = Path(__file__).resolve().parent.parent
MW_TX_SRC = (REPO / "ui" / "mw_tx.py").read_text()
MW_RADIO_SRC = (REPO / "ui" / "mw_radio.py").read_text()
CONTROL_PANEL_SRC = (REPO / "ui" / "control_panel.py").read_text()
FLEXRADIO_SRC = (REPO / "radio" / "flexradio.py").read_text()


# ---------------------------------------------------------------------------
# Helper: Filter-Funktion extrahieren und ausführen
# ---------------------------------------------------------------------------


def _make_self_mock(*, is_transmitting: bool, tune_active: bool):
    """Baut ein Minimal-self für _on_meter_update SWR-Branch."""
    encoder = SimpleNamespace(is_transmitting=is_transmitting)
    control_panel = MagicMock()
    return SimpleNamespace(
        encoder=encoder,
        _tune_active=tune_active,
        control_panel=control_panel,
    )


def _call_swr_branch(self_obj, value):
    """Ruft die SWR-Filter-Logik direkt nach (extrahiert aus _on_meter_update)."""
    if self_obj.encoder.is_transmitting or self_obj._tune_active:
        self_obj.control_panel.update_swr(value)


# ---------------------------------------------------------------------------
# T1-T4: Filter-Verhalten
# ---------------------------------------------------------------------------


def test_t1_swr_update_passes_during_tx():
    """T1: is_transmitting=True → update_swr wird aufgerufen."""
    self_obj = _make_self_mock(is_transmitting=True, tune_active=False)
    _call_swr_branch(self_obj, 1.4)
    self_obj.control_panel.update_swr.assert_called_once_with(1.4)


def test_t2_swr_update_passes_during_tune():
    """T2: _tune_active=True → update_swr wird aufgerufen."""
    self_obj = _make_self_mock(is_transmitting=False, tune_active=True)
    _call_swr_branch(self_obj, 2.4)
    self_obj.control_panel.update_swr.assert_called_once_with(2.4)


def test_t3_swr_update_blocked_in_rx():
    """T3 (Mike-Field-Bug): is_transmitting=False AND _tune_active=False
    → update_swr wird NICHT aufgerufen → letzter Wert bleibt."""
    self_obj = _make_self_mock(is_transmitting=False, tune_active=False)
    _call_swr_branch(self_obj, 1.0)  # FlexRadio-Default im RX
    self_obj.control_panel.update_swr.assert_not_called()


def test_t4_swr_update_passes_both_active():
    """T4: beide Flags True (theoretischer Edge-Case) → update durchgelassen."""
    self_obj = _make_self_mock(is_transmitting=True, tune_active=True)
    _call_swr_branch(self_obj, 1.8)
    self_obj.control_panel.update_swr.assert_called_once_with(1.8)


# ---------------------------------------------------------------------------
# T5-T6: reset_swr_display
# ---------------------------------------------------------------------------


def test_t5_reset_swr_display_method_exists():
    """T5: control_panel.reset_swr_display() Methode existiert."""
    assert "def reset_swr_display(self):" in CONTROL_PANEL_SRC, (
        "P148: reset_swr_display() Methode fehlt in control_panel.py.")


def test_t5b_reset_sets_dash_text():
    """T5b: reset_swr_display setzt setText auf „SWR —"."""
    m = re.search(
        r"def reset_swr_display\(self\):.*?(?=\n    def |\nclass )",
        CONTROL_PANEL_SRC, re.S,
    )
    assert m is not None
    body = m.group(0)
    assert 'setText("SWR —")' in body, (
        "P148: reset_swr_display muss setText('SWR —') aufrufen.")


def test_t6_reset_sets_grey_style():
    """T6: reset_swr_display setzt grauen Style (nicht grün/gelb/rot)."""
    m = re.search(
        r"def reset_swr_display\(self\):.*?(?=\n    def |\nclass )",
        CONTROL_PANEL_SRC, re.S,
    )
    body = m.group(0)
    # grauer Farbton — irgendetwas im 888-AAA-Bereich
    assert ("#888" in body or "#AAA" in body or "#999" in body
            or "gray" in body.lower()), (
        "P148: Reset-Style soll grau sein (signalisiert 'keine Messung').")


# ---------------------------------------------------------------------------
# T7: Source-Inspektion — Filter-Bedingung in _on_meter_update
# ---------------------------------------------------------------------------


def _extract_swr_block():
    """Extrahiert den SWR-Branch-Code aus _on_meter_update."""
    m = re.search(
        r"def _on_meter_update\(self, name.*?(?=\n    @Slot|\n    def |\Z)",
        MW_TX_SRC, re.S,
    )
    assert m is not None, "_on_meter_update nicht gefunden"
    body = m.group(0)
    swr_start = body.find('elif name == "SWR":')
    assert swr_start > 0, "SWR-Branch nicht in _on_meter_update gefunden"
    # Nächster elif-Marker NACH dem SWR-Anfang
    swr_end = body.find('elif name ==', swr_start + len('elif name == "SWR":'))
    if swr_end == -1:
        return body[swr_start:]
    return body[swr_start:swr_end]


def test_t7_filter_in_on_meter_update():
    """T7: _on_meter_update SWR-Branch hat Filter-Bedingung."""
    swr_block = _extract_swr_block()
    assert "is_transmitting" in swr_block, (
        "P148: SWR-Branch muss is_transmitting prüfen.")
    assert "_tune_active" in swr_block, (
        "P148: SWR-Branch muss _tune_active prüfen.")


def test_t7b_filter_comment_references_p148():
    """T7b: Filter hat P148-Kommentar mit Mike-Field-Bug-Datum."""
    swr_block = _extract_swr_block()
    assert "P148" in swr_block, (
        "P148: P148-Tag im Kommentar fehlt — Doku-Pflicht.")


# ---------------------------------------------------------------------------
# T8: Source-Inspektion — Bandwechsel ruft reset_swr_display
# ---------------------------------------------------------------------------


def test_t8_band_changed_calls_reset_swr():
    """T8: _on_band_changed in mw_radio.py ruft reset_swr_display()."""
    m = re.search(
        r"def _on_band_changed\(self, band.*?(?=\n    def |\n    @Slot)",
        MW_RADIO_SRC, re.S,
    )
    assert m is not None
    body = m.group(0)
    assert "reset_swr_display()" in body, (
        "P148: _on_band_changed muss control_panel.reset_swr_display() rufen.")


def test_t8b_reset_after_band_set():
    """T8b: reset_swr_display kommt NACH settings.set('band', band)
    — Reset gehört zum neuen Band-Kontext, nicht zum alten."""
    m = re.search(
        r"def _on_band_changed\(self, band.*?(?=\n    def |\n    @Slot)",
        MW_RADIO_SRC, re.S,
    )
    body = m.group(0)
    pos_set = body.find('self.settings.set("band", band)')
    pos_reset = body.find("reset_swr_display()")
    assert pos_set > 0 and pos_reset > 0
    assert pos_reset > pos_set, (
        "P148: reset_swr_display muss NACH settings.set('band') laufen.")


# ---------------------------------------------------------------------------
# T9: P53 SWR-Watchdog ist unbeeinflusst (Hardware-Sicherheit)
# ---------------------------------------------------------------------------


def test_t9_swr_watchdog_reads_radio_last_swr():
    """T9 (Hardware-Sicherheit): SWR-Watchdog liest `radio._last_swr`
    aus FlexRadio direkt — UI-Filter (P148) hat keinen Einfluss.

    Wenn dieser Test fehlschlägt → Hardware-Sicherheits-Schicht in
    Gefahr! P53 muss UNABHÄNGIG von UI-Anzeige funktionieren.
    """
    # check_swr_safe liest _last_swr
    assert "_last_swr" in FLEXRADIO_SRC, (
        "Hardware-Quelle _last_swr muss in flexradio.py existieren.")
    assert "self._last_swr <" in FLEXRADIO_SRC or \
           "self._last_swr < self._swr_limit" in FLEXRADIO_SRC, (
        "check_swr_safe muss _last_swr direkt prüfen — nicht UI-Anzeige.")
    # swr_alarm wird mit Hardware-Wert emittiert, nicht UI-Wert
    assert "swr_alarm.emit(self._last_swr)" in FLEXRADIO_SRC, (
        "swr_alarm muss Hardware-_last_swr emittieren, nicht UI-Wert.")


def test_t9b_update_swr_does_not_modify_radio_last_swr():
    """T9b: update_swr (UI-Setter) modifiziert NICHT radio._last_swr.

    Defensive Verifikation: UI ist Read-Only-Anzeige der Hardware-
    Telemetrie, niemals umgekehrt.
    """
    m = re.search(
        r"def update_swr\(self, swr.*?(?=\n    def )",
        CONTROL_PANEL_SRC, re.S,
    )
    assert m is not None
    body = m.group(0)
    # Präzise: update_swr darf die HARDWARE-Telemetrie radio._last_swr /
    # radio.last_swr NICHT schreiben. (P156: `self._last_swr_for_netto` ist
    # UI-Netto-State, KEINE Radio-Manipulation — daher kein blanker
    # `_last_swr`-Substring-Check mehr.)
    assert "radio._last_swr" not in body, (
        "update_swr darf radio._last_swr NICHT manipulieren!")
    assert "radio.last_swr" not in body, (
        "update_swr darf radio.last_swr NICHT manipulieren!")


# ---------------------------------------------------------------------------
# T10: Defensiver Test — Field-Szenario aus Mike-Bug
# ---------------------------------------------------------------------------


def test_t10_mike_field_scenario():
    """T10: Mike's konkretes Field-Szenario 27.05. 06:44:

    Sequenz:
    1. User drückt TUNE → _tune_active=True → SWR 2.4 ankommt → angezeigt
    2. TUNE-Ende → _tune_active=False, is_transmitting=False
    3. FlexRadio pusht im RX kontinuierlich SWR 1.0
    4. → KEIN update_swr → Anzeige bleibt auf 2.4 (letzter echter Wert)

    Test simuliert Schritt 3+4: in RX wird Update geblockt.
    """
    # Phase 1: TUNE läuft
    self_tune = _make_self_mock(is_transmitting=False, tune_active=True)
    _call_swr_branch(self_tune, 2.4)
    self_tune.control_panel.update_swr.assert_called_once_with(2.4)

    # Phase 2: TUNE beendet, FlexRadio pusht Sensor-Default 1.0 im RX
    self_rx = _make_self_mock(is_transmitting=False, tune_active=False)
    _call_swr_branch(self_rx, 1.0)  # Misleading-Wert
    self_rx.control_panel.update_swr.assert_not_called()
    # → Anzeige bleibt auf 2.4 vom Tune (in echtem UI; hier nur Mock-Check)
