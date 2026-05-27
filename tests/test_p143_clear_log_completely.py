"""P143 (26.05.2026) — qso_panel.clear_log_completely Helper.

Mike-Field-Bug 26.05.: Bandwechsel 30m -> 20m leerte log_view, ABER
nicht _entries (Master-SOT eingefuehrt mit P95). Der 30s-Auto-Trim-
Timer (_cleanup_timer in qso_panel.py) ruft _rerender_all() das aus
_entries neu zeichnet -> alte 30m-Sende-Eintraege erschienen nach
Bandwechsel auf 20m wieder im Log.

Fix (Option B, Mike-Spec):
- Helper-Methode qso_panel.clear_log_completely() macht alles richtig
- 3 Aufrufer in mw_radio.py ersetzen den nackten log_view.clear()

Mike-Spec fuer welche Pfade leer:
- Bandwechsel (_on_band_changed)            : JA
- FT-Mode-Wechsel (_on_mode_changed)        : JA
- RX-On/Off-Toggle (set_rx_active)          : JA
- RX-Mode-Switch (Normal<->Diversity)       : NEIN (P115 Chronik)
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def qapp():
    """QApplication-Fixture fuer Tests die echte Widgets brauchen."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# T1: Helper existiert + leert alle 3 States
# ---------------------------------------------------------------------------


def test_t1_helper_exists_and_clears_three_states(qapp):
    """T1: clear_log_completely() leert _entries, log_view UND
    _last_omni_tx_even."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()

    # Vorbereitung: alle 3 States fuellen (echte API-Signaturen)
    panel.add_rx("K1ABC DA1MHH -10", tx_even=True, ant_label="A1")
    panel.add_info("Test-Info")
    panel._last_omni_tx_even = True
    assert len(panel._entries) > 0
    assert panel.log_view.toPlainText() != ""
    assert panel._last_omni_tx_even is True

    # Akt: Helper aufrufen
    panel.clear_log_completely()

    # Verifikation: alle 3 States geleert
    assert panel._entries == [], "_entries muss leer sein"
    assert panel.log_view.toPlainText() == "", "log_view muss leer sein"
    assert panel._last_omni_tx_even is None, (
        "_last_omni_tx_even muss None sein (OMNI-Parity-Reset)")


# ---------------------------------------------------------------------------
# T2: 3 mw_radio.py-Aufrufer rufen Helper auf (Source-Inspektion)
# ---------------------------------------------------------------------------


MW_RADIO_SRC = (Path(__file__).resolve().parent.parent
                / "ui" / "mw_radio.py").read_text()


def test_t2a_on_band_changed_calls_helper():
    """T2a: _on_band_changed nutzt clear_log_completely (P143)."""
    import re
    m = re.search(
        r"def _on_band_changed\(self,.*?(?=\n    def )",
        MW_RADIO_SRC, re.S)
    assert m is not None, "_on_band_changed nicht gefunden"
    body = m.group(0)
    assert "clear_log_completely()" in body, (
        "P143: _on_band_changed MUSS clear_log_completely() rufen "
        "statt nur log_view.clear().")
    # Sicherstellen dass NICHT MEHR der alte nackte log_view.clear()
    # Aufruf existiert
    assert "self.qso_panel.log_view.clear()" not in body, (
        "Alter log_view.clear()-Aufruf muss ersetzt sein.")


def test_t2b_on_mode_changed_calls_helper():
    """T2b: _on_mode_changed (FT8↔FT4) nutzt clear_log_completely."""
    import re
    m = re.search(
        r"def _on_mode_changed\(self,.*?(?=\n    def )",
        MW_RADIO_SRC, re.S)
    assert m is not None, "_on_mode_changed nicht gefunden"
    body = m.group(0)
    assert "clear_log_completely()" in body, (
        "P143: _on_mode_changed MUSS clear_log_completely() rufen.")


def test_t2c_on_rx_panel_toggled_calls_helper():
    """T2c: _on_rx_panel_toggled (RX-On/Off-Toggle) nutzt
    clear_log_completely."""
    import re
    m = re.search(
        r"def _on_rx_panel_toggled\(self,.*?(?=\n    def )",
        MW_RADIO_SRC, re.S)
    assert m is not None, "_on_rx_panel_toggled nicht gefunden"
    body = m.group(0)
    assert "clear_log_completely()" in body, (
        "P143: _on_rx_panel_toggled MUSS clear_log_completely() rufen.")


# ---------------------------------------------------------------------------
# T3: rx_mode-Switch-Pfade rufen Helper NICHT auf (P115-Spec)
# ---------------------------------------------------------------------------


def test_t3_rx_mode_setters_do_not_clear():
    """T3: set_rx_mode + _on_rx_mode_clicked rufen NICHT
    clear_log_completely (P115: optische Kontinuität bei
    Normal↔Diversity-Switch)."""
    import re
    # set_rx_mode in mw_radio.py oder control_panel.py
    for pattern in (r"def set_rx_mode\(self,.*?(?=\n    def )",
                    r"def _on_rx_mode_clicked\(self,.*?(?=\n    def )"):
        m = re.search(pattern, MW_RADIO_SRC, re.S)
        if m is None:
            continue
        body = m.group(0)
        assert "clear_log_completely" not in body, (
            f"P115: Pfad {pattern[4:25]} darf NICHT clear_log_completely "
            "rufen (optische Kontinuität bei rx_mode-Switch).")


# ---------------------------------------------------------------------------
# T4: Mike-Field-Szenario - clear_log_completely + _rerender_all
#     log_view bleibt leer (Bug-Reproduktion)
# ---------------------------------------------------------------------------


def test_t4_field_scenario_no_resurrection(qapp):
    """T4: Mike-Field-Bug: 30m-Eintraege fuellen, clear_log_completely,
    dann _rerender_all triggern -> log_view bleibt LEER.

    Vor P143: log_view.clear() ohne _entries.clear() -> _rerender_all
    zog Eintraege aus _entries zurueck -> Mike-Bug.
    """
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()

    # 30m-Szenario: paar Sende-Eintraege (echte API-Signaturen)
    panel.add_tx("BG4UCZ DA1MHH -15", ant_label="A1", tx_even=True)
    panel.add_tx("R9AL DA1MHH -15", ant_label="A1", tx_even=False)
    panel.add_tx("MW0DNF DA1MHH -17", ant_label="A1", tx_even=True)
    assert len(panel._entries) == 3

    # Bandwechsel-Simulation: nackter log_view.clear() (WIE FRUEHER)
    # waere nicht ausreichend. Mike's Fix: clear_log_completely().
    panel.clear_log_completely()
    assert panel.log_view.toPlainText() == ""
    assert panel._entries == []

    # Simuliere 30s-Auto-Trim-Timer-Tick -> _rerender_all aus _entries
    panel._rerender_all()

    # Verifikation: kein Resurrection
    assert panel.log_view.toPlainText() == "", (
        "P143-Fix: nach clear_log_completely + _rerender_all muss "
        "log_view leer bleiben -- keine Eintraege aus dem Vor-Clear-"
        "Stand zurueckkehren (Mike-Field-Bug 26.05.).")


# ---------------------------------------------------------------------------
# T5: Reihenfolge Daten -> View -> State (R1-F1)
# ---------------------------------------------------------------------------


def test_t5_helper_order_data_view_state():
    """T5: Helper-Reihenfolge Daten -> View -> State (R1-F1
    Empfehlung). Verifiziert durch Source-Inspektion."""
    import re
    src = (Path(__file__).resolve().parent.parent
           / "ui" / "qso_panel.py").read_text()
    m = re.search(
        r"def clear_log_completely\(self\):.*?(?=\n    def )",
        src, re.S)
    assert m is not None, "clear_log_completely nicht gefunden"
    body = m.group(0)
    pos_entries = body.find("self._entries.clear()")
    pos_logview = body.find("self.log_view.clear()")
    pos_omni = body.find("self._last_omni_tx_even = None")
    assert pos_entries > 0 and pos_logview > 0 and pos_omni > 0
    assert pos_entries < pos_logview < pos_omni, (
        "Reihenfolge muss Daten -> View -> State sein "
        "(_entries -> log_view -> _last_omni_tx_even).")


# ---------------------------------------------------------------------------
# T6: Helper-Doku enthaelt Anti-Pattern-Hinweis (P115-Spec)
# ---------------------------------------------------------------------------


def test_t6_docstring_p115_anti_pattern():
    """T6: clear_log_completely-Docstring warnt explizit dass es NICHT
    bei rx_mode-Switch (Normal↔Diversity) gerufen werden darf
    (P115-Spec Chronik)."""
    from ui.qso_panel import QSOPanel
    doc = QSOPanel.clear_log_completely.__doc__ or ""
    assert "P115" in doc or "rx_mode" in doc.lower() or "diversity" in doc.lower(), (
        "Helper-Docstring muss vor versehentlichem Aufruf bei "
        "rx_mode-Switch warnen (P115-Spec).")


# ---------------------------------------------------------------------------
# T7: Idempotenz - mehrfach aufrufen schadet nicht
# ---------------------------------------------------------------------------


def test_t7_idempotent(qapp):
    """T7: Mehrfacher Helper-Aufruf bleibt sauber (keine Exception)."""
    from ui.qso_panel import QSOPanel
    panel = QSOPanel()
    panel.add_info("foo")
    panel.clear_log_completely()
    panel.clear_log_completely()  # zweiter Aufruf direkt danach
    panel.clear_log_completely()  # dritter
    assert panel._entries == []
    assert panel._last_omni_tx_even is None
