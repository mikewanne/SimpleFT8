"""P133 + Hotfix (26.05.2026) — starter.command Bash-Vorschichten.

Mike-Spec nach P132: Defense-in-Depth in starter.command BEVOR Python
startet. Falls Python-Code mal versagt (Crash, Hänger), greift Bash
als 2. Sicherheits-Netz.

Hotfix 26.05. (Mike-Field-Bug „starter wird beendet, App startet nicht"):
Schicht 3 lsof-CWD-Sweep entfernt — sie killte fremde Python-Prozesse
(pytest, IDE-Tools) mit cwd im App-Dir und ueber die Eltern-Kette sogar
den Starter selbst (Exit 144). Selber Fehlerklassen-Bug wie pgrep vor
P132. lsof-Identifikation findet jetzt nur noch in Python statt
(acquire_single_instance_lock in main.py, nur PIDs aus Lockfile).

R1-Final-Catch (urspruenglich): Reihenfolge Lockfile vor osascript fuer
Race-Sicherheit bei parallelem Doppelklick.

ACs:
- AC1: Schicht 1 = Lockfile-PID-Check (R1-Race-Schutz)
- AC2: Schicht 2 = osascript Window-Title-Check
- AC3: Beide Schichten KILL automatisch (Mike-Spec, kein Dialog)
- AC4: PID-Recycling-Schutz in Schicht 1 (ps-Check)
- AC5: kill_with_grace Helper-Funktion (SIGTERM + sleep + SIGKILL)
- AC6: Lock-File-Cleanup nach Schicht 1
- AC7: bash -n Syntax-Check passing
- AC8: KEIN lsof-Sweep mehr (Hotfix-Regression-Schutz)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


STARTER_CMD = Path(__file__).parent.parent / "starter.command"


def test_t1_starter_exists():
    """T1: starter.command existiert und ist ausfuehrbar."""
    assert STARTER_CMD.exists()
    # Auf macOS: ausfuehrbares Bit muss gesetzt sein
    mode = STARTER_CMD.stat().st_mode
    assert mode & 0o100, "starter.command muss ausfuehrbar sein"


def test_t2_bash_syntax_valid():
    """T2: bash -n bestaetigt Syntax."""
    result = subprocess.run(
        ["bash", "-n", str(STARTER_CMD)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Syntax-Fehler: {result.stderr}"


def test_t3_kill_with_grace_helper_exists():
    """T3: kill_with_grace Helper-Funktion ist definiert."""
    src = STARTER_CMD.read_text()
    assert "kill_with_grace()" in src
    assert "kill -TERM" in src
    assert "kill -KILL" in src
    assert "sleep 1.5" in src


def test_t4_schicht_1_lockfile_first():
    """T4: SCHICHT 1 vor SCHICHT 2 (R1-Race-Schutz)."""
    src = STARTER_CMD.read_text()
    pos_schicht1 = src.find("SCHICHT 1: Lockfile-PID-Check")
    pos_schicht2 = src.find("SCHICHT 2: osascript Window-Title-Check")
    assert pos_schicht1 > 0, "SCHICHT 1 Lockfile-Check fehlt"
    assert pos_schicht2 > 0, "SCHICHT 2 osascript fehlt"
    assert pos_schicht1 < pos_schicht2


def test_t5_lockfile_check_auto_kill():
    """T5: Schicht 1 KILLT automatisch (Mike-Spec, kein Abort/Dialog)."""
    src = STARTER_CMD.read_text()
    # Finde den Lockfile-Block + verifiziere KILL statt EXIT
    schicht1_start = src.find("SCHICHT 1: Lockfile-PID-Check")
    schicht2_start = src.find("SCHICHT 2: osascript")
    schicht1_block = src[schicht1_start:schicht2_start]
    assert "kill_with_grace" in schicht1_block, (
        "Schicht 1 muss kill_with_grace rufen, nicht exit/abort")
    # KEIN exit oder Banner-Dialog
    assert "exit 1" not in schicht1_block
    assert "läuft bereits" not in schicht1_block


def test_t6_pid_recycling_protection():
    """T6: Schicht 1 hat PID-Recycling-Schutz via ps-Check."""
    src = STARTER_CMD.read_text()
    schicht1_start = src.find("SCHICHT 1: Lockfile-PID-Check")
    schicht2_start = src.find("SCHICHT 2: osascript")
    schicht1_block = src[schicht1_start:schicht2_start]
    assert "ps -p" in schicht1_block
    assert "Python|python|SimpleFT8" in schicht1_block or "grep -qE" in schicht1_block


def test_t7_no_lsof_sweep_anymore():
    """T7 (Hotfix-Regression-Schutz): KEIN lsof-Sweep mehr im Starter.

    lsof-CWD-Erkennung gehoert in Python (acquire_single_instance_lock),
    nicht in Bash — sonst killt sie fremde Python-Prozesse (pytest, IDE)
    mit cwd im App-Dir, inkl. Eltern-Kette zum Starter selbst.
    """
    src = STARTER_CMD.read_text()
    assert "lsof -c Python" not in src
    assert "SCHICHT 3" not in src
    assert "ZOMBIES=" not in src


def test_t8_no_dialog_anywhere():
    """T8: KEIN Dialog/Abbruch — Mike-Spec automatisch killen."""
    src = STARTER_CMD.read_text()
    # Alter Banner darf nicht mehr da sein
    assert "läuft bereits — KEIN zweiter Start" not in src
    # Alter display dialog Aufruf vor exit 1 auch weg
    # (Wir behalten den Exit-Code-Banner fuer App-Fehler — das ist OK)
    main_section = src[:src.find("./venv/bin/python3 main.py")]
    assert "display dialog" not in main_section, (
        "Schicht 1-3 darf keinen Dialog zeigen (Mike-Spec)")


def test_t9_lock_file_cleanup():
    """T9: Stale Lock-File wird nach Schicht-1-Kill geloescht."""
    src = STARTER_CMD.read_text()
    count = src.count('rm -f "$LOCK_FILE"')
    assert count >= 1, f"Lock-File-Cleanup fehlt (found {count}x)"


def test_t10_python_start_after_all_checks():
    """T10: ./venv/bin/python3 main.py kommt NACH beiden Schichten."""
    src = STARTER_CMD.read_text()
    pos_schicht2 = src.find("SCHICHT 2: osascript")
    pos_python = src.find("./venv/bin/python3 main.py")
    assert pos_schicht2 > 0
    assert pos_python > 0
    assert pos_python > pos_schicht2


def test_t11_doc_marker_p133():
    """T11: P133-Marker + R1-Race-Catch-Hinweis im Doku-Kommentar."""
    src = STARTER_CMD.read_text()
    assert "P133" in src
    assert "R1-Race-Catch" in src or "Race-sicher" in src
