"""P134 (26.05.2026) — `_kill_stale_lockfile_owner` Helper + Sweep-Removal.

Mike-Field-Bug 26.05.: „starter.command wird beendet, App startet nicht"
nach P132. Diagnose: SCHRITT 3 (lsof-CWD-Backup-Sweep) killte fremde
Python-Prozesse (pytest/IDE/Parent-Bash) — selber Fehlerklassen-Bug wie
pgrep vor P132.

V3 (DeepSeek R1 26.05.):
- Sweep KOMPLETT entfernt
- Helper `_kill_stale_lockfile_owner` deckt 2 Pfade ab:
  a) nach flock-Erfolg (faengt alte App-Versionen ohne flock ab)
  b) nach flock-Blockade (killt aktuellen Inhaber)
- Zielgerichtet 1 PID, niemals Sweep

ACs:
- AC1: `_kill_stale_lockfile_owner` existiert
- AC2: Helper wird in beiden Pfaden in `acquire_single_instance_lock`
       gerufen (flock-Erfolg + flock-Blockade)
- AC3: Helper killt NUR wenn cwd-Match (kein Fremd-Kill)
- AC4: Helper ignoriert tote PIDs (ProcessLookupError)
- AC5: Helper ignoriert eigene PID
- AC6: Helper ignoriert leeren/ungueltigen Lockfile-Inhalt
- AC7: APP_VERSION auf 0.98.14 gebumpt
- AC8: Doku-Kommentar nennt P134 explizit
"""

from __future__ import annotations

import ast
from pathlib import Path


MAIN_PY = Path(__file__).parent.parent / "main.py"


def _find_func(name: str) -> ast.FunctionDef | None:
    src = MAIN_PY.read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


# ---------------------------------------------------------------------------
# T1-T4: Sweep-Removal Regression-Schutz
# ---------------------------------------------------------------------------


def test_t1_lsof_sweep_function_removed():
    """T1: `_find_simpleft8_processes_by_cwd` ist KOMPLETT entfernt."""
    src = MAIN_PY.read_text()
    assert "def _find_simpleft8_processes_by_cwd" not in src
    assert "_find_simpleft8_processes_by_cwd(" not in src


def test_t2_no_lsof_command_filter_sweep():
    """T2: KEIN lsof mit Command-Filter (Sweep ueber ALLE Python-Procs).

    Sweep-Charakteristik: `lsof -c Python -c python` (Command-Match,
    listet alle Treffer). Gezielter Pfad ist `lsof -p <pid>` (1 PID).
    Beide nutzen `-d cwd` — Unterscheidung ist `-c` vs `-p`.
    """
    src = MAIN_PY.read_text()
    forbidden_command_filter = [
        '"-c", "Python", "-c", "python"',  # P132/P134 Sweep-Form
        "'-c', 'Python', '-c', 'python'",
    ]
    for pat in forbidden_command_filter:
        assert pat not in src, (
            f"P134: lsof Command-Filter-Sweep {pat!r} entfernt — "
            "killte fremde Python-Prozesse")


def test_t3_no_backup_scan_block_in_acquire():
    """T3: SCHRITT 3 Backup-Scan-Block ist aus `acquire_single_instance_lock` raus."""
    func = _find_func("acquire_single_instance_lock")
    assert func is not None
    src = ast.unparse(func)
    # Diese Strings waren Teil des alten Sweep-Blocks
    assert "Backup-Scan via lsof" not in src
    assert "zombies = [" not in src
    assert "Zombie PID" not in src


def test_t4_acquire_step_count_is_three():
    """T4: acquire_single_instance_lock hat jetzt 3 SCHRITTE, nicht 4+.

    Pruefung am Source-Text (ast.unparse strippt Kommentare).
    """
    src = MAIN_PY.read_text()
    start = src.find("def acquire_single_instance_lock")
    assert start > 0
    # Naechste Funktion oder EOF als Ende
    end = src.find("\ndef ", start + 1)
    if end == -1:
        end = len(src)
    func_src = src[start:end]
    assert "SCHRITT 1:" in func_src
    assert "SCHRITT 2:" in func_src
    assert "SCHRITT 3:" in func_src
    # P134 Sweep ist raus — kein SCHRITT 3: Backup mehr
    assert "SCHRITT 3: Backup" not in func_src
    assert "Backup-Scan via lsof" not in func_src


# ---------------------------------------------------------------------------
# T5-T8: Helper-Funktion vorhanden + struktural korrekt
# ---------------------------------------------------------------------------


def test_t5_helper_function_exists():
    """T5: `_kill_stale_lockfile_owner` Funktion ist definiert."""
    func = _find_func("_kill_stale_lockfile_owner")
    assert func is not None, (
        "P134: Helper-Funktion `_kill_stale_lockfile_owner` muss existieren")


def test_t6_helper_has_correct_signature():
    """T6: Helper-Signatur (app_dir: str, my_pid: int) -> bool."""
    func = _find_func("_kill_stale_lockfile_owner")
    assert func is not None
    arg_names = [a.arg for a in func.args.args]
    assert arg_names == ["app_dir", "my_pid"]


def test_t7_helper_reads_lockfile_pid():
    """T7: Helper nutzt `_read_pid_from_lock` (nicht direkt parse)."""
    func = _find_func("_kill_stale_lockfile_owner")
    src = ast.unparse(func)
    assert "_read_pid_from_lock" in src


def test_t8_helper_checks_cwd_before_kill():
    """T8: Helper prueft `_pid_has_cwd_in_app_dir` VOR `_kill_pid_with_grace`."""
    func = _find_func("_kill_stale_lockfile_owner")
    src = ast.unparse(func)
    pos_cwd_check = src.find("_pid_has_cwd_in_app_dir")
    pos_kill = src.find("_kill_pid_with_grace")
    assert pos_cwd_check > 0, "Helper muss cwd pruefen"
    assert pos_kill > 0, "Helper muss kill_with_grace nutzen"
    assert pos_cwd_check < pos_kill, (
        "P134: cwd-Check MUSS vor Kill kommen — sonst Fremd-Kill-Risiko")


def test_t9_helper_handles_dead_pid():
    """T9: Helper behandelt ProcessLookupError (tote PID)."""
    func = _find_func("_kill_stale_lockfile_owner")
    src = ast.unparse(func)
    assert "ProcessLookupError" in src


def test_t10_helper_skips_own_pid():
    """T10: Helper ignoriert eigene PID (kein Selbst-Kill)."""
    func = _find_func("_kill_stale_lockfile_owner")
    src = ast.unparse(func)
    assert "my_pid" in src
    # Muss expliziter Vergleich sein
    assert "old_pid == my_pid" in src or "my_pid == old_pid" in src


# ---------------------------------------------------------------------------
# T11-T13: Integration in acquire_single_instance_lock
# ---------------------------------------------------------------------------


def test_t11_helper_called_after_flock_success():
    """T11: Helper wird NACH erfolgreichem flock gerufen (R1-Catch).

    Faengt alte App-Versionen ab die kein flock hielten.
    """
    func = _find_func("acquire_single_instance_lock")
    src = ast.unparse(func)
    # Helper-Aufruf muss im try-Block (nach erfolgreichem flock) stehen
    assert "_kill_stale_lockfile_owner(app_dir, my_pid)" in src


def test_t12_helper_called_in_blocking_path():
    """T12: Helper wird auch im BlockingIOError-Pfad gerufen.

    Das ist der Pfad der vor P134 als Schritt 2 inline existierte.
    """
    func = _find_func("acquire_single_instance_lock")
    src = ast.unparse(func)
    # Mindestens 2 Aufrufe des Helpers (Erfolg + Blockade)
    count = src.count("_kill_stale_lockfile_owner(")
    assert count >= 2, (
        f"P134: Helper muss in beiden Pfaden gerufen werden "
        f"(found {count} Aufrufe)")


def test_t13_inline_pid_check_removed_from_acquire():
    """T13: Alte inline PID-Check-Logik aus SCHRITT 2 ist durch Helper ersetzt."""
    func = _find_func("acquire_single_instance_lock")
    src = ast.unparse(func)
    # Frueher inline: "Lebende Instanz PID" Print
    assert "Lebende Instanz PID" not in src, (
        "P134: alte inline-Logik durch Helper ersetzt — bitte Helper-"
        "Pfad nutzen")


# ---------------------------------------------------------------------------
# T14-T15: Doku + Version
# ---------------------------------------------------------------------------


def test_t14_p134_marker_in_doc():
    """T14: P134-Marker im Doku-Kommentar von acquire_single_instance_lock."""
    func = _find_func("acquire_single_instance_lock")
    doc = ast.get_docstring(func) or ""
    assert "P134" in doc, "P134-Marker muss im Doku-Kommentar stehen"
    assert "Sweep" in doc or "sweep" in doc, (
        "Doku muss Sweep-Entfernung erwaehnen")


def test_t15_app_version_bumped_to_0_98_14():
    """T15: APP_VERSION ist >= 0.98.14 fuer P134."""
    src = MAIN_PY.read_text()
    import re
    m = re.search(r'APP_VERSION = "(\d+)\.(\d+)\.(\d+)"', src)
    assert m is not None
    version = tuple(int(g) for g in m.groups())
    assert version >= (0, 98, 14), (
        f"P134: mindestens 0.98.14, gefunden {'.'.join(map(str, version))}")


# ---------------------------------------------------------------------------
# T16-T19: Dynamische Mock-Tests (Final-R1 GELB-Auflage)
# ---------------------------------------------------------------------------


def _load_helper_function():
    """Lade `_kill_stale_lockfile_owner` Funktion aus main.py via exec.

    Wir laden NICHT das ganze Modul (das wuerde main() rufen).
    Stattdessen Funktions-Body extrahieren und in Mini-Namespace
    ausfuehren mit gemockten Abhaengigkeiten.
    """
    import os as _os
    src = MAIN_PY.read_text()
    tree = ast.parse(src)
    deps = ["_read_pid_from_lock", "_pid_has_cwd_in_app_dir",
            "_kill_pid_with_grace", "_kill_stale_lockfile_owner"]
    ns: dict = {"os": _os, "_LOCK_FILE": Path("/tmp/p134_test.lock")}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in deps:
            exec(compile(ast.Module([node], type_ignores=[]),
                         "<test>", "exec"), ns)
    return ns


def _prepare_helper_ns(tmp_path, lock_content: str):
    """Helper-Namespace mit Mock-Lockfile + Mock-Kill-Tracker."""
    ns = _load_helper_function()
    lock_file = tmp_path / "lock"
    lock_file.write_text(lock_content)
    ns["_LOCK_FILE"] = lock_file
    # Helper-Funktion teilt __globals__ mit ns — wir mocken im Globals
    ns["_kill_stale_lockfile_owner"].__globals__["_LOCK_FILE"] = lock_file
    killed = []
    ns["_kill_stale_lockfile_owner"].__globals__["_kill_pid_with_grace"] = (
        lambda pid: killed.append(pid))
    return ns, killed


def test_t16_helper_skips_own_pid(tmp_path):
    """T16: Helper killt NICHT die eigene PID."""
    ns, killed = _prepare_helper_ns(tmp_path, str(os.getpid()))
    result = ns["_kill_stale_lockfile_owner"]("/tmp/foo", os.getpid())
    assert result is False
    assert killed == [], "Eigene PID darf nicht gekillt werden"


def test_t17_helper_skips_dead_pid(tmp_path):
    """T17: Helper behandelt tote PID (ProcessLookupError) sauber."""
    ns, killed = _prepare_helper_ns(tmp_path, "999999")
    result = ns["_kill_stale_lockfile_owner"]("/tmp/foo", os.getpid())
    assert result is False
    assert killed == [], "Tote PID darf nicht gekillt werden"


def test_t18_helper_skips_foreign_cwd(tmp_path):
    """T18: Helper killt NICHT bei fremdem cwd (anti-Pattern-Killing).

    Das ist der KERN-Schutz gegen den P132/P134-Bug-Klasse:
    eine lebende PID mit Lockfile-Eintrag, aber NICHT SimpleFT8.
    """
    ns, killed = _prepare_helper_ns(tmp_path, str(os.getpid()))
    # cwd-Check sagt False → Helper darf NICHT killen
    ns["_kill_stale_lockfile_owner"].__globals__["_pid_has_cwd_in_app_dir"] = (
        lambda pid, app_dir: False)
    # my_pid anders, damit own-PID-Check nicht greift
    result = ns["_kill_stale_lockfile_owner"]("/tmp/foo", os.getpid() + 1)
    assert result is False
    assert killed == [], (
        "P134 Kern-Schutz: fremder Prozess (cwd-Check False) "
        "darf NICHT gekillt werden")


def test_t19_helper_kills_legit_simpleft8_instance(tmp_path):
    """T19: Helper killt eine echte SimpleFT8-Instanz (cwd-match + lebt)."""
    ns, killed = _prepare_helper_ns(tmp_path, str(os.getpid()))
    ns["_kill_stale_lockfile_owner"].__globals__["_pid_has_cwd_in_app_dir"] = (
        lambda pid, app_dir: True)
    result = ns["_kill_stale_lockfile_owner"]("/tmp/foo", os.getpid() + 1)
    assert result is True
    assert killed == [os.getpid()], (
        f"Legitime SimpleFT8-Instanz muss gekillt werden "
        f"(killed={killed})")


def test_t20_helper_doc_mentions_pid_reuse_risk():
    """T20: Doku erwaehnt PID-Reuse-Rest-Risiko (Final-R1 GELB)."""
    func = _find_func("_kill_stale_lockfile_owner")
    doc = ast.get_docstring(func) or ""
    assert "PID-Reuse" in doc or "Reuse" in doc, (
        "Final-R1 GELB-Auflage: PID-Reuse-Edge-Case soll dokumentiert sein")


# Modulebener Import os fuer T16-T19
import os  # noqa: E402
