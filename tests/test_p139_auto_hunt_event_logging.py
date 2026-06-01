"""P139 (26.05.2026) -- Auto-Hunt Event-Logging via debug_log.

Mike-Field-Bug (mehrfach): Auto-Hunt springt mit Verzoegerung an
(beobachtet 30-60s+, manchmal 8 Min nach SWR-Sperre). Aktuell keine
Diagnose-Daten. P139 logged kompletten Pfad von Klick bis 1. TX
via existierendes debug_log-Framework (P21).

Bedienung: Mike aktiviert Settings -> "Debug-Log schreiben" -> macht
Auto-Hunt-Lauf -> Datei ~/.simpleft8/debug_YYYY-MM-DD.log liefert
zeitstempelte HUNT-Events.

ACs:
- AC1: start_auto_hunt loggt "START band=... mode=... duration=..."
- AC2: stop_auto_hunt loggt "STOP reason=..." VOR Defer-Check
  (R1-ORANGE-Catch: deferierte Stops sonst unsichtbar)
- AC3: select_next loggt Eingangs-Parameter + Skip-Reasons +
  pre/post-Affinity-Anzahl + PICKED oder NO_CANDIDATE+Grund
- AC4: mark_pick loggt MARK_PICK call=...
- AC5: _run_auto_hunt loggt START_QSO target=... freq=... tx_even=...
- AC6: _on_tx_started loggt TX_STARTED NUR bei aktivem Auto-Hunt
- AC7: alle Hooks nutzen try/except (debug_log darf NIE crashen)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core import debug_log as dlog_mod


AUTO_HUNT = Path(__file__).parent.parent / "core" / "auto_hunt.py"
MW_CYCLE = Path(__file__).parent.parent / "ui" / "mw_cycle.py"
MW_QSO = Path(__file__).parent.parent / "ui" / "mw_qso.py"


# ---------------------------------------------------------------------------
# Source-Inspection Tests
# ---------------------------------------------------------------------------


def test_t1_start_auto_hunt_logs_event():
    """T1: start_auto_hunt enthaelt debug_log mit Kategorie HUNT."""
    src = AUTO_HUNT.read_text()
    pos = src.find("def start_auto_hunt")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    assert 'debug_log("HUNT"' in body
    assert "START band=" in body


def test_t2_stop_auto_hunt_logs_before_defer_check():
    """T2 (R1-ORANGE-Catch): STOP-Reason VOR Defer-AKTION geloggt.

    Sonst sind deferierte Stops (timer_expired, totmann_expired,
    mouse_inactive_5min) im Log unsichtbar bis QSO-Ende.

    Defer-AKTION = der `if reason in _DEFER_REASONS and ...:` Block
    der mit `return` aus stop_auto_hunt aussteigt.
    Eine `will_defer`-Hilfsvariable VOR dem Log ist erlaubt.
    """
    src = AUTO_HUNT.read_text()
    pos = src.find("def stop_auto_hunt")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    pos_log = body.find('debug_log("HUNT", f"STOP')
    # Defer-AKTION = "P122: Defer fuer" Kommentar
    pos_defer_action = body.find("P122: Defer f")
    assert pos_log > 0, "STOP-Event-Log fehlt"
    assert pos_defer_action > 0, "P122 Defer-Block-Kommentar fehlt"
    assert pos_log < pos_defer_action, (
        "P139 R1-ORANGE: STOP-Log MUSS vor Defer-Aktion stehen "
        "(sonst sind deferierte Stops unsichtbar)")
    # DEFERRED-Suffix wenn deferiert wird
    assert "DEFERRED" in body


def test_t3_select_next_logs_entry_params():
    """T3: select_next loggt Eingangs-Parameter."""
    src = AUTO_HUNT.read_text()
    pos = src.find("def select_next")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    assert 'SELECT_NEXT msgs=' in body
    assert "qso_idle=" in body and "presence=" in body


def test_t4_select_next_logs_all_early_returns():
    """T4: select_next loggt alle 4 Early-Return-Reasons."""
    src = AUTO_HUNT.read_text()
    pos = src.find("def select_next")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    for reason in ["not_active", "not_presence", "not_qso_idle",
                   "manual_override"]:
        assert f"reason={reason}" in body, (
            f"Early-Return-Log fuer {reason!r} fehlt")


def test_t5_select_next_logs_all_skip_reasons():
    """T5: select_next loggt alle Skip-Reasons in Filter-Schleife."""
    src = AUTO_HUNT.read_text()
    pos = src.find("def select_next")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    # P165: "low_snr" → "below_floor" (Mindest-SNR ist jetzt ein -26-dB-Boden).
    for reason in ["empty_call", "not_callsign", "recent_qso_cooldown",
                   "fail_cooldown", "below_floor"]:
        assert f"reason={reason}" in body, (
            f"SKIP-Log fuer {reason!r} fehlt")


def test_t6_select_next_logs_candidate_count():
    """T6 (P165): Kandidaten-Anzahl wird geloggt (Affinity-Phase entfiel)."""
    src = AUTO_HUNT.read_text()
    pos = src.find("def select_next")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    assert "CANDIDATES n=" in body


def test_t7_select_next_logs_no_candidate_with_reason():
    """T7 (R1-GELB-F2): NO_CANDIDATE-Reason wird unterschieden."""
    src = AUTO_HUNT.read_text()
    pos = src.find("def select_next")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    # Mindestens 2 Reasons: empty_list (keine CQs) + all_worked_on_band
    # (P165: ersetzte score_zero — alle Kandidaten bereits auf Band gearbeitet).
    assert "NO_CANDIDATE reason=empty_list" in body
    assert "NO_CANDIDATE reason=all_worked_on_band" in body


def test_t8_select_next_logs_picked_event():
    """T8: PICKED-Event mit allen Diagnose-Feldern."""
    src = AUTO_HUNT.read_text()
    pos = src.find("def select_next")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    assert "PICKED call=" in body
    assert "prio=" in body  # P165: score= → prio= (Tupel-Rangordnung)
    assert "tx_even=" in body
    assert "freq=" in body


def test_t9_mark_pick_logs_event():
    """T9: mark_pick loggt MARK_PICK call=..."""
    src = AUTO_HUNT.read_text()
    pos = src.find("def mark_pick")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    assert "MARK_PICK call=" in body


def test_t10_run_auto_hunt_logs_start_qso():
    """T10: _run_auto_hunt loggt START_QSO mit target/freq/tx_even."""
    src = MW_CYCLE.read_text()
    pos = src.find("def _run_auto_hunt")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    assert "START_QSO target=" in body
    assert "freq=" in body
    assert "tx_even=" in body


def test_t11_tx_started_logs_only_when_auto_hunt_active():
    """T11: TX_STARTED-Log NUR bei aktivem Auto-Hunt (kein Spam)."""
    src = MW_QSO.read_text()
    pos = src.find("def _on_tx_started")
    end = src.find("\n    def ", pos + 1)
    body = src[pos:end]
    assert "TX_STARTED" in body
    # Gating: nur bei active=True
    assert "active" in body
    assert "_auto_hunt" in body


def test_t12_all_hooks_use_try_except():
    """T12: Alle debug_log-Aufrufe in try/except (darf NIE crashen)."""
    auto_hunt_src = AUTO_HUNT.read_text()
    mw_cycle_src = MW_CYCLE.read_text()
    mw_qso_src = MW_QSO.read_text()

    for src, name in [(auto_hunt_src, "auto_hunt.py"),
                      (mw_cycle_src, "mw_cycle.py"),
                      (mw_qso_src, "mw_qso.py")]:
        # Jeder Import von debug_log fuer P139 sollte in try-Block
        # (Suche nach try gefolgt von debug_log import)
        if 'debug_log' in src and 'HUNT' in src:
            # Mindestens ein try/except-Wrapper rund um die Imports
            # (Heuristisch: try + from .debug_log oder from core.debug_log)
            assert "try:" in src, f"{name}: try/except fehlt"


# ---------------------------------------------------------------------------
# Funktionaler Mock-Test
# ---------------------------------------------------------------------------


def test_t13_start_auto_hunt_calls_debug_log_with_hunt_category():
    """T13: start_auto_hunt ruft debug_log mit Category='HUNT'."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    captured = []
    with patch.object(dlog_mod, "_enabled", True), \
         patch("core.debug_log.debug_log",
               side_effect=lambda c, m: captured.append((c, m))):
        hunt.start_auto_hunt(duration_sec=600)
    # Mindestens ein HUNT-Event mit START
    hunt_events = [(c, m) for c, m in captured if c == "HUNT"]
    assert hunt_events, f"Keine HUNT-Events geloggt: {captured}"
    assert any("START" in m for _, m in hunt_events)


def test_t14_stop_auto_hunt_logs_reason_before_defer():
    """T14: stop_auto_hunt loggt STOP-Event mit reason."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    hunt.start_auto_hunt(duration_sec=600)
    captured = []
    with patch.object(dlog_mod, "_enabled", True), \
         patch("core.debug_log.debug_log",
               side_effect=lambda c, m: captured.append((c, m))):
        hunt.stop_auto_hunt("manual_halt")
    hunt_events = [(c, m) for c, m in captured if c == "HUNT"]
    assert any("STOP" in m and "manual_halt" in m for _, m in hunt_events), (
        f"STOP-Event mit reason=manual_halt fehlt: {hunt_events}")


def test_t15_select_next_logs_select_next_event():
    """T15: select_next loggt SELECT_NEXT-Eingangsdaten."""
    from core.auto_hunt import AutoHunt
    hunt = AutoHunt()
    hunt.set_band("20m")
    hunt.set_mode("FT8")
    hunt.start_auto_hunt(duration_sec=600)
    captured = []
    with patch.object(dlog_mod, "_enabled", True), \
         patch("core.debug_log.debug_log",
               side_effect=lambda c, m: captured.append((c, m))):
        hunt.select_next(messages=[], qso_idle=True, presence_ok=True)
    hunt_events = [(c, m) for c, m in captured if c == "HUNT"]
    assert any("SELECT_NEXT" in m for _, m in hunt_events), (
        f"SELECT_NEXT-Event fehlt: {hunt_events}")
