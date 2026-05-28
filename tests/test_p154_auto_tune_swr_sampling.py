"""P154 (28.05.2026, v0.98.36) — Auto-TUNE SWR-Median-Fix (Zwilling zu P153).

Mike-Field-Bug 28.05.2026:
- Screenshot: „⚠ Band 20M gesperrt — SWR 8.7" obwohl Radio-Widget live
  SWR 1.4 zeigt. Mike: „autohunt tune bekommt auch nicht den richtigen
  wert. nur manuell tune das rafft er."

Root Cause:
P153 (heute früher) baute die SWR-Sample-Sammlung für `_compute_match_swr`
(Median über stabiles Fenster) NUR in `_tune_start` ein (manueller TUNE-
Knopf). Die beiden AUTO-TUNE-Pfade haben eigenes Setup und rufen
`_tune_start` NICHT auf:
  - `_start_auto_tune_for_band_change` (mw_tx.py) — Bandwechsel-Auto-TUNE
  - `_start_dialog_tune_sequence`     (mw_radio.py) — DXTuneDialog-TUNE
→ `_tune_start_time` blieb STALE (vom letzten manuellen TUNE, evtl. anderes
Band) → `_on_meter_update` sammelte mit riesigem `_elapsed` → die neuen
Samples fielen aus dem Median-Fenster [Dauer-3s, Dauer-1s] → `_compute_match_swr`
lieferte None oder den Median ALTER Samples → falsche Band-Bewertung.

Pattern-Klasse wie P133/P134 (ein Pfad gefixt, dupliziertes Setup im
Zwilling übersehen). Hardware-Sicherheit.

Fix:
- Zentraler Helper `_init_tune_swr_sampling(duration_s)` (mw_tx.py) hält die
  3 Init-Zeilen (`_tune_swr_samples=[]`, `_tune_duration_s`, `_tune_start_time`).
- `_tune_start` + beide Auto-TUNE-Pfade rufen ihn — VOR `_tune_active=True`
  (sonst Mini-Race im `_on_meter_update`-Guard).
- R1-F1: beide Auto-Pfade resetten zusätzlich `_tune_post_check_token = None`
  (P101-Symmetrie — latenter Post-Check vom letzten manuellen TUNE dürfte
  sonst mitten im Auto-TUNE feuern → Watchdog vorzeitig scharf + stale Eval).

DeepSeek-R1 (V4-pro): PUSH FREIGEBEN, 0 Blocker. F1 (Token-Reset) eingebaut,
F2 (Gain-Mess-Snapshot-Pfad) als separates Ticket.

Tests:
- T1/T2: Helper existiert + setzt die 3 Vars
- T3: _tune_start ruft Helper
- T4/T5: _start_auto_tune_for_band_change ruft Helper + Token-Reset, VOR _tune_active
- T6/T7: _start_dialog_tune_sequence ruft Helper + Token-Reset, VOR _tune_active
- T8: Helper resettet stale Samples + setzt frische Startzeit
- T9: Bug-Szenario dynamisch — stale start_time → nach Helper landen
       frische Samples korrekt im Fenster → _compute_match_swr liefert Median
- T10: Gain-Mess-Pfad bleibt bewusst Snapshot (separates Ticket — Doku-Anker)
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MW_TX_SRC = (REPO / "ui" / "mw_tx.py").read_text()
MW_RADIO_SRC = (REPO / "ui" / "mw_radio.py").read_text()


# ---------------------------------------------------------------------------
# Source-Inspektion: Helper
# ---------------------------------------------------------------------------

def _helper_body() -> str:
    m = re.search(r"def _init_tune_swr_sampling.*?(?=\n    def )", MW_TX_SRC, re.S)
    assert m is not None, "_init_tune_swr_sampling-Helper nicht gefunden"
    return m.group(0)


def test_t1_helper_exists():
    """T1: Helper _init_tune_swr_sampling existiert mit duration_s-Param."""
    assert "def _init_tune_swr_sampling(self, duration_s" in MW_TX_SRC


def test_t2_helper_sets_three_vars():
    """T2: Helper initialisiert Sammelliste + Dauer + frische Startzeit."""
    body = _helper_body()
    assert "self._tune_swr_samples" in body
    assert "self._tune_duration_s = duration_s" in body
    assert "self._tune_start_time = time.time()" in body


def test_t3_tune_start_calls_helper():
    """T3: _tune_start (manuell) nutzt den Helper."""
    m = re.search(r"def _tune_start\(self, duration_s.*?(?=\n    def )", MW_TX_SRC, re.S)
    assert m is not None
    assert "self._init_tune_swr_sampling(duration_s)" in m.group(0)


# ---------------------------------------------------------------------------
# Source-Inspektion: Auto-TUNE-Pfad 1 (mw_tx) — Bandwechsel
# ---------------------------------------------------------------------------

def _auto_band_change_body() -> str:
    m = re.search(
        r"def _start_auto_tune_for_band_change.*?(?=\n    def )", MW_TX_SRC, re.S)
    assert m is not None, "_start_auto_tune_for_band_change nicht gefunden"
    return m.group(0)


def test_t4_band_change_calls_helper_and_resets_token():
    """T4: _start_auto_tune_for_band_change ruft Helper + resettet Token."""
    body = _auto_band_change_body()
    assert "self._init_tune_swr_sampling(duration_s)" in body, (
        "P154: Bandwechsel-Auto-TUNE muss die Sample-Sammlung initialisieren")
    assert "self._tune_post_check_token = None" in body, (
        "P154 R1-F1: latenten Post-Check-Token invalidieren (P101-Symmetrie)")


def test_t5_band_change_helper_before_tune_active():
    """T5: Helper-Aufruf VOR _tune_active=True (sonst Mini-Race im
    _on_meter_update-Guard)."""
    body = _auto_band_change_body()
    i_helper = body.find("self._init_tune_swr_sampling(duration_s)")
    i_active = body.find("self._tune_active = True")
    assert i_helper != -1 and i_active != -1
    assert i_helper < i_active, (
        "P154: _init_tune_swr_sampling muss VOR _tune_active=True stehen")


# ---------------------------------------------------------------------------
# Source-Inspektion: Auto-TUNE-Pfad 2 (mw_radio) — DXTuneDialog
# ---------------------------------------------------------------------------

def _dialog_tune_body() -> str:
    m = re.search(
        r"def _start_dialog_tune_sequence.*?(?=\n    def )", MW_RADIO_SRC, re.S)
    assert m is not None, "_start_dialog_tune_sequence nicht gefunden"
    return m.group(0)


def test_t6_dialog_tune_calls_helper_and_resets_token():
    """T6: _start_dialog_tune_sequence ruft Helper + resettet Token."""
    body = _dialog_tune_body()
    assert "self._init_tune_swr_sampling(duration_s)" in body, (
        "P154: Dialog-TUNE muss die Sample-Sammlung initialisieren")
    assert "self._tune_post_check_token = None" in body, (
        "P154 R1-F1: latenten Post-Check-Token invalidieren (P101-Symmetrie)")


def test_t7_dialog_tune_helper_before_tune_active():
    """T7: Helper-Aufruf VOR _tune_active=True."""
    body = _dialog_tune_body()
    i_helper = body.find("self._init_tune_swr_sampling(duration_s)")
    i_active = body.find("self._tune_active = True")
    assert i_helper != -1 and i_active != -1
    assert i_helper < i_active


# ---------------------------------------------------------------------------
# Dynamische Tests: Helper-Verhalten
# ---------------------------------------------------------------------------

class _FakeTX:
    """Minimal-Mock für Helper + _compute_match_swr."""
    pass


def test_t8_helper_resets_stale_state():
    """T8: Helper leert alte Samples + setzt frische Startzeit (nicht stale)."""
    from ui.mw_tx import TXMixin
    fake = _FakeTX()
    # Stale-Zustand simulieren (alter manueller TUNE)
    fake._tune_swr_samples = [(1.0, 9.9), (2.0, 8.8)]
    fake._tune_duration_s = 99
    fake._tune_start_time = time.time() - 3600.0  # 1h alt

    t0 = time.time()
    TXMixin._init_tune_swr_sampling(fake, 10)

    assert fake._tune_swr_samples == [], "Alte Samples müssen geleert sein"
    assert fake._tune_duration_s == 10, "Dauer muss neu gesetzt sein"
    assert fake._tune_start_time >= t0, (
        "Startzeit muss FRISCH sein (nicht stale 1h-Wert)")


def test_t9_bug_scenario_fresh_start_makes_window_valid():
    """T9: Bug-Reproduktion. Vorher: stale start_time → frische Messungen
    landen außerhalb des Fensters → None. Nachher (Helper): frische
    start_time → dieselben Messungen landen im Fenster → korrekter Median."""
    from ui.mw_tx import TXMixin
    fake = _FakeTX()

    # --- VORHER: stale start_time (simuliert fehlende Init im Auto-Pfad) ---
    stale_start = time.time() - 3600.0
    fake._tune_duration_s = 99            # stale Dauer vom letzten TUNE
    fake._tune_swr_samples = []
    # _on_meter_update-Logik nachbilden: elapsed = now - stale_start (riesig)
    now = time.time()
    for swr in (2.5, 2.4, 2.5, 2.6):
        elapsed = now - stale_start       # ~3600s
        fake._tune_swr_samples.append((elapsed, swr))
    # Fenster für dur=99 ist [96, 98] — die ~3600s-Samples fallen raus
    assert TXMixin._compute_match_swr(fake) is None, (
        "Stale-Zustand muss zu None führen (Bug-Reproduktion)")

    # --- NACHHER: Helper setzt frische start_time + korrekte Dauer ---
    TXMixin._init_tune_swr_sampling(fake, 10)
    fresh_start = fake._tune_start_time
    # Messungen im stabilen Fenster [7, 9] für dur=10
    for elapsed, swr in [(7.1, 2.5), (7.6, 2.4), (8.2, 2.5), (8.8, 2.6)]:
        # _on_meter_update würde elapsed = time - fresh_start anhängen;
        # wir hängen die Fenster-Werte direkt an (Logik-äquivalent).
        fake._tune_swr_samples.append((elapsed, swr))
    r = TXMixin._compute_match_swr(fake)
    assert r is not None, "Mit frischer Init muss das Fenster auswertbar sein"
    assert r == pytest.approx(2.5, abs=0.1), (
        f"Median der Fenster-Werte (~2,5) erwartet, war {r}")
    assert fresh_start >= now, "start_time muss frisch sein"


# ---------------------------------------------------------------------------
# Doku-Anker: Gain-Mess-Pfad bleibt bewusst Snapshot (separates Ticket)
# ---------------------------------------------------------------------------

def test_t10_gain_measure_path_still_snapshot_separate_ticket():
    """T10: Der Gain-Mess-TUNE (_start_dx_tuning._after_tune) nutzt weiter
    `radio.last_swr` (Snapshot). Das ist BEWUSST nicht Teil von P154
    (eigene 3s-Struktur, kein _tune_stop) — DeepSeek-F2: separates Ticket.
    Dieser Test dokumentiert die Abgrenzung (kein Regressions-Schutz für
    den Snapshot, nur Awareness-Anker)."""
    m = re.search(r"def _start_dx_tuning.*?(?=\n    def )", MW_RADIO_SRC, re.S)
    assert m is not None
    body = m.group(0)
    # Der Gain-Mess-Pfad nutzt nach wie vor radio.last_swr — wenn das
    # eines Tages auf _compute_match_swr umgestellt wird, diesen Test
    # bewusst anpassen (dann ist das separate Ticket erledigt).
    assert "self.radio.last_swr" in body, (
        "Awareness-Anker: Gain-Mess nutzt noch Snapshot (separates Ticket)")
