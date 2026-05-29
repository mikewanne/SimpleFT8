"""P153 (28.05.2026) — SWR-Freeze: Median über stabiles Fenster statt Snapshot.

Mike-Field-Bug 28.05.2026:
- Bandwechsel 15m → gesperrt. Manueller TUNE: Tuner matchte sichtbar auf
  SWR 2,5 (Anzeige zeigte es), ABER System fror >4,0 ein → Band blieb
  gesperrt („SWR 4.0 > Limit 3.0"). 2. TUNE: zufällig 2,3 → frei.

Root Cause: `_tune_stop` nahm einen EINZIGEN Momentan-Snapshot
(`radio.last_swr`). Wenn der genau einen Mess-/Regel-Ausreißer (4,0)
erwischt obwohl der Tuner stabil bei 2,5 ist → falscher Freeze.

Auslöser: P142 (27.05.) zog den Freeze von „nach Phase B" (5s
Stabilisierung) auf „nach Phase A" (direkt nach Match, SWR noch am
Schwanken) → Snapshot fragiler. P148 machte es sichtbar.

Fix (Mike-Spec): Median über Fenster [Dauer-3s, Dauer-1s] (= Sek. 7-9
bei 10s Tune). R1-V4-pro Hardware-Sicherheits-Nachschärfungen:
- F3: < 3 Samples im Fenster → None (nicht aussagekräftig)
- F6: KEIN Fallback auf radio.last_swr (= Snapshot-Bug zurück) → None
  → Post-Check behandelt None als FAIL → Band bleibt gesperrt

DeepSeek-Detail-Fehler abgefangen: behauptete `None <= 3.0 == False`,
ist aber Python-TypeError → expliziter `is not None`-Check im Code.

Pattern-Klasse Hardware-Sicherheit 4. Iteration (P53/P76-A/P142/P153).

Tests:
- T1: Mike-Bug-Szenario (2,5 stabil + 4,0 Spike) → Median ~2,5
- T2: echt schlechtes Match (4,x durchweg) → Median > Limit
- T3: < 3 Samples → None
- T4: leeres Fenster → None
- T5: 15s Tune → Fenster 12-14
- T6: Fenster-Grenzen (6,9/9,1 ausgeschlossen)
- T7: kurze Tune-Dauer (3s) → win_start=0
- T8: _tune_stop nutzt _compute_match_swr (nicht radio.last_swr direkt)
- T9: _tune_stop hat expliziten is-None-Check (kein None<=limit TypeError)
- T10: _on_meter_update sammelt SWR während TUNE
- T11: _tune_start initialisiert Sammlung
- T12: P153-Kommentar mit Mike-Field-Bug-Datum
"""

from __future__ import annotations

import re
import statistics
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MW_TX_SRC = (REPO / "ui" / "mw_tx.py").read_text()


# ---------------------------------------------------------------------------
# Funktionale Tests der _compute_match_swr-Logik (via Mock-self)
# ---------------------------------------------------------------------------

class _FakeTX:
    """Minimal-Mock für _compute_match_swr — nur die genutzten Attribute."""
    def __init__(self, samples, duration):
        self._tune_swr_samples = samples
        self._tune_duration_s = duration


def _compute(samples, duration):
    from ui.mw_tx import TXMixin
    fake = _FakeTX(samples, duration)
    return TXMixin._compute_match_swr(fake)


def test_t1_mike_bug_scenario_median_recovers():
    """T1: Tuner stabil 2,5 mit einem 4,0-Ausreißer → Median ~2,5 → Band frei."""
    samples = [
        (0.5, 30.0), (1.0, 12.0), (2.0, 6.0), (3.0, 3.5), (5.0, 2.6),
        (7.1, 2.5), (7.5, 2.5), (8.0, 4.0), (8.5, 2.5), (9.0, 2.4),
        (9.5, 1.0),  # letzte Sekunde — ausgeschlossen
    ]
    r = _compute(samples, 10.0)
    assert r is not None
    assert r == pytest.approx(2.5, abs=0.1), (
        f"Median sollte ~2,5 sein (Ausreißer 4,0 gefiltert), war {r}")
    assert r <= 3.0, "Band müsste freigegeben werden"


def test_t2_genuine_bad_match_stays_blocked():
    """T2: Echt schlechtes Match (4,x durchweg) → Median > Limit → gesperrt."""
    samples = [
        (0.5, 30.0), (3.0, 8.0),
        (7.1, 4.2), (7.5, 4.0), (8.0, 4.5), (8.5, 4.1), (9.0, 4.0),
    ]
    r = _compute(samples, 10.0)
    assert r is not None
    assert r > 3.0, f"Echt schlechtes Match muss > Limit bleiben, war {r}"


def test_t3_too_few_samples_returns_none():
    """T3: < 3 Samples im Fenster → None (Hardware-Sicherheit R1-F3)."""
    samples = [(0.5, 30.0), (3.0, 5.0), (8.0, 2.3)]  # nur 1 im Fenster 7-9
    r = _compute(samples, 10.0)
    assert r is None, "Bei < 3 Samples muss None zurückkommen (Band gesperrt)"


def test_t4_empty_window_returns_none():
    """T4: Gar keine Samples im Fenster → None."""
    samples = [(0.5, 30.0), (3.0, 5.0), (5.0, 3.0)]  # alle vor Fenster 7-9
    r = _compute(samples, 10.0)
    assert r is None


def test_t5_15s_tune_window_12_14():
    """T5: 15s Tune → Fenster [12s, 14s]."""
    samples = [
        (11.0, 5.0),  # vor Fenster
        (12.1, 2.0), (12.5, 2.1), (13.0, 2.0), (13.5, 2.2),  # im Fenster
        (14.5, 1.0),  # nach Fenster (letzte Sekunde)
    ]
    r = _compute(samples, 15.0)
    assert r is not None
    assert r == pytest.approx(2.05, abs=0.1)


def test_t6_window_boundaries_exclusive():
    """T6: Grenzen — 6,9s raus, 7,0s drin, 9,0s drin, 9,1s raus (10s Tune)."""
    samples = [
        (6.9, 99.0),  # raus (vor win_start=7)
        (7.0, 2.0), (8.0, 2.5), (9.0, 3.0),  # drin
        (9.1, 99.0),  # raus (nach win_end=9)
    ]
    r = _compute(samples, 10.0)
    assert r == pytest.approx(2.5, abs=0.01), (
        f"Median der 3 Fenster-Werte (2,0/2,5/3,0) = 2,5, war {r}")


def test_t7_short_tune_window_clamped():
    """T7: Kurze Tune-Dauer (3s) → win_start=max(0, 0)=0 → Fenster [0, 2]."""
    samples = [
        (0.1, 30.0), (0.5, 5.0), (1.0, 3.0), (1.5, 2.8),  # im Fenster [0,2]
        (2.5, 1.0),  # nach Fenster
    ]
    r = _compute(samples, 3.0)
    # 4 Werte 30/5/3/2,8 → Median = (3,0+5,0)/2 = 4,0
    assert r is not None
    assert r == pytest.approx(4.0, abs=0.1)


# ---------------------------------------------------------------------------
# Source-Inspektion: _tune_stop nutzt Helper + is-None-Check
# ---------------------------------------------------------------------------

def _tune_stop_body():
    m = re.search(r"def _tune_stop\(self, token.*?(?=\n    def )", MW_TX_SRC, re.S)
    assert m is not None, "_tune_stop nicht gefunden"
    return m.group(0)


def test_t8_tune_stop_uses_compute_helper():
    """T8: _tune_stop nutzt _compute_match_swr() statt radio.last_swr-Snapshot
    für den Freeze."""
    body = _tune_stop_body()
    assert "swr_after_match = self._compute_match_swr()" in body, (
        "P153: Freeze muss über _compute_match_swr (Median-Fenster) laufen")
    # Der alte direkte Snapshot darf NICHT mehr die Freeze-Quelle sein
    assert "swr_after_match = self.radio.last_swr" not in body, (
        "P153: alter Snapshot-Freeze (radio.last_swr) muss ersetzt sein")


def test_t9_post_check_explicit_none_check():
    """T9 (nach P119): expliziter is-None-Check für den eingefrorenen
    Median-SWR. Nach Wegfall von Phase B lebt der Check NICHT mehr in
    _tune_stop (das friert nur ein), sondern im Post-Check
    (_tune_post_swr_check): swr_frozen kann None sein (Fenster < 3 Samples)
    → muss explizit abgefangen werden (None<float ist Python-TypeError)."""
    assert "swr_frozen is None or swr_frozen < 1.0" in MW_TX_SRC, (
        "P153/P119: Post-Check muss expliziten is-None-Check für den "
        "eingefrorenen SWR haben (None<float ist TypeError, kein False).")


def test_t10_meter_update_collects_swr_during_tune():
    """T10: _on_meter_update sammelt SWR-Werte mit Zeitstempel während TUNE."""
    # _on_meter_update ist die letzte Methode → bis Dateiende matchen.
    m = re.search(r"def _on_meter_update.*", MW_TX_SRC, re.S)
    assert m is not None
    body = m.group(0)
    assert "_tune_swr_samples.append" in body, (
        "P153: SWR-Branch muss Samples während TUNE sammeln")
    assert "self._tune_active and hasattr(self, '_tune_start_time')" in body


def test_t11_tune_start_inits_collection():
    """T11: _tune_start initialisiert die Sammlung — seit P154 über den
    zentralen Helper `_init_tune_swr_sampling`, der die 3 Zeilen hält."""
    m = re.search(r"def _tune_start\(self, duration_s.*?(?=\n    def )", MW_TX_SRC, re.S)
    assert m is not None
    body = m.group(0)
    assert "self._init_tune_swr_sampling(duration_s)" in body, (
        "P154: _tune_start nutzt jetzt den zentralen Helper für die Init")
    # Helper selbst hält die 3 Init-Zeilen
    hm = re.search(r"def _init_tune_swr_sampling.*?(?=\n    def )", MW_TX_SRC, re.S)
    assert hm is not None, "_init_tune_swr_sampling-Helper nicht gefunden"
    hbody = hm.group(0)
    assert "self._tune_swr_samples" in hbody
    assert "self._tune_duration_s = duration_s" in hbody
    assert "self._tune_start_time = time.time()" in hbody


def test_t12_compute_helper_window_and_min_samples():
    """T12: _compute_match_swr hat Fenster-Logik + >= 3 Samples + statistics.median."""
    m = re.search(r"def _compute_match_swr.*?(?=\n    def )", MW_TX_SRC, re.S)
    assert m is not None
    body = m.group(0)
    assert "dur - 3.0" in body and "dur - 1.0" in body, "Fenster [Dauer-3, Dauer-1]"
    assert "len(window) >= 3" in body, "R1-F3: Mindest-3-Samples-Check"
    assert "statistics.median(window)" in body, "Median (nicht Min)"
    assert "return None" in body, "R1-F6: None statt Snapshot-Fallback"
    # KEIN echter Fallback-RETURN auf radio.last_swr im Helper (Docstring-
    # Erwähnung erlaubt — nur die ausführbare Zeile darf nicht da sein).
    assert "return self.radio.last_swr" not in body, (
        "P153 R1-F6: Helper darf NICHT auf radio.last_swr zurückfallen")


def test_t13_p153_comment_with_field_date():
    """T13: P153-Kommentar mit Mike-Field-Bug-Datum 28.05.2026 im Code."""
    assert "P153" in MW_TX_SRC
    assert "28.05.2026" in MW_TX_SRC
