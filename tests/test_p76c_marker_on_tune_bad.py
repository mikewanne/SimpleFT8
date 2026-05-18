"""P76-C (v0.97.50): TUNE-bad setzt Band-Marker proaktiv.

Mike-Field-Test 18.05.: Mit SWR-Limit=1.5 + TUNE auf 40m → TUNE schlaegt
fehl (SWR 2.0 > 1.5) → korrekter Hinweis im Log, aber CQ blieb klickbar.
TX startet → P53-Watchdog feuert beim ersten TX-Versuch.

Mike-Spec: Marker MUSS schon nach TUNE-bad gesetzt sein, vor jedem
TX-Versuch. Freischaltung durch manuellen TUNE (zur Diagnostik) oder
Bandwechsel.

Fix: In `_tune_post_swr_check` else-Branch (SWR-bad) `_swr_blocked_bands.add(band)`
wenn `tuner_present=True`. Pattern uebernommen aus `_on_swr_alarm`.

T1-T10.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock


def _read(path: str) -> str:
    return (Path(__file__).parent.parent / path).read_text()


def _method_src(file_rel: str, method_name: str) -> str:
    text = _read(file_rel)
    pattern = rf"    def {method_name}\([^)]*\)[^\n]*:.*?(?=\n    def |\nclass |\Z)"
    m = re.search(pattern, text, flags=re.DOTALL)
    if not m:
        raise AssertionError(f"Methode {method_name} nicht in {file_rel}")
    return m.group(0)


# ── Functional Helper ──────────────────────────────────────────────────


def _make_post_check_mock(swr_frozen=2.0, swr_limit=1.5,
                           tuner_present=True, is_auto=False, band="40m"):
    """Mock-Self fuer _tune_post_swr_check-Tests."""
    obj = MagicMock()
    obj._tune_post_check_token = object()
    obj._tune_in_progress = True
    obj._auto_tune_running = is_auto
    obj._auto_tune_dialog = MagicMock() if is_auto else None
    obj.radio.ip = "192.168.1.1"
    obj.radio.last_swr = swr_frozen
    obj.radio.radio_type = "flexradio"
    obj._tune_last_valid_swr = swr_frozen  # P76-A
    obj.settings.get = MagicMock(side_effect=lambda k, d=None: {
        "swr_limit": swr_limit,
        "tuner_present": tuner_present,
    }.get(k, d))
    obj.settings.band = band
    obj.settings.mode = "FT8"
    obj._fwdpwr_samples = []
    obj._swr_blocked_bands = set()
    obj._rx_mode = "normal"
    obj._diversity_ctrl = MagicMock(scoring_mode="normal")
    obj._tune_converged_rf = None
    obj._rfpower_current = 50
    return obj


# ── T1 — Manueller TUNE-bad mit Tuner → Marker gesetzt ─────────────────


def test_t1_manual_tune_bad_with_tuner_sets_marker():
    from ui import mw_tx
    obj = _make_post_check_mock(
        swr_frozen=2.0, swr_limit=1.5, tuner_present=True, is_auto=False
    )
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    assert "40M" in obj._swr_blocked_bands, (
        "P76-C T1: Band-Marker MUSS nach TUNE-bad gesetzt sein "
        "(tuner_present=True)")


# ── T2 — Auto-Tune-bad mit Tuner → Marker gesetzt (F2 Konsistenz) ──────


def test_t2_auto_tune_bad_with_tuner_sets_marker():
    from ui import mw_tx
    obj = _make_post_check_mock(
        swr_frozen=2.0, swr_limit=1.5, tuner_present=True, is_auto=True
    )
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    assert "40M" in obj._swr_blocked_bands, (
        "P76-C T2: Auto-Tune-Pfad MUSS auch Marker setzen (R1-F02)")


# ── T3 — TUNE-bad ohne Tuner → KEIN Marker (P63-Konsistenz) ────────────


def test_t3_tune_bad_no_tuner_no_marker():
    from ui import mw_tx
    obj = _make_post_check_mock(
        swr_frozen=2.0, swr_limit=1.5, tuner_present=False, is_auto=False
    )
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    assert "40M" not in obj._swr_blocked_bands, (
        "P76-C T3: ohne Tuner kein Marker (P63-Konsistenz mit _on_swr_alarm)")


# ── T4 — TUNE-OK nach TUNE-bad → Marker discarded (Regression P63 AC6) ─


def test_t4_tune_ok_discards_marker_regression():
    from ui import mw_tx
    obj = _make_post_check_mock(
        swr_frozen=1.5, swr_limit=2.5, tuner_present=True, is_auto=False
    )
    # Vorher Marker bereits gesetzt
    obj._swr_blocked_bands.add("40M")
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    assert "40M" not in obj._swr_blocked_bands, (
        "P76-C T4 Regression: TUNE-OK muss Marker freigeben (P63 AC6)")


# ── T5 — Text mit Tuner enthaelt „Band X gesperrt" ─────────────────────


def test_t5_text_with_tuner_says_band_gesperrt():
    from ui import mw_tx
    obj = _make_post_check_mock(
        swr_frozen=2.0, swr_limit=1.5, tuner_present=True, is_auto=False
    )
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    add_info_calls = obj.qso_panel.add_info.call_args_list
    found = any("Band 40M gesperrt" in str(c) for c in add_info_calls)
    assert found, (
        f"P76-C T5: Text mit Tuner muss 'Band 40M gesperrt' enthalten. "
        f"Calls: {add_info_calls}")


# ── T6 — Text ohne Tuner enthaelt „Tuner konnte nicht matchen" ─────────


def test_t6_text_no_tuner_says_tuner_match():
    from ui import mw_tx
    obj = _make_post_check_mock(
        swr_frozen=2.0, swr_limit=1.5, tuner_present=False, is_auto=False
    )
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    add_info_calls = obj.qso_panel.add_info.call_args_list
    found = any("Tuner konnte nicht matchen" in str(c) for c in add_info_calls)
    assert found, (
        f"P76-C T6: Text ohne Tuner muss 'Tuner konnte nicht matchen' "
        f"enthalten. Calls: {add_info_calls}")


# ── T7 — Source-Level: Marker-Set im else-Branch ───────────────────────


def test_t7_source_marker_set_in_else_branch():
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    # Else-Branch finden NACH `if swr_now <= swr_limit:` (nicht den P76-A inner else)
    swr_if_idx = src.find("if swr_now <= swr_limit:")
    assert swr_if_idx > 0, "P76-C T7: SWR-Check if nicht gefunden"
    # Suche else AB der if-Position (8 Leerzeichen Einrueckung des SWR-if)
    else_idx = src.find("\n        else:\n", swr_if_idx)
    assert else_idx > 0, "P76-C T7: SWR-else-Branch nicht gefunden"
    else_block = src[else_idx:]
    assert "_swr_blocked_bands.add" in else_block, (
        "P76-C T7: `_swr_blocked_bands.add` MUSS im SWR-bad else-Branch sein")
    assert "P76-C" in else_block, "P76-C T7: Marker-Kommentar fehlt"


# ── T8 — Source-Level: kein Marker-Set im if-Branch (TUNE-OK) ──────────


def test_t8_source_no_marker_set_in_if_branch():
    """Im TUNE-OK-Branch darf nur `discard` (Freischaltung), nicht `add`."""
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    swr_if_idx = src.find("if swr_now <= swr_limit:")
    else_idx = src.find("\n        else:\n", swr_if_idx)
    if_block = src[swr_if_idx:else_idx]
    # Im if-Branch (TUNE-OK) MUSS `_swr_blocked_bands.discard` sein
    assert "_swr_blocked_bands.discard" in if_block, (
        "P76-C T8: TUNE-OK-Branch muss discard machen (P63 AC6)")
    # Aber KEIN .add (das gehoert in else)
    assert "_swr_blocked_bands.add" not in if_block, (
        "P76-C T8: TUNE-OK-Branch darf KEIN .add machen")


# ── T9 — Source-Level: kein set_tx_antenna im P76-C-Block ──────────────


def test_t9_source_no_antenna_change_in_p76c_block():
    """ANT1-Hardware-Pflicht: P76-C-Block darf Antenne nicht umschalten."""
    src = _method_src("ui/mw_tx.py", "_tune_post_swr_check")
    # P76-C-Block extrahieren (else-Branch nach Marker)
    p76c_match = re.search(
        r"# P76-C.*?qso_panel\.add_info",
        src, flags=re.DOTALL)
    assert p76c_match, "P76-C T9: P76-C-Block nicht gefunden"
    assert "set_tx_antenna" not in p76c_match.group(0), (
        "P76-C T9 ANT1-Pflicht: kein set_tx_antenna im neuen P76-C-Block")


# ── T10 — Idempotenz: 2x TUNE-bad → Marker bleibt 1x drin ──────────────


def test_t10_idempotent_marker_add():
    from ui import mw_tx
    obj = _make_post_check_mock(
        swr_frozen=2.0, swr_limit=1.5, tuner_present=True, is_auto=False
    )
    # 1. TUNE-bad
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    assert obj._swr_blocked_bands == {"40M"}

    # 2. TUNE-bad (selbes Band)
    obj._tune_post_check_token = object()  # neuer Token
    obj._tune_last_valid_swr = 2.0  # neu setzen weil Post-Check Reset
    mw_tx.TXMixin._tune_post_swr_check(obj, obj._tune_post_check_token)
    assert obj._swr_blocked_bands == {"40M"}, (
        f"P76-C T10: Idempotent — 2x TUNE-bad → 1x Marker. "
        f"Got: {obj._swr_blocked_bands}")
