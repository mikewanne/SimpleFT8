"""P145 (27.05.2026) — Pattern-Check-Skript für mode-aware Symmetrie.

R1-Empfehlung aus P141-Review: statisches AST-Analyse-Tool das die Bug-
Klasse P102/P114/P135/P141 (mode-aware Symmetrie-Bugs) automatisch findet.

Tests:
- T1: Skript läuft ohne Exception auf der Real-Codebase
- T2: Real-Codebase aktuell 0 Asymmetrien (alle bekannten Bugs gefixt)
- T3: Skript findet künstliche Asymmetrie in if/elif/else
- T4: Skript findet künstliche Asymmetrie in Mode-Handler-Familien (P141-Fall)
- T5: Whitelist-Methoden werden NICHT als Asymmetrie gemeldet
- T6: Geschachtelte elif/else-Kaskaden werden korrekt aufgelöst (R1-F3)
- T7: Exit-Code-Verhalten (0 bei OK, 1 bei Asymmetrie)
- T8: Skript-Ausgabe enthält Pattern-Klasse-Hinweis
"""

from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_mode_symmetry.py"


# ---------------------------------------------------------------------------
# T1-T2: Real-Codebase
# ---------------------------------------------------------------------------


def test_t1_script_runs_on_real_codebase():
    """T1: Skript läuft ohne Crash auf ui/mw_cycle.py."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "ui/mw_cycle.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    # Wir prüfen nur dass kein Python-Crash (Returncode 0 oder 1, NICHT > 1)
    assert result.returncode in (0, 1), (
        f"Skript crashed: stderr={result.stderr}")


def test_t2_real_codebase_no_asymmetries():
    """T2: Aktuell sollten 0 echte Asymmetrien gefunden werden.

    Wenn dieser Test fehlschlägt → entweder neuer Bug oder
    Whitelist-Erweiterung nötig (siehe check_mode_symmetry.py).
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"P145: Asymmetrien gefunden — entweder Bug fixen oder "
        f"Whitelist erweitern.\n\n{result.stdout}\n{result.stderr}")
    assert "Keine mode-aware Symmetrie-Asymmetrien" in result.stdout


# ---------------------------------------------------------------------------
# T3-T4: Synthetische Asymmetrien (Skript-Logik verifizieren)
# ---------------------------------------------------------------------------


def _make_tempfile(tmp_path: Path, src: str) -> Path:
    """Schreibt Quelltext in eine Temp-Datei für AST-Test."""
    f = tmp_path / "fake_module.py"
    f.write_text(textwrap.dedent(src))
    return f


def test_t3_finds_branch_asymmetry(tmp_path: Path):
    """T3: Skript findet `update_X` in einem _rx_mode-Branch aber nicht
    im anderen → ASYMMETRIE."""
    src = """
        class X:
            def _on_cycle(self):
                if self._rx_mode == "diversity":
                    self.control_panel.update_decode_count(5)
                    self.control_panel.update_some_other_widget(1)
                elif self._rx_mode == "normal":
                    self.control_panel.update_decode_count(5)
                    # update_some_other_widget FEHLT — Asymmetrie!
    """
    f = _make_tempfile(tmp_path, src)
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    issues = mod.check_file(f)
    # Mindestens eine Asymmetrie auf update_some_other_widget
    descs = " ".join(str(i) for i in issues)
    assert "update_some_other_widget" in descs, (
        f"Asymmetrie nicht erkannt. Issues: {issues}")


def test_t4_finds_handler_family_asymmetry(tmp_path: Path):
    """T4: Skript findet update_X in `_handle_diversity_operate` aber
    nicht in `_handle_normal_mode` → Familien-Asymmetrie (P141-Fall)."""
    src = """
        class X:
            def _handle_diversity_operate(self, messages, ant):
                self.control_panel.update_decode_count(5)
                self.control_panel.update_local_conditions(1, 2, 3)

            def _handle_normal_mode(self, messages):
                self.control_panel.update_decode_count(5)
                # update_local_conditions FEHLT — genau P141-Fall!
    """
    f = _make_tempfile(tmp_path, src)
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    issues = mod.check_file(f)
    descs = " ".join(str(i) for i in issues)
    assert "update_local_conditions" in descs, (
        f"P141-Asymmetrie nicht erkannt. Issues: {issues}")
    assert "handler_family" in descs, (
        f"Check-Tag handler_family fehlt. Issues: {issues}")


def test_t5_whitelist_blocks_diversity_only(tmp_path: Path):
    """T5: update_diversity_counts (auf Whitelist) wird NICHT als
    Asymmetrie gemeldet."""
    src = """
        class X:
            def _handle_diversity_operate(self, messages, ant):
                self.control_panel.update_decode_count(5)
                self.control_panel.update_diversity_counts(1, 2)

            def _handle_normal_mode(self, messages):
                self.control_panel.update_decode_count(5)
                # update_diversity_counts FEHLT — aber legitim (Whitelist)
    """
    f = _make_tempfile(tmp_path, src)
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    issues = mod.check_file(f)
    descs = " ".join(str(i) for i in issues)
    assert "update_diversity_counts" not in descs, (
        f"Whitelist-Methode falsch gemeldet. Issues: {issues}")


# ---------------------------------------------------------------------------
# T6: Geschachtelte elif/else (R1-F3)
# ---------------------------------------------------------------------------


def test_t6_nested_elif_chain_resolved(tmp_path: Path):
    """T6 (R1-F3): if/elif/elif/else mit 3 Modes wird komplett gewalked."""
    src = """
        class X:
            def _on_cycle(self):
                if self._rx_mode == "diversity":
                    self.control_panel.update_A(1)
                    self.control_panel.update_B(2)
                elif self._rx_mode == "normal":
                    self.control_panel.update_A(1)
                    self.control_panel.update_B(2)
                elif self._rx_mode == "dx_tuning":
                    self.control_panel.update_A(1)
                    # update_B FEHLT in dx_tuning — Asymmetrie!
    """
    f = _make_tempfile(tmp_path, src)
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    issues = mod.check_file(f)
    descs = " ".join(str(i) for i in issues)
    assert "update_B" in descs, (
        f"3-Wege-Kaskade nicht aufgelöst. Issues: {issues}")
    assert "dx_tuning" in descs, (
        f"3. Branch-Name fehlt im Issue. Issues: {issues}")


# ---------------------------------------------------------------------------
# T7-T8: Exit-Code + Output-Format
# ---------------------------------------------------------------------------


def test_t7_exit_code_zero_on_clean_codebase():
    """T7a: Aktuelle saubere Codebase → Exit-Code 0."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_t7b_exit_code_one_on_asymmetry(tmp_path: Path):
    """T7b: Datei mit Asymmetrie → Exit-Code 1."""
    src = """
        class X:
            def _on_cycle(self):
                if self._rx_mode == "diversity":
                    self.control_panel.update_only_in_diversity(1)
                elif self._rx_mode == "normal":
                    pass
    """
    f = _make_tempfile(tmp_path, src)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(f)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "update_only_in_diversity" in result.stdout


def test_t8_output_mentions_pattern_class():
    """T8: Bei Asymmetrie-Fund Hinweis auf Pattern-Klasse P102/P114/
    P135/P141 ausgeben — Mike-Doku-Anker."""
    src_path = SCRIPT.read_text()
    assert "P102" in src_path
    assert "P141" in src_path
    assert "Pattern-Klasse" in src_path or "Pattern-Familie" in src_path


# ---------------------------------------------------------------------------
# T9: Modul-Imports + API-Stabilität (Bonus, R1-F6)
# ---------------------------------------------------------------------------


def test_t9_module_has_check_file_api():
    """T9: Modul exportiert `check_file()` für Pytest-Integration."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert hasattr(mod, "check_file"), (
        "Modul muss check_file(path) exportieren für Test-Integration.")
    assert hasattr(mod, "main"), (
        "Modul muss main() exportieren für CLI-Aufruf.")


def test_t9b_handler_families_defined():
    """T9b: MODE_HANDLER_FAMILIES enthält den P141-Fall."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_mod", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    families = mod.MODE_HANDLER_FAMILIES
    assert "cycle_handlers" in families
    members = families["cycle_handlers"]
    assert "_handle_normal_mode" in members, (
        "P141-Fall: _handle_normal_mode muss in Familie sein.")
    assert "_handle_diversity_operate" in members, (
        "P141-Fall: _handle_diversity_operate muss in Familie sein.")
