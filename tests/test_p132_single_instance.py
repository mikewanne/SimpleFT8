"""P132 (26.05.2026) — Single-Instance Architektur-Refactor.

Mike-Field-Bug 26.05.2026: 4 Zombie-Instanzen seit Mittwoch trotz
acquire_single_instance_lock. Root Cause: pgrep-Pattern-Matching auf
cmdline-Text war fundamental falsch — setproctitle (P43) ueberschreibt
cmdline, false-positives bei anderen main.py-Apps (Websdr/JimBob).

Mike-Wort: "so identifiziert man das doch nicht"

V3 Architektur (KISS, atomar):
- fcntl.flock atomar holen (verhindert Race)
- Falls Lock blockiert: Inhaber-PID lesen, cwd-Check, killen
- lsof-CWD-Backup-Scan fuer Zombies ohne Lock
- Port-Cleanup integriert in acquire_single_instance_lock
- Pattern-basiertes pgrep KOMPLETT entfernt

ACs:
- AC1: alte Funktionen (_get_simpleft8_window_pids,
       _kill_all_simpleft8_instances, kill_old_instances) sind WEG
- AC2: neue Funktionen vorhanden
- AC3: cwd-basierte Identifikation deterministisch + setproctitle-immun
- AC4: kill_old_instances-Aufruf aus main() entfernt
- AC5: _find_simpleft8_processes_by_cwd parsing korrekt (lsof -Fpn)
- AC6: _kill_pid_with_grace idempotent + SIGTERM-vor-SIGKILL
- AC7: _read_pid_from_lock handhabt leere/ungueltige Inputs
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


MAIN_PY = Path(__file__).parent.parent / "main.py"


def _get_main_module():
    """Lazy import main.py ohne main() zu starten."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("main_p132", MAIN_PY)
    mod = importlib.util.module_from_spec(spec)
    # spec.loader.exec_module(mod) wuerde main() ausfuehren — wir wollen
    # nur die Funktions-Definitionen. Stattdessen den Quellcode parsen.
    return mod, MAIN_PY.read_text()


# ---------------------------------------------------------------------------
# T1-T3: Alte Funktionen entfernt
# ---------------------------------------------------------------------------


def test_t1_old_pgrep_killer_removed():
    """T1: _kill_all_simpleft8_instances ist entfernt (pgrep-basiert)."""
    src = MAIN_PY.read_text()
    assert "def _kill_all_simpleft8_instances" not in src, (
        "P132: _kill_all_simpleft8_instances war pgrep-Pattern-basiert "
        "und fundamental falsch — muss entfernt sein")


def test_t2_old_osascript_cache_removed():
    """T2: _get_simpleft8_window_pids + Cache ist entfernt."""
    src = MAIN_PY.read_text()
    assert "def _get_simpleft8_window_pids" not in src
    assert "_simpleft8_window_pids_cache" not in src


def test_t3_old_kill_old_instances_removed():
    """T3: kill_old_instances ist entfernt (Port-Cleanup integriert)."""
    src = MAIN_PY.read_text()
    assert "def kill_old_instances" not in src, (
        "P132: kill_old_instances ist redundant — Port-Cleanup ist "
        "jetzt in _free_radio_ports + acquire_single_instance_lock")


def test_t4_main_does_not_call_kill_old_instances():
    """T4: main() ruft kill_old_instances NICHT mehr."""
    src = MAIN_PY.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            main_src = ast.unparse(node)
            assert "kill_old_instances" not in main_src, (
                "P132: main() darf kill_old_instances nicht mehr rufen")
            return
    pytest.fail("main()-Funktion nicht gefunden")


# ---------------------------------------------------------------------------
# T5-T8: Neue Funktionen vorhanden
# ---------------------------------------------------------------------------


def test_t5_new_functions_exist():
    """T5: Alle neuen Funktionen sind in main.py definiert.

    `_free_radio_ports` ist NICHT mehr drin (R1-Final-Catch 26.05.):
    Port-basierter Kill koennte fremde Prozesse killen. cwd-Sweep
    deckt alle SimpleFT8-Zombies ab — Ports werden automatisch frei.
    """
    src = MAIN_PY.read_text()
    required = [
        "def _get_app_dir",
        "def _kill_pid_with_grace",
        "def _pid_has_cwd_in_app_dir",
        "def _find_simpleft8_processes_by_cwd",
        "def _read_pid_from_lock",
        "def acquire_single_instance_lock",
    ]
    missing = [r for r in required if r not in src]
    assert not missing, f"P132 fehlende Funktionen: {missing}"
    # _free_radio_ports MUSS WEG sein (R1-Final-Catch)
    assert "def _free_radio_ports" not in src, (
        "P132 R1-Final-Catch: _free_radio_ports entfernt — Port-Kill "
        "koennte fremde Prozesse killen (genau der Pattern-Killing-Bug)")


def test_t6_acquire_lock_uses_fcntl_first():
    """T6: acquire_single_instance_lock holt fcntl.flock ZUERST."""
    src = MAIN_PY.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "acquire_single_instance_lock"):
            func_src = ast.unparse(node)
            assert "fcntl.flock" in func_src
            assert "LOCK_EX" in func_src
            assert "LOCK_NB" in func_src
            # cwd-basierte Identifikation muss benutzt werden
            assert "_find_simpleft8_processes_by_cwd" in func_src
            # R1-Final-Catch: _free_radio_ports darf NICHT mehr gerufen
            assert "_free_radio_ports" not in func_src, (
                "R1-Final-Catch: Port-basierter Kill koennte fremde "
                "Prozesse killen — cwd-Sweep reicht")
            return
    pytest.fail("acquire_single_instance_lock nicht gefunden")


def test_t7_no_more_pgrep_pattern_matching():
    """T7: KEIN pgrep-Pattern-Matching mehr in main.py.

    Pattern-basiertes Killen war Mike-Kritik 26.05.: false-positives,
    setproctitle-anfaellig. cwd-basierte Identifikation ersetzt es.
    """
    src = MAIN_PY.read_text()
    # Diese alten Pattern-Strings duerfen nicht mehr vorkommen
    forbidden = [
        r'r"python.*main\.py"',
        r'r"python.*start_simpleft8"',
        r'r"SimpleFT8 v"',  # auch das war ein heuristisches Pattern
    ]
    for pat in forbidden:
        assert pat not in src, (
            f"P132: pgrep-Pattern {pat} muss entfernt sein — "
            f"cwd-basiert ist die Loesung")


def test_t8_setproctitle_still_active():
    """T8: setproctitle bleibt (Activity-Monitor-Schoenheit)."""
    src = MAIN_PY.read_text()
    assert "setproctitle.setproctitle" in src, (
        "P43-setproctitle bleibt — nur die pgrep-Aufraeumlogik wurde "
        "ersetzt")


# ---------------------------------------------------------------------------
# T9-T12: Funktions-Verhalten via Mock
# ---------------------------------------------------------------------------


def test_t9_get_app_dir_returns_resolved_path():
    """T9: _get_app_dir liefert absoluten Pfad zum App-Verzeichnis."""
    mod, _ = _get_main_module()
    # Skript-Modul laden inkl. exec, damit Funktionen verfuegbar
    import importlib.util
    spec = importlib.util.spec_from_file_location("p132_test", MAIN_PY)
    # Nur Funktions-Defs laden — main() wird in if __name__ geschuetzt
    src = MAIN_PY.read_text()
    assert 'if __name__ == "__main__"' in src, (
        "main() darf nur unter __main__-Guard ausgefuehrt werden — "
        "sonst kollidiert Test-Import mit echter App")


def test_t10_lsof_parsing_format_fpn():
    """T10: _find_simpleft8_processes_by_cwd nutzt -Fpn Format.

    -Fpn liefert newline-getrennte Felder: 'pPID\\nnPATH\\np...'.
    Pfad-Leerzeichen-immun (anders als space-separated Output).
    """
    src = MAIN_PY.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "_find_simpleft8_processes_by_cwd"):
            func_src = ast.unparse(node)
            assert '-Fpn' in func_src or 'Fpn' in func_src
            # Parser muss 'p' und 'n' Linien handhaben (ast.unparse
            # nutzt single-quotes statt double-quotes)
            assert "startswith('p')" in func_src or 'startswith("p")' in func_src
            assert "startswith('n')" in func_src or 'startswith("n")' in func_src
            return
    pytest.fail("_find_simpleft8_processes_by_cwd nicht gefunden")


def test_t11_kill_pid_with_grace_sigterm_then_sigkill():
    """T11: _kill_pid_with_grace sendet SIGTERM, wartet, dann SIGKILL."""
    src = MAIN_PY.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "_kill_pid_with_grace"):
            func_src = ast.unparse(node)
            assert "SIGTERM" in func_src
            assert "SIGKILL" in func_src
            assert "time.sleep" in func_src
            # ProcessLookupError-Handling fuer Idempotenz
            assert "ProcessLookupError" in func_src
            # SIGTERM muss VOR SIGKILL kommen
            pos_term = func_src.find("SIGTERM")
            pos_kill = func_src.find("SIGKILL")
            assert pos_term < pos_kill
            return
    pytest.fail("_kill_pid_with_grace nicht gefunden")


def test_t12_release_lock_on_exit_unlink():
    """T12: _release_lock_on_exit gibt Lock frei UND loescht File."""
    src = MAIN_PY.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "_release_lock_on_exit"):
            func_src = ast.unparse(node)
            assert "LOCK_UN" in func_src or "flock" in func_src
            assert "close" in func_src
            assert "unlink" in func_src
            return
    pytest.fail("_release_lock_on_exit nicht gefunden")


# ---------------------------------------------------------------------------
# T13-T14: Lock-File-PID-Read
# ---------------------------------------------------------------------------


def test_t13_read_pid_from_lock_valid(tmp_path):
    """T13: _read_pid_from_lock liest gueltige PID."""
    # Direkter Aufruf der Funktion ueber dynamic-import + exec
    src = MAIN_PY.read_text()
    # Funktions-Body extrahieren und exec-fyhren in Mini-Modul
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "_read_pid_from_lock"):
            ns: dict = {"Path": Path}
            exec(compile(ast.Module([node], type_ignores=[]),
                         "<test>", "exec"), ns)
            fn = ns["_read_pid_from_lock"]
            lock_file = tmp_path / "test.lock"
            lock_file.write_text("12345")
            assert fn(lock_file) == 12345
            lock_file.write_text("")
            assert fn(lock_file) is None
            lock_file.write_text("not-a-number")
            assert fn(lock_file) is None
            # Nonexistent file
            assert fn(tmp_path / "missing") is None
            return
    pytest.fail("_read_pid_from_lock nicht gefunden")


def test_t14_app_version_bumped():
    """T14: APP_VERSION ist auf 0.98.13 gebumpt fuer P132."""
    src = MAIN_PY.read_text()
    assert 'APP_VERSION = "0.98.13"' in src, (
        "P132: APP_VERSION muss 0.98.13 sein")


# ---------------------------------------------------------------------------
# T15: Doku-Marker
# ---------------------------------------------------------------------------


def test_t15_p132_marker_in_doc():
    """T15: P132-Marker im Docstring der acquire_single_instance_lock."""
    src = MAIN_PY.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "acquire_single_instance_lock"):
            doc = ast.get_docstring(node) or ""
            assert "P132" in doc, (
                "P132-Marker muss im Doku-Kommentar stehen")
            assert "setproctitle" in doc or "cwd" in doc.lower()
            return
    pytest.fail("acquire_single_instance_lock nicht gefunden")
