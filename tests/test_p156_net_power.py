"""P156 (28.05.2026, v0.98.39) — Netto-Leistung dezent anzeigen.

Mike-Wunsch (erfahrener Funker): die angezeigten Watt sind FWDPWR (vorlauf
Richtung Antenne), nicht was bei schlechtem SWR effektiv durchgeht. Daher
zusaetzlich eine kleine, dunkelgraue, statische Netto-Zahl in Klammern
ZWISCHEN W und SWR — nur wenn Leistung anliegt (W > 0). Tooltip erklaert
ehrlich „netto in die Leitung" (nicht „abgestrahlt").

Physik (DeepSeek-validiert): Gamma=(SWR-1)/(SWR+1), netto=FWD*(1-Gamma^2).

DeepSeek Konzept-R1 + Implementierungs-R1: FREIGEGEBEN. Farbe #666
(dunkelgrau), reset auch _last_watt (R1-Hinweise eingebaut).

Tests:
- T1-T5: compute_net_power Physik (SWR 1.0/2.6/hoch/<=1, Rundung)
- T6: update_watt>0 + update_swr → Netto-Klammer sichtbar
- T7: update_watt(0) (RX) → Klammer leer
- T8: reset_swr_display → Klammer leer + State zurueck
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from ui.control_panel import compute_net_power


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ── Pure-Funktion: Physik ──────────────────────────────────────────
def test_t1_swr_1_full_power():
    """T1: SWR 1.0 → keine Reflexion → netto = FWD."""
    assert compute_net_power(70, 1.0) == 70


def test_t2_swr_2_6_mike_example():
    """T2: Mikes Screenshot-Fall — 70 W, SWR 2.6 → ~56 W (80% durch)."""
    # gamma=1.6/3.6=0.4444, gamma^2=0.1975, 70*0.8025=56.17 → 56
    assert compute_net_power(70, 2.6) == 56


def test_t3_high_swr_near_zero():
    """T3: sehr hohes SWR → fast alles reflektiert → netto drastisch reduziert.
    SWR 50 → gamma≈0.96 → ~7% durch → ~5 W von 70 W."""
    assert compute_net_power(70, 50.0) < 10


def test_t4_swr_below_one_defensive():
    """T4: SWR <= 1 (physikalisch unmoeglich, defensiv) → volle FWD."""
    assert compute_net_power(70, 0.9) == 70
    assert compute_net_power(70, 1.0) == 70


def test_t5_rounding_integer():
    """T5: ganzzahlig, kein Schein-Praezision."""
    r = compute_net_power(33, 1.8)
    assert isinstance(r, int)
    # gamma=0.8/2.8=0.2857, ^2=0.0816, 33*0.9184=30.3 → 30
    assert r == 30


# ── Display-Logik ──────────────────────────────────────────────────
def test_t6_netto_visible_during_tx(qapp):
    """T6: update_watt(>0) + update_swr → Netto-Klammer sichtbar."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp.update_swr(2.6)
    cp.update_watt(70)
    assert cp.netto_label.text() == "(56)", (
        f"Netto-Klammer erwartet '(56)', war '{cp.netto_label.text()}'")


def test_t7_netto_hidden_in_rx(qapp):
    """T7: update_watt(0) (RX, keine Leistung) → Klammer leer."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp.update_swr(2.6)
    cp.update_watt(70)
    assert cp.netto_label.text() == "(56)"
    cp.update_watt(0)                       # TX endet
    assert cp.netto_label.text() == "", "Bei 0 W darf keine Netto-Zahl stehen"


def test_t8_reset_clears_netto(qapp):
    """T8: reset_swr_display (Bandwechsel) → Klammer leer + State zurueck."""
    from ui.control_panel import ControlPanel
    cp = ControlPanel()
    cp.update_swr(2.6)
    cp.update_watt(70)
    assert cp.netto_label.text() == "(56)"
    cp.reset_swr_display()
    assert cp.netto_label.text() == ""
    assert cp._last_swr_for_netto == 1.0
    assert cp._last_watt == 0.0
