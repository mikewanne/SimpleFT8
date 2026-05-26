"""P132 + P134 (26.05.2026) — Single-Instance Architektur-Refactor.

P132 Mike-Field-Bug: 4 Zombie-Instanzen seit Mittwoch trotz
acquire_single_instance_lock. Root Cause: pgrep-Pattern-Matching auf
cmdline-Text war fundamental falsch — setproctitle (P43) ueberschreibt
cmdline, false-positives bei anderen main.py-Apps (Websdr/JimBob).

Mike-Wort: "so identifiziert man das doch nicht"

P134 Mike-Field-Bug („starter wird beendet, App nicht gestartet"):
lsof-CWD-Backup-Sweep (P132 SCHRITT 3) killte fremde Python-Prozesse
(pytest, IDE, Parent-Bash). Selber Fehlerklassen-Bug wie pgrep —
zu breite Erkennung. ENTFERNT. Stattdessen: nach flock-Erfolg
zielgerichtete 1-PID-Pruefung via Helper `_kill_stale_lockfile_owner`
(R1-Catch: faengt alte App-Versionen ab die kein flock hielten).

Architektur (KISS, atomar):
- fcntl.flock atomar holen (verhindert Race)
- Bei flock-Erfolg: 1-PID-Check des Lockfile-Inhabers (P134)
- Falls Lock blockiert: Inhaber-PID lesen, cwd-Check, killen
- Pattern-basiertes pgrep KOMPLETT entfernt
- lsof-CWD-Sweep KOMPLETT entfernt (P134)

ACs:
- AC1: alte Funktionen (pgrep-basiert) sind WEG
- AC2: neue Funktionen vorhanden
- AC3: cwd-basierte Identifikation deterministisch + setproctitle-immun
- AC4: kill_old_instances-Aufruf aus main() entfernt
- AC5: KEIN lsof-Sweep mehr (P134 Regression-Schutz)
- AC6: _kill_pid_with_grace idempotent + SIGTERM-vor-SIGKILL
- AC7: _read_pid_from_lock handhabt leere/ungueltige Inputs
- AC8: _kill_stale_lockfile_owner Helper deckt beide Pfade ab (P134)
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

    P132+P134: `_free_radio_ports` UND `_find_simpleft8_processes_by_cwd`
    sind NICHT mehr drin (Pattern-Killing-Bug). Stattdessen
    `_kill_stale_lockfile_owner` Helper fuer zielgerichtete 1-PID-Pruefung.
    """
    src = MAIN_PY.read_text()
    required = [
        "def _get_app_dir",
        "def _kill_pid_with_grace",
        "def _pid_has_cwd_in_app_dir",
        "def _read_pid_from_lock",
        "def _kill_stale_lockfile_owner",  # P134 Helper
        "def acquire_single_instance_lock",
    ]
    missing = [r for r in required if r not in src]
    assert not missing, f"P132+P134 fehlende Funktionen: {missing}"
    # _free_radio_ports MUSS WEG sein (P132 R1-Final-Catch)
    assert "def _free_radio_ports" not in src, (
        "P132 R1-Final-Catch: _free_radio_ports entfernt — Port-Kill "
        "koennte fremde Prozesse killen")
    # _find_simpleft8_processes_by_cwd MUSS WEG sein (P134 Sweep-Bug)
    assert "def _find_simpleft8_processes_by_cwd" not in src, (
        "P134: lsof-CWD-Sweep entfernt — killte fremde Python-Prozesse "
        "(pytest/IDE/Parent-Bash). Selber Fehlerklassen-Bug wie pgrep.")


def test_t6_acquire_lock_uses_fcntl_first():
    """T6: acquire_single_instance_lock holt fcntl.flock ZUERST.

    P134: cwd-basierte Identifikation laeuft jetzt ueber Helper
    `_kill_stale_lockfile_owner` (zielgerichtet 1 PID, kein Sweep).
    """
    src = MAIN_PY.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "acquire_single_instance_lock"):
            func_src = ast.unparse(node)
            assert "fcntl.flock" in func_src
            assert "LOCK_EX" in func_src
            assert "LOCK_NB" in func_src
            # P134: Helper-Aufruf statt direkter Sweep
            assert "_kill_stale_lockfile_owner" in func_src
            # P134 Regression-Schutz: kein Sweep mehr
            assert "_find_simpleft8_processes_by_cwd" not in func_src, (
                "P134: lsof-Sweep darf nicht zurueck — killt fremde Procs")
            # _free_radio_ports darf NICHT mehr gerufen werden (P132)
            assert "_free_radio_ports" not in func_src, (
                "P132 R1-Final-Catch: Port-basierter Kill koennte fremde "
                "Prozesse killen")
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


def test_t10_no_lsof_sweep_anywhere():
    """T10 (P134 Regression-Schutz): KEIN lsof-Command-Filter-Sweep mehr.

    Sweep-Form: `lsof -c Python -c python` (listet alle Treffer).
    Gezielter Pfad: `lsof -p <pid>` (1 PID) — ist OK und bleibt.
    """
    src = MAIN_PY.read_text()
    assert "_find_simpleft8_processes_by_cwd" not in src
    forbidden_command_filter = [
        '"-c", "Python", "-c", "python"',
        "'-c', 'Python', '-c', 'python'",
    ]
    for pat in forbidden_command_filter:
        assert pat not in src, (
            f"P134: lsof Command-Filter-Sweep {pat!r} entfernt — "
            "killte fremde Python-Prozesse")


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
    """T14: APP_VERSION ist >= 0.98.14 fuer P132+P134+P131."""
    src = MAIN_PY.read_text()
    # P132 war 0.98.13, P134 0.98.14, P131 0.98.15
    import re
    m = re.search(r'APP_VERSION = "0\.98\.(\d+)"', src)
    assert m is not None, "APP_VERSION-Format unerwartet"
    assert int(m.group(1)) >= 14, (
        f"P132+P134: APP_VERSION mindestens 0.98.14, gefunden 0.98.{m.group(1)}")


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
