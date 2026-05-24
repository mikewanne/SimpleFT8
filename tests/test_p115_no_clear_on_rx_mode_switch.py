"""P115 (24.05.2026, v0.98.00) — Empfangsfenster nicht löschen bei
RX-Mode-Switch + Kalibrierungs-Ende + Diversity-Sub-Toggle.

Mike-Spec 24.05.: „Empfangsfenster wird nach Kalibrieren gelöscht, ist
überflüssig wenn wir auf dem Band bleiben. Bei Bandwechsel oder
Modus-Wechsel (FT8-FT4) macht es Sinn, aber nicht wenn wir bleiben auf
dem Band und auch nicht wenn wir von Normal auf Diversity wechseln,
dann kann der Inhalt doch auch bleiben."

Mike-Klärung Sub-Toggle Std↔DX: „auch nicht löschen. Beim nächsten
Slot wird eh alles aktualisiert — das ist wie ein Fortschrittsbalken
beim Kopieren."

P115 ersetzt P110: `clear_panels`-Parameter komplett aus API entfernt.
Stationen bleiben sichtbar in `_enable_diversity` / `_disable_diversity`
/ `_activate_diversity_with_scoring` / `_on_rx_mode_changed`. Echte
Lösch-Pfade sind `_on_band_changed`, `_on_mode_changed`,
`_on_rx_panel_toggled`.

Test-Coverage:
- T1: _enable_diversity Signatur ohne clear_panels-Parameter
- T2: _activate_diversity_with_scoring Signatur ohne clear_panels
- T3: _check_diversity_preset Signatur ohne clear_panels
- T4: _enable_diversity-Body enthält keine setRowCount(0)/stations={}
- T5: _disable_diversity-Body enthält keine setRowCount(0)/stations={}
- T6: _on_rx_mode_changed enthält kein setRowCount(0)/_normal_stations={}
- T7 Regression: _on_band_changed löscht NACH WIE VOR (Mike-Liste)
- T8 Regression: _on_mode_changed löscht NACH WIE VOR (Mike-Liste)
- T9 Regression: _on_rx_panel_toggled löscht NACH WIE VOR (Mike-Klärung)
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path


SRC = (Path(__file__).resolve().parent.parent / "ui" / "mw_radio.py").read_text()


# ── T1-T3: Signaturen ohne clear_panels ─────────────────────────────


def test_t1_enable_diversity_no_clear_panels_param():
    """P115: _enable_diversity Signatur enthält KEIN clear_panels."""
    from ui.mw_radio import RadioMixin
    sig = inspect.signature(RadioMixin._enable_diversity)
    params = list(sig.parameters.keys())
    assert "clear_panels" not in params, (
        "P115: _enable_diversity darf clear_panels NICHT mehr haben "
        "(Stations bleiben immer sichtbar)")


def test_t2_activate_diversity_with_scoring_no_clear_panels_param():
    """P115: _activate_diversity_with_scoring Signatur ohne clear_panels."""
    from ui.mw_radio import RadioMixin
    sig = inspect.signature(RadioMixin._activate_diversity_with_scoring)
    params = list(sig.parameters.keys())
    assert "clear_panels" not in params, (
        "P115: _activate_diversity_with_scoring darf clear_panels NICHT haben")


def test_t3_check_diversity_preset_no_clear_panels_param():
    """P115: _check_diversity_preset Signatur ohne clear_panels."""
    from ui.mw_radio import RadioMixin
    sig = inspect.signature(RadioMixin._check_diversity_preset)
    params = list(sig.parameters.keys())
    assert "clear_panels" not in params, (
        "P115: _check_diversity_preset darf clear_panels NICHT haben")


# ── T4-T6: Lösch-Code aus drei Methoden raus ────────────────────────


def _extract_method_body(method_name: str) -> str:
    """Extrahiert Body einer Methode aus SRC bis zur nächsten def."""
    m = re.search(rf"    def {method_name}\(", SRC)
    assert m, f"Methode {method_name} nicht gefunden"
    start = m.start()
    nxt = re.search(r"\n    def ", SRC[start + 10:])
    end = start + 10 + nxt.start() if nxt else len(SRC)
    return SRC[start:end]


def test_t4_enable_diversity_no_clear_statements():
    """P115: _enable_diversity-Body enthält keine setRowCount(0) /
    _diversity_stations={} / _normal_stations={} / log_view.clear() /
    update_decode_count(0) — alle Lösch-Statements raus."""
    body = _extract_method_body("_enable_diversity")
    forbidden = [
        "setRowCount(0)",
        "_diversity_stations = {}",
        "_normal_stations = {}",
        "log_view.clear()",
        "update_decode_count(0)",
    ]
    for stmt in forbidden:
        assert stmt not in body, (
            f"P115: _enable_diversity darf '{stmt}' NICHT mehr enthalten "
            f"(Stations bleiben sichtbar)")


def test_t5_disable_diversity_no_clear_statements():
    """P115: _disable_diversity-Body enthält keine Lösch-Statements für
    RX-Liste/Stations (NUR qso_panel.log_view.clear() bleibt — Chronik,
    R1-F4 Klärung — Mike's „Empfangsfenster" ist nur die Stationsliste)."""
    body = _extract_method_body("_disable_diversity")
    forbidden = [
        "rx_panel.table.setRowCount(0)",
        "self._diversity_stations = {}",
        "self._normal_stations = {}",
        "update_decode_count(0)",
    ]
    for stmt in forbidden:
        assert stmt not in body, (
            f"P115: _disable_diversity darf '{stmt}' NICHT mehr enthalten")


def test_t6_on_rx_mode_changed_no_clear_statements():
    """P115: _on_rx_mode_changed enthält keine Lösch-Statements für
    RX-Liste/Stations."""
    body = _extract_method_body("_on_rx_mode_changed")
    forbidden = [
        "self.rx_panel.table.setRowCount(0)",
        "self._normal_stations = {}",
        "self.control_panel.update_decode_count(0)",
    ]
    for stmt in forbidden:
        assert stmt not in body, (
            f"P115: _on_rx_mode_changed darf '{stmt}' NICHT enthalten "
            f"(Normal↔Diversity-Wechsel behält Stationen — Mike-Spec)")


# ── T7-T9: Regression — die 3 erlaubten Lösch-Pfade laufen weiter ──


def test_t7_on_band_changed_still_clears():
    """Regression: _on_band_changed muss WEITERHIN löschen (Mike-Liste:
    Bandwechsel = echter Kontext-Wechsel, Stationen alle anders)."""
    body = _extract_method_body("_on_band_changed")
    assert "self.rx_panel.table.setRowCount(0)" in body, (
        "Regression: _on_band_changed muss RX-Liste löschen")
    assert "self._diversity_stations = {}" in body, (
        "Regression: _on_band_changed muss _diversity_stations leeren")
    assert "self._normal_stations = {}" in body, (
        "Regression: _on_band_changed muss _normal_stations leeren")


def test_t8_on_mode_changed_still_clears():
    """Regression: _on_mode_changed (FT8↔FT4↔FT2) muss WEITERHIN löschen
    (Mike-Liste: Modus-Wechsel = anderer Kontext, Slot-Dauer + Decoder
    anders, alte Stationen passen nicht zum neuen Modus)."""
    body = _extract_method_body("_on_mode_changed")
    assert "self.rx_panel.table.setRowCount(0)" in body, (
        "Regression: _on_mode_changed muss RX-Liste löschen")
    assert "self._diversity_stations = {}" in body, (
        "Regression: _on_mode_changed muss _diversity_stations leeren")


def test_t9_on_rx_panel_toggled_still_clears():
    """Regression: _on_rx_panel_toggled (RX ON/OFF) muss WEITERHIN
    löschen (Mike-Klärung 24.05.: bewusster RX-Neustart-Akt)."""
    body = _extract_method_body("_on_rx_panel_toggled")
    assert "self.rx_panel.table.setRowCount(0)" in body, (
        "Regression: _on_rx_panel_toggled muss RX-Liste löschen")
    assert "self._diversity_stations = {}" in body, (
        "Regression: _on_rx_panel_toggled muss _diversity_stations leeren")
