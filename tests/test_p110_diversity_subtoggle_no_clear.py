"""P110 (21.05.2026, v0.97.87) — Diversity↔Diversity Sub-Toggle skippt RX-Clear.

Mike-Spec 21.05.: Beim Wechsel Std↔DX innerhalb von Diversity nutzen beide
Modi DIESELBEN 2 Antennen mit derselben Gain-Config. Stationen sind weiter
empfangbar, Werte adaptieren sich in 1-2 Slots automatisch — RX-Panel zu
leeren ist nicht nötig und nervt visuell.

Loesung: clear_panels: bool = True an _enable_diversity / _check_diversity_preset
/ _activate_diversity_with_scoring. Default True (echter Modus-Wechsel).
_on_diversity_subtoggle_requested ruft mit clear_panels=False.

Tests:
- T1: Source — _enable_diversity hat clear_panels-Parameter mit Default True
- T2: Source — Clear-Block (setRowCount, log_view.clear) in if clear_panels:
- T3: Source — _on_diversity_subtoggle_requested ruft mit clear_panels=False
- T4: Source — _check_diversity_preset reicht clear_panels durch
- T5: Source — _activate_diversity_with_scoring hat clear_panels-Parameter
- T6: Source — _activate_diversity_with_scoring _diversity_stations={} ist if-geschützt
- T7: Bandwechsel-Pfad ruft OHNE clear_panels (Default=True → Verhalten unverändert)
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(rel: str) -> str:
    return (Path(__file__).resolve().parent.parent / rel).read_text(
        encoding="utf-8")


def test_t1_enable_diversity_has_clear_panels_param():
    """_enable_diversity Signatur enthält clear_panels: bool = True."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _enable_diversity\(self,\s*scoring_mode:\s*str\s*=\s*\"normal\"\s*,"
        r"\s*clear_panels:\s*bool\s*=\s*True\s*\)",
        src,
    )
    assert m, ("P110: _enable_diversity muss clear_panels: bool = True "
               "als zweiten Parameter haben")


def test_t2_clear_block_inside_if_clear_panels():
    """Clear-Statements müssen INNERHALB von `if clear_panels:` stehen."""
    src = _read("ui/mw_radio.py")
    # Zwischen _enable_diversity-Header und nächstem method-Def
    m = re.search(
        r"def _enable_diversity\(.*?\n(.*?)(?=\n    def )",
        src, re.DOTALL)
    assert m, "_enable_diversity-Body nicht gefunden"
    body = m.group(1)
    # Erwartung: `if clear_panels:` kommt im Body vor, und danach folgen
    # die Clear-Aufrufe
    if_idx = body.find("if clear_panels:")
    assert if_idx >= 0, "P110: `if clear_panels:` fehlt im _enable_diversity-Body"
    after_if = body[if_idx:]
    for stmt in ("rx_panel.table.setRowCount(0)",
                 "_diversity_stations = {}",
                 "_normal_stations = {}",
                 "log_view.clear()",
                 "update_decode_count(0)"):
        assert stmt in after_if, (f"P110: '{stmt}' muss innerhalb des "
                                   f"`if clear_panels:`-Blocks stehen")


def test_t3_subtoggle_calls_with_clear_panels_false():
    """_on_diversity_subtoggle_requested ruft mit clear_panels=False."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _on_diversity_subtoggle_requested.*?(?=\n    def )",
        src, re.DOTALL)
    assert m, "_on_diversity_subtoggle_requested nicht gefunden"
    body = m.group(0)
    assert re.search(
        r"_activate_diversity_with_scoring\(new,\s*clear_panels=False\)",
        body,
    ), ("P110: Sub-Toggle muss _activate_diversity_with_scoring "
        "mit clear_panels=False rufen")


def test_t4_check_preset_passes_clear_panels_through():
    """_check_diversity_preset hat clear_panels-Parameter + reicht durch."""
    src = _read("ui/mw_radio.py")
    # Signatur
    m_sig = re.search(
        r"def _check_diversity_preset\(self,\s*band:\s*str,\s*scoring:\s*str,"
        r"\s*clear_panels:\s*bool\s*=\s*True\s*\)",
        src,
    )
    assert m_sig, ("P110: _check_diversity_preset muss clear_panels: "
                   "bool = True als 3. Parameter haben")
    # Aufruf von _enable_diversity reicht durch
    m_pass = re.search(
        r"self\._enable_diversity\(scoring_mode=scoring,\s*"
        r"clear_panels=clear_panels\)",
        src,
    )
    assert m_pass, ("P110: _check_diversity_preset muss "
                    "_enable_diversity mit clear_panels=clear_panels rufen")


def test_t5_activate_diversity_has_clear_panels_param():
    """_activate_diversity_with_scoring hat clear_panels-Parameter."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _activate_diversity_with_scoring\(self,\s*scoring:\s*str,"
        r"\s*clear_panels:\s*bool\s*=\s*True\s*\)",
        src,
    )
    assert m, ("P110: _activate_diversity_with_scoring muss "
               "clear_panels: bool = True als 2. Parameter haben")


def test_t6_diversity_stations_clear_is_conditional():
    """_diversity_stations = {} in _activate_diversity_with_scoring nur bei
    clear_panels=True."""
    src = _read("ui/mw_radio.py")
    m = re.search(
        r"def _activate_diversity_with_scoring\(.*?(?=\n    def )",
        src, re.DOTALL)
    assert m, "_activate_diversity_with_scoring-Body nicht gefunden"
    body = m.group(0)
    # `if clear_panels:` muss vor `self._diversity_stations = {}` stehen
    if_match = re.search(r"if clear_panels:\s*\n\s+self\._diversity_stations\s*=\s*\{\}",
                          body)
    assert if_match, ("P110: _diversity_stations = {} muss innerhalb "
                       "if clear_panels: stehen")


def test_t7_band_change_path_unchanged():
    """Bandwechsel-Pfad (_on_band_changed → _check_diversity_preset)
    nutzt Default clear_panels=True → kein expliziter Parameter."""
    src = _read("ui/mw_radio.py")
    # Im _on_band_changed-Handler darf _check_diversity_preset OHNE
    # clear_panels-Argument aufgerufen werden (Default True greift)
    m = re.search(
        r"def _on_band_changed.*?(?=\n    def )",
        src, re.DOTALL)
    if m:
        body = m.group(0)
        # Wenn _check_diversity_preset aufgerufen wird, dann nicht mit
        # clear_panels=False
        for call in re.findall(
                r"_check_diversity_preset\([^)]*\)", body):
            assert "clear_panels=False" not in call, (
                f"P110: Bandwechsel darf NICHT mit clear_panels=False "
                f"rufen (Call: {call})")
