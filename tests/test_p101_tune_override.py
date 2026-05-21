"""P101 (21.05.2026, v0.97.73) — TUNE-Override Variante B + Diagnose-Prints.

Mike-Field-Test 21.05.: Rechtsklick TUNE → Sekunden-Auswahl startete kein
TUNE. Plus Spec: 2. Rechtsklick während laufendem TUNE soll Dauer
UMSCHALTEN (Mike: „in einem Rutsch") — nicht stoppen.

Tests:
- T1: _on_tune_override Source enthält Diagnose-Prints (4 Stellen)
- T2: _on_tune_override nutzt _tune_active (nicht btn.isChecked) als Guard
- T3: _on_tune_override hat KEIN frühes return im Stop-Pfad (Variante B)
- T4: control_panel _emit_override Helper für Menu-Action existiert
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(rel: str) -> str:
    return (Path(__file__).resolve().parent.parent / rel).read_text(
        encoding="utf-8")


def test_t1_override_has_debug_log_calls():
    """P101+P102: Diagnose über debug_log() — dauerhaft im Code,
    schaltbar via Settings (Mike-Anweisung 21.05.: nicht jedes Mal
    rausnehmen)."""
    src = _read("ui/mw_tx.py")
    m = re.search(r"def _on_tune_override\(self, duration_s: int\):.*?(?=\n    def )",
                  src, re.DOTALL)
    assert m, "_on_tune_override nicht gefunden"
    body = m.group(0)
    # Mindestens 3 debug_log-Aufrufe zur Signal-Verifikation
    assert body.count("debug_log(") >= 3, (
        f"P101 Diagnose: erwartet ≥3 debug_log() in _on_tune_override, "
        f"gefunden {body.count('debug_log(')}")
    assert '"P101"' in body, "P101-Tag in debug_log-Aufrufen"


def test_t2_override_checks_tune_active_not_isChecked():
    """Mike-Field-Test-Bug: btn.isChecked() kann nach Auto-Stop-Race stale True
    sein → P101 muss _tune_active als Wahrheit nehmen."""
    src = _read("ui/mw_tx.py")
    m = re.search(r"def _on_tune_override\(self, duration_s: int\):.*?(?=\n    def )",
                  src, re.DOTALL)
    body = m.group(0)
    # Logik-Guard muss _tune_active nutzen
    assert "_tune_active" in body, "P101: _tune_active als Guard"


def test_t3_override_no_early_return_on_active_stop():
    """Variante B: bei aktivem TUNE wird gestoppt UND danach neu gestartet —
    nicht mit `return` abgebrochen wie in P95."""
    src = _read("ui/mw_tx.py")
    m = re.search(r"def _on_tune_override\(self, duration_s: int\):.*?(?=\n    def )",
                  src, re.DOTALL)
    body = m.group(0)
    # Code MUSS am Ende _tune_start aufrufen — unabhängig vom vorherigen
    # _tune_active-Zustand.
    assert "_tune_start(duration_s)" in body, (
        "P101: _tune_start muss in jedem Pfad aufgerufen werden (Variante B)")
    # Defensive: alter return-Pfad nach `_tune_stop(None)` darf nicht da sein
    stop_idx = body.find("_tune_stop(None)")
    if stop_idx >= 0:
        after_stop = body[stop_idx:]
        # Vor dem nächsten _tune_start darf KEIN `return` stehen
        start_idx = after_stop.find("_tune_start")
        if start_idx >= 0:
            between = after_stop[:start_idx]
            assert "return" not in between, (
                "P101: alter early-return nach _tune_stop muss raus")


def test_t4_tune_start_clears_post_check_token_and_fwdpwr():
    """R1 Final-Catch: _tune_start muss latenten Post-Check-Token + FWDPWR-
    Samples vom vorherigen TUNE leeren, sonst Race bei Override-Restart."""
    src = _read("ui/mw_tx.py")
    m = re.search(r"def _tune_start\(self, duration_s: int\):.*?(?=\n    def )",
                  src, re.DOTALL)
    assert m, "_tune_start nicht gefunden"
    body = m.group(0)
    assert "_tune_post_check_token = None" in body, (
        "P101 Final-R1: _tune_start muss alten Post-Check-Token canceln")
    assert "_fwdpwr_samples" in body and "clear()" in body, (
        "P101 Final-R1: _fwdpwr_samples vom alten TUNE muss geleert werden")


def test_t5_menu_action_has_emit_helper_with_debug_log():
    """control_panel.py menu-action emit-Helper mit debug_log statt print."""
    src = _read("ui/control_panel.py")
    assert "_emit_override" in src, (
        "P101: Helper-Funktion _emit_override im Menu-Action existiert")
    m = re.search(r"def _emit_override\(s: int\):.*?(?=\n        for )",
                  src, re.DOTALL)
    assert m, "_emit_override im Menu-Action gefunden"
    body = m.group(0)
    assert "debug_log(" in body, "P102: debug_log statt print (dauerhaft)"
    assert '"P101"' in body, "P101-Tag in debug_log"
