"""Bundle L (v0.97.38): Display-3-Auto-Move + Bypass-Button = Beenden.

Mike-Wünsche 15.05.2026 abends:
A) App-Hauptfenster automatisch auf Display 3 (Position 2944,0) bei
   jedem App-Start. Helper `MainWindow.move_to_remote_display()` mit
   defensivem `QGuiApplication.screens()`-Check (R1-F1).
B) `_on_continue_without_radio` ruft jetzt `QApplication.quit()` —
   Mike-Spec: Demo-Modus macht praktisch keinen Sinn.

Workflow V1→V2→R1→V3 mit DeepSeek-V4-pro durchgelaufen.
"""

from __future__ import annotations

import inspect
from pathlib import Path


def _read(rel: str) -> str:
    return (Path(__file__).parent.parent / rel).read_text()


# ── T1 — main.py ruft move_to_remote_display nach window.show() ────────


def test_t1_main_py_calls_move_to_remote_display():
    """AC1: main.py:main() ruft window.move_to_remote_display() nach show()."""
    src = _read("main.py")
    idx_show = src.find("window.show()")
    idx_move = src.find("window.move_to_remote_display()")
    assert idx_show > 0, "main.py: window.show() fehlt"
    assert idx_move > 0, "Bundle L: move_to_remote_display-Aufruf fehlt"
    assert idx_show < idx_move, (
        "Bundle L: move_to_remote_display muss NACH show() kommen")


# ── T2 — remote-Wrapper ruft auch move_to_remote_display ────────────────


def test_t2_remote_wrapper_calls_move_to_remote_display():
    """AC1: tools/remote/start_simpleft8_nokill.py macht das auch."""
    src = _read("tools/remote/start_simpleft8_nokill.py")
    idx_show = src.find("window.show()")
    idx_move = src.find("window.move_to_remote_display()")
    assert idx_show > 0
    assert idx_move > 0, (
        "Bundle L: move_to_remote_display fehlt im Remote-Wrapper")
    assert idx_show < idx_move


# ── T3 — Helper hat defensive Screen-Check ──────────────────────────────


def test_t3_helper_has_defensive_screen_check():
    """R1-F1: Helper iteriert QGuiApplication.screens() und prüft contains()."""
    src = _read("ui/main_window.py")
    idx_func = src.find("def move_to_remote_display")
    assert idx_func > 0, "Bundle L: move_to_remote_display-Methode fehlt"
    snippet = src[idx_func:idx_func + 1200]
    assert "QGuiApplication.screens()" in snippet, (
        "R1-F1: Defensive Screen-Check fehlt")
    assert "geom.contains" in snippet, (
        "R1-F1: contains()-Prüfung fehlt")
    assert "2944" in snippet, "Bundle L: Position 2944 fehlt"


# ── T4 — Bundle-L-Revert: Bypass ruft KEIN quit ────────────────────────


def test_t4_bypass_button_does_not_call_quit():
    """Bundle-L-Revert v0.97.40 (16.05.2026, Mike-Klärung):

    Bundle L Punkt B hatte `QApplication.quit()` in
    `_on_continue_without_radio` eingebaut — beide Buttons machten
    dann dasselbe. Mike-Klärung: „ohne Radio weiter" = Demo-Modus,
    „Beenden" = quit. Test schützt vor Wiedereinbau des Bugs.
    """
    src = _read("ui/connect_status_dialog.py")
    idx_func = src.find("def _on_continue_without_radio")
    assert idx_func > 0
    next_def = src.find("\n    def ", idx_func + 10)
    full = src[idx_func:next_def if next_def > 0 else idx_func + 2000]

    # Docstring überspringen damit nur Code-Body gegrept wird.
    doc_open = full.find('"""')
    assert doc_open > 0
    doc_close = full.find('"""', doc_open + 3)
    assert doc_close > 0, "_on_continue_without_radio: Docstring nicht schließbar"
    body = full[doc_close + 3:]

    assert "QApplication.quit()" not in body, (
        "Bundle-L-Revert: Bypass darf KEIN QApplication.quit() rufen "
        "(Demo-Modus weiter, Mike-Klärung 16.05.2026)")
    assert "self.reject()" in body, (
        "_on_continue_without_radio muss self.reject() rufen")


# ── T7 — Hotfix v0.97.39: Timer-Stop + reject() VOR quit() (nur _on_quit) ─


def test_t7_quit_timer_stop_before_quit():
    """Hotfix v0.97.39 (Mike-Crash-Report 15.05.2026 abends):

    Race-Condition zwischen `_tick_timer` (500ms) und destroyed Dialog
    nach `QApplication.quit()` führte zu SIGBUS. Fix: Timer.stop() +
    reject() VOR quit().

    Bundle-L-Revert v0.97.40: Test prüft Reihenfolge nur noch für
    `_on_quit` — `_on_continue_without_radio` hat seit Revert kein
    quit() mehr (Demo-Modus weiter, siehe T4).
    """
    src = _read("ui/connect_status_dialog.py")
    idx_func = src.find("def _on_quit")
    assert idx_func > 0, "_on_quit fehlt"
    next_def = src.find("\n    def ", idx_func + 10)
    full = src[idx_func:next_def if next_def > 0 else idx_func + 2000]

    # Docstring überspringen damit nur Code-Body gegrept wird.
    doc_open = full.find('"""')
    assert doc_open > 0
    doc_close = full.find('"""', doc_open + 3)
    assert doc_close > 0, "_on_quit: Docstring nicht schließbar"
    body = full[doc_close + 3:]

    idx_stop = body.find("_tick_timer.stop()")
    idx_reject = body.find("self.reject()")
    idx_quit = body.find("QApplication.quit()")

    assert idx_stop >= 0, "Hotfix v0.97.39: _on_quit muss `_tick_timer.stop()` rufen"
    assert idx_reject >= 0, "_on_quit: reject fehlt"
    assert idx_quit >= 0, "_on_quit: quit fehlt"
    assert idx_stop < idx_reject < idx_quit, (
        f"Hotfix v0.97.39 (_on_quit): Reihenfolge muss "
        f"Timer.stop → reject → quit sein (Race-Schutz). "
        f"Aktuell: stop={idx_stop}, reject={idx_reject}, quit={idx_quit}")


# ── T5 — APP_VERSION ist 0.97.38 ────────────────────────────────────────


def test_t5_app_version_bumped():
    """Versions-Bump 0.97.37 → 0.97.38 → 0.97.39 (Hotfix)."""
    import main as m
    assert m.APP_VERSION >= "0.97.38", (
        f"APP_VERSION sollte ≥ 0.97.38 sein, ist {m.APP_VERSION}")


# ── T6 — Revert-Kommentare vorhanden ────────────────────────────────────


def test_t6_revert_comments_present():
    """Mike-Wunsch ist temporär bis 10.06.2026. Code muss klare
    Revert-Hinweise tragen damit später leicht zu finden."""
    main_src = _read("main.py")
    assert "10.06.2026" in main_src, (
        "Bundle L: Revert-Datum-Kommentar fehlt in main.py")
    helper_src = _read("ui/main_window.py")
    assert "10.06.2026" in helper_src, (
        "Bundle L: Revert-Datum-Kommentar fehlt in MainWindow-Helper")
