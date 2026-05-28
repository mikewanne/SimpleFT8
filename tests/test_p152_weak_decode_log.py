"""P152 (28.05.2026) — Weak-Decode-Log: schwache Decodes (SNR <= -21 dB) sammeln.

Mike-Wunsch: nach P150 (kMin_score 10->4) sehen wir mehr tiefe Decodes
(Mike sah live -25 dB auf ANT2). Keine Vorher-Werte → ab jetzt jeden
schwachen Decode in eigene Liste schreiben, empirischer Beweis.

Mike-Wahl (AskUserQuestion): eigene Datei, immer an, Schwelle <= -21 dB.
R1-V4-pro: Batching (1 File-Append/Slot), snr-None-Check, UTC, keep_days=7.

Tests:
- T1: Threshold-Konstante = -21
- T2: log_weak_decodes schreibt korrektes Format
- T3: Batching — mehrere Einträge in EINEM Append
- T4: leere Liste → no-op (keine Datei)
- T5: silent-fail bei Disk-Fehler
- T6: cleanup_old_files löscht alte, behält neue
- T7: Hook in mw_cycle filtert nur <= -21 + snr-None-Defensive
- T8: Hook ist batched (eine log_weak_decodes-Liste statt Schleife)
- T9: main.py ruft cleanup_old_files
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MW_CYCLE_SRC = (REPO / "ui" / "mw_cycle.py").read_text()
MAIN_SRC = (REPO / "main.py").read_text()


def test_t1_threshold_constant():
    from core import weak_decode_log as wdl
    assert wdl.WEAK_SNR_THRESHOLD == -21


def test_t2_log_format(tmp_path, monkeypatch):
    from core import weak_decode_log as wdl
    monkeypatch.setattr(wdl, "LOG_DIR", tmp_path)
    wdl.log_weak_decodes([(-24, "DL1ABC OE5XYZ -15", 1234)], "20m", "FT8")
    files = list(tmp_path.glob("weak_decodes_*.log"))
    assert len(files) == 1
    content = files[0].read_text()
    # Format: HH:MM:SS | -24 dB | DL1ABC OE5XYZ -15 | 1234 Hz | 20m FT8
    assert "-24 dB" in content
    assert "DL1ABC OE5XYZ -15" in content
    assert "1234 Hz" in content
    assert "20m FT8" in content
    assert re.search(r"\d\d:\d\d:\d\d \| -24 dB \| ", content)


def test_t3_batching_single_append(tmp_path, monkeypatch):
    """Mehrere Einträge landen in EINER Datei mit je einer Zeile."""
    from core import weak_decode_log as wdl
    monkeypatch.setattr(wdl, "LOG_DIR", tmp_path)
    entries = [
        (-22, "CALL1 ME -10", 800),
        (-24, "CALL2 ME RR73", 1500),
        (-21, "CQ DX CALL3 JN01", 2100),
    ]
    wdl.log_weak_decodes(entries, "15m", "FT8")
    files = list(tmp_path.glob("weak_decodes_*.log"))
    assert len(files) == 1
    lines = files[0].read_text().strip().split("\n")
    assert len(lines) == 3
    assert "CALL1 ME -10" in lines[0]
    assert "CALL2 ME RR73" in lines[1]
    assert "CQ DX CALL3 JN01" in lines[2]


def test_t4_empty_entries_noop(tmp_path, monkeypatch):
    from core import weak_decode_log as wdl
    monkeypatch.setattr(wdl, "LOG_DIR", tmp_path)
    wdl.log_weak_decodes([], "20m", "FT8")
    assert list(tmp_path.glob("weak_decodes_*.log")) == []


def test_t5_silent_fail(monkeypatch):
    """Disk-Fehler darf nicht crashen."""
    from core import weak_decode_log as wdl
    monkeypatch.setattr(wdl, "LOG_DIR", Path("/nonexistent/cannot/create/xyz"))
    # darf nicht werfen
    wdl.log_weak_decodes([(-23, "X Y -10", 1000)], "20m", "FT8")


def test_t6_cleanup_old_files(tmp_path, monkeypatch):
    from core import weak_decode_log as wdl
    monkeypatch.setattr(wdl, "LOG_DIR", tmp_path)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    old = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d")
    recent = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
    (tmp_path / f"weak_decodes_{today}.log").write_text("x")
    (tmp_path / f"weak_decodes_{old}.log").write_text("x")
    (tmp_path / f"weak_decodes_{recent}.log").write_text("x")
    deleted = wdl.cleanup_old_files(keep_days=7)
    assert deleted == 1  # nur die 10-Tage-alte
    remaining = {f.name for f in tmp_path.glob("weak_decodes_*.log")}
    assert f"weak_decodes_{today}.log" in remaining
    assert f"weak_decodes_{recent}.log" in remaining
    assert f"weak_decodes_{old}.log" not in remaining


def test_t7_hook_filters_threshold_and_none():
    """Hook in _on_cycle_decoded filtert <= Threshold + snr-None-Defensive."""
    m = re.search(r"def _on_cycle_decoded.*?(?=\n    def )", MW_CYCLE_SRC, re.S)
    assert m is not None
    body = m.group(0)
    assert "_wdl.WEAK_SNR_THRESHOLD" in body
    assert "getattr(_m, 'snr', None) is not None" in body, (
        "snr-None-Defensive (R1) fehlt")
    assert "_m.snr <= _wdl.WEAK_SNR_THRESHOLD" in body


def test_t8_hook_is_batched():
    """Hook ruft log_weak_decodes EINMAL mit Liste (batched), nicht in Schleife."""
    m = re.search(r"def _on_cycle_decoded.*?(?=\n    def )", MW_CYCLE_SRC, re.S)
    body = m.group(0)
    assert "_wdl.log_weak_decodes(_weak" in body, (
        "P152 R1: batched-Aufruf (Liste) erwartet, nicht pro-Decode")


def test_t9_main_calls_cleanup():
    assert "weak_decode_log" in MAIN_SRC
    assert "cleanup_old_files(keep_days=7)" in MAIN_SRC
