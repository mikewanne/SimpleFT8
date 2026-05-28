"""P159 (28.05.2026) — SWR-Clamp-1.0-Werte aus Median filtern.

Mike-Field-Bug 28.05.: Band 15M wurde mal mit „SWR 1.0" freigegeben, mal mit
„SWR 28.5" gesperrt — echter Wert war 2.4. Mike-Diagnose (Funker-Praxis): ein
SWR von exakt 1.0 ist auf einer echten KW-Antenne praktisch unmöglich (nur
Dummy-Load), sein bester realer Wert je: 1.2.

Root Cause: Der FlexRadio-SWR-Sensor clampt bei fehlender Vorwärtsleistung
(FWDPWR≈0, kein Träger) HART auf exakt 1.0 (radio/flexradio.py:
`if swr < 1.0: swr = 1.0`). Diese künstlichen 1.0-Werte landeten in
`_tune_swr_samples` und verfälschten den Median in `_compute_match_swr`.

Field-Beweis (Debug-Log 14:52:29, Fenster [7-9s], n=33):
  samples = 14× [2.5-2.6 ECHT] + 19× [1.0 CLAMP]  → median=1.00
  → Band fälschlich freigegeben (echter Match war 2.5-2.6).
Echte Werte streuen (2.5/2.6); der Clamp ist immer EXAKT 1.0.

Fix: `_compute_match_swr` filtert `swr > 1.0` aus dem Fenster. Verschiebt den
Median nach OBEN = immer in die sichere Richtung (DeepSeek-R1 GO). Bleiben < 3
echte Werte (nur Clamps = kein echter Träger) → None → Band bleibt gesperrt.

Pattern-Klasse Hardware-Sicherheit 6. Iteration (P53/P76-A/P142/P153/P154/P159).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MW_TX_SRC = (REPO / "ui" / "mw_tx.py").read_text()


class _FakeTX:
    """Minimal-Mock für _compute_match_swr — nur die genutzten Attribute."""
    def __init__(self, samples, duration):
        self._tune_swr_samples = samples
        self._tune_duration_s = duration


def _compute(samples, duration):
    from ui.mw_tx import TXMixin
    fake = _FakeTX(samples, duration)
    return TXMixin._compute_match_swr(fake)


# ── Funktionale Tests ────────────────────────────────────────────────────────

def test_t1_mike_field_scenario_clamp_filtered():
    """T1: Mike-Field-Bug 14:52 — 14 echte (2.5-2.6) + 19 Clamp (1.0).
    Vorher Median 1.0 (Band fälschlich frei). Jetzt: Clamps raus → Median 2.5-2.6.
    """
    # Fenster [7-9s] bei 10s Tune. Reihenfolge wie im echten Log.
    real = [(7.0 + i * 0.05, 2.5 if i % 2 else 2.6) for i in range(14)]
    clamp = [(7.7 + i * 0.05, 1.0) for i in range(19)]
    samples = real + clamp
    r = _compute(samples, 10.0)
    assert r is not None, "echte Werte vorhanden → kein None"
    assert r > 1.0, f"Median darf nicht der Clamp-Wert 1.0 sein, war {r}"
    assert r == pytest.approx(2.55, abs=0.1), (
        f"Median der echten 2.5/2.6-Werte erwartet ~2.5-2.6, war {r}")


def test_t2_only_clamp_returns_none():
    """T2: Fenster enthält NUR Clamp-1.0-Werte (kein echter Träger) → None
    → Band bleibt gesperrt (sicher)."""
    samples = [(7.0 + i * 0.1, 1.0) for i in range(20)]
    r = _compute(samples, 10.0)
    assert r is None, "Nur Clamp-Werte → keine gültige Messung → None (gesperrt)"


def test_t3_real_values_unchanged_regression():
    """T3 Regression: Fenster ohne Clamp-Werte → Median wie bisher."""
    samples = [(7.1, 2.4), (7.5, 2.5), (8.0, 2.4), (8.5, 2.6), (9.0, 2.5)]
    r = _compute(samples, 10.0)
    assert r == pytest.approx(2.5, abs=0.1)


def test_t4_clamp_filter_threshold_exactly_one():
    """T4: Schwelle `> 1.0` — exakt 1.0 raus, 1.1 drin (DeepSeek: nicht >=1.1,
    sonst würden echte gute Matches wie 1.2 wegfallen)."""
    # 3 echte knapp über 1.0 + 5 Clamp → echte zählen, Median aus echten
    samples = [(7.0, 1.0), (7.2, 1.0), (7.4, 1.1), (7.6, 1.2), (7.8, 1.3),
               (8.0, 1.0), (8.2, 1.0)]
    r = _compute(samples, 10.0)
    assert r is not None, "3 echte Werte (1.1/1.2/1.3) → gültig"
    assert r == pytest.approx(1.2, abs=0.01), (
        f"Median der echten 1.1/1.2/1.3 = 1.2 (1.0er gefiltert), war {r}")


def test_t5_clamp_drops_below_min_samples():
    """T5: 14 echte aber davon nur 2 im Fenster + viele Clamps → < 3 echte
    im Fenster → None (Hardware-Sicherheit bleibt erhalten)."""
    samples = [(7.1, 2.5), (7.5, 2.6)] + [(8.0 + i * 0.1, 1.0) for i in range(10)]
    r = _compute(samples, 10.0)
    assert r is None, "Nur 2 echte Werte im Fenster (< 3) → None"


def test_t6_genuine_bad_match_stays_blocked():
    """T6 Hardware-Sicherheit: echt schlechtes Match (4.x) wird NICHT durch
    Clamp-Filter künstlich gut — bleibt > Limit → gesperrt."""
    samples = [(7.1, 4.2), (7.5, 4.0), (8.0, 4.5), (8.5, 4.1), (9.0, 4.0)]
    r = _compute(samples, 10.0)
    assert r is not None
    assert r > 3.0, f"echt schlechtes Match muss > Limit bleiben, war {r}"


# ── Source-Inspektion ────────────────────────────────────────────────────────

def _compute_body():
    m = re.search(r"def _compute_match_swr.*?(?=\n    def )", MW_TX_SRC, re.S)
    assert m is not None, "_compute_match_swr nicht gefunden"
    return m.group(0)


def test_t7_filter_in_window_comprehension():
    """T7: Der `> 1.0`-Filter sitzt in der window-Comprehension von
    _compute_match_swr (Filter-Ort: Median, nicht Sammlung → Rohdaten bleiben
    im Diagnose-Log)."""
    body = _compute_body()
    assert "swr > 1.0" in body, "P159: Clamp-Filter `swr > 1.0` fehlt"
    assert "win_start <= el <= win_end and swr > 1.0" in body, (
        "P159: Filter muss in der window-Comprehension stehen (mit Zeitfenster)")
    assert "len(window) >= 3" in body, "Mindest-3-Samples-Sicherung bleibt"
    assert "P159" in body, "P159-Doku-Marker fehlt"


def test_t8_diagnostic_log_counts_clamps():
    """T8: Diagnose-Log in _tune_stop zeigt Anzahl gefilterter Clamp-Werte
    (Transparenz — Rohwerte bleiben sichtbar)."""
    m = re.search(r"def _tune_stop\(self, token.*?(?=\n    def )", MW_TX_SRC, re.S)
    assert m is not None
    body = m.group(0)
    assert "clamps_gefiltert" in body, (
        "P159: Diagnose-Log muss clamps_gefiltert-Zähler enthalten")
    assert "if s <= 1.0" in body, "P159: Clamp-Zählung im Log"


def test_t9_sample_collection_unchanged():
    """T9: Die Sample-Sammlung in _on_meter_update bleibt UNgefiltert
    (Rohdaten vollständig — Filter erst im Median). Schützt Diagnose."""
    m = re.search(r"def _on_meter_update.*", MW_TX_SRC, re.S)
    assert m is not None
    body = m.group(0)
    # Sammlung hängt alle Werte an, KEIN > 1.0 Guard an der append-Stelle
    assert "self._tune_swr_samples.append((_elapsed, value))" in body, (
        "P159: Sammlung bleibt ungefiltert (Rohdaten vollständig)")
