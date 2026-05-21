"""P111 (21.05.2026, v0.97.88) — "99" raus aus max_calls-Dropdown.

Mike-Beobachtung 21.05.: Wahl "99 = quasi-endlos" im Settings-Dropdown ist
irreführend — MAX_STATION_CALLS=7 in qso_state.py ist Hard-Cap. Effektiv
identisch mit Wahl 7. Sauberer: 99 raus.

Migration: alte Settings mit max_calls=99 fallen beim Load auf Default 5
(via dict.get-Fallback).

Tests:
- T1: Dropdown enthält nur 3/5/7
- T2: Hint-Text erwähnt kein "99 = quasi-endlos"
- T3: Mapping in setCurrentIndex enthält keinen 99-Eintrag
- T4: Alte Settings mit 99 fallen auf Default-Index 1 (=5)
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(rel: str) -> str:
    return (Path(__file__).resolve().parent.parent / rel).read_text(
        encoding="utf-8")


def test_t1_dropdown_only_3_5_7():
    """addItems-Liste enthält nur 3, 5, 7 (kein 99)."""
    src = _read("ui/settings_dialog.py")
    m = re.search(
        r'self\.max_calls_combo\.addItems\(\["3",\s*"5",\s*"7"\]\)',
        src,
    )
    assert m, "P111: addItems muss exakt ['3', '5', '7'] sein"
    # 99 darf in addItems nicht mehr vorkommen
    bad = re.search(
        r'self\.max_calls_combo\.addItems\([^)]*"99"[^)]*\)',
        src,
    )
    assert not bad, "P111: '99' darf nicht mehr in addItems stehen"


def test_t2_hint_no_99_quasi_endless():
    """Hint-Text darf '99 = quasi-endlos' nicht mehr enthalten."""
    src = _read("ui/settings_dialog.py")
    assert "99 = quasi-endlos" not in src, (
        "P111: Hint 'quasi-endlos' muss entfernt sein")


def test_t3_index_mapping_has_no_99():
    """Mapping setCurrentIndex({...}.get(mc, 1)) enthält kein 99: 3."""
    src = _read("ui/settings_dialog.py")
    m = re.search(
        r"\{3:\s*0,\s*5:\s*1,\s*7:\s*2\}\.get\(mc,\s*1\)",
        src,
    )
    assert m, ("P111: Mapping muss exakt {3: 0, 5: 1, 7: 2}.get(mc, 1) "
               "sein (ohne 99-Eintrag)")
    # 99 darf nicht im Mapping stehen
    bad = re.search(
        r"\{[^}]*99:\s*\d+[^}]*\}\.get\(mc",
        src,
    )
    assert not bad, "P111: '99: N' darf nicht mehr im Mapping stehen"


def test_t4_legacy_99_falls_to_default():
    """Wenn settings.max_calls=99 gespeichert ist, fällt setCurrentIndex auf 1 (=5)."""
    # Reines Logic-Check: {3:0, 5:1, 7:2}.get(99, 1) === 1
    mapping = {3: 0, 5: 1, 7: 2}
    assert mapping.get(99, 1) == 1, "Migration alt 99 → Default Index 1 (=5)"
