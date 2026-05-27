#!/usr/bin/env python3
"""P145 (27.05.2026): Pattern-Check-Skript für mode-aware Symmetrie-Bugs.

R1-Empfehlung aus P141-Review (27.05.): statisches AST-Analyse-Skript
das mode-aware Symmetrie-Bugs (Pattern-Klasse P102/P114/P135/P141)
AUTOMATISCH findet bevor sie ins Feld kommen.

## Hintergrund

Die Bug-Klasse hat 4 dokumentierte Iterationen:
- P102: `_on_rx_mode_clicked` rief `_refresh_antenna_status_label()`
  nicht auf (nur `set_rx_mode` tat es) → Header-Suffix stale.
- P114: `_refresh_modeband_status_label` fehlte in beiden
  Mode/Band-Settern.
- P135: `update_decode_count` per-Slot statt akkumuliert.
- P141: `compute_local_conditions + update_local_conditions` fehlten
  im `_handle_diversity_operate`, nur in `_handle_normal_mode` → 1★
  statt 4★.

## Zwei Check-Arten

**Check 1: UI-Update-Symmetrie über `_rx_mode == "..."`-Branches.**
Vergleicht NUR UI-Update-Methoden (`update_*`, `_refresh_*`, `show_*`)
über if/elif/else-Branches innerhalb derselben Methode. R1-F1: ohne
diese Einschränkung wird die Whitelist zum Monster.

**Check 2: Mode-Handler-Methoden-Familien.**
Vergleicht hardcoded Familien parallelaufender Handler-Methoden
(`_handle_normal_mode` ⇄ `_handle_diversity_operate`). Wenn UI-Update-
Methode in einem Mitglied vorkommt, im anderen fehlt → Asymmetrie.

## Aufruf

```
./venv/bin/python3 scripts/check_mode_symmetry.py
./venv/bin/python3 scripts/check_mode_symmetry.py ui/mw_cycle.py
```

Exit-Code: 0 wenn keine Asymmetrien, 1 wenn welche gefunden.

## False-Positive-Whitelist

`WHITELIST_UI_METHODS` = Methoden die per Definition mode-spezifisch
sind (`update_diversity_counts`, `update_tx_peak` etc.).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Optional


# ────────────────────────────────────────────────────────────────────────
# Konfiguration
# ────────────────────────────────────────────────────────────────────────

# UI-Update-Methoden-Präfixe (R1-F1: Check 1 beschränken)
UI_UPDATE_PREFIXES = ("update_", "_refresh_", "show_")

# Mode-Handler-Familien (R1-F1: hardcoded mit Pflege-Doku)
# Pflege: bei neuem Empfangsmodus hier Familie ergänzen.
MODE_HANDLER_FAMILIES = {
    # P141-Fall: Normal vs Diversity-Operate sollen parallele UI-Updates
    # haben. DX-Tune ist absichtlich anders (DX-Mess-Phase mit Dialog).
    "cycle_handlers": ["_handle_normal_mode", "_handle_diversity_operate"],
}

# UI-Update-Methoden die per Definition mode-spezifisch sind (= legitim
# asymmetrisch, sollen NICHT als Bug gemeldet werden).
WHITELIST_UI_METHODS = {
    # Diversity-only (legitim)
    "update_diversity_counts",
    "update_diversity_ratio",
    "update_freq_histogram",
    "update_from_stations",  # _antenna_prefs.update_from_stations
                             # — nutzt Diversity-Stations für Karten-
                             # Render. Im Normal-Mode kein Diversity-
                             # Pattern → keine Antennen-Präferenzen.
    # DX-Tune-only
    "update_tx_peak",
    # Mode-aware-anders aber legitim
    "update_snr",  # In _handle_normal_mode = avg über alle Stationen.
                   # Im Diversity-Pfad wird update_snr per-Message in
                   # on_message_decoded gerufen (Z. 818, mode-agnostisch).
                   # Beide Anzeige-Semantiken bewusst.
}


# ────────────────────────────────────────────────────────────────────────
# Datenmodell
# ────────────────────────────────────────────────────────────────────────


class Issue:
    """Ein gefundener Symmetrie-Bug."""

    def __init__(self, path: str, line: int, check: str, description: str):
        self.path = path
        self.line = line
        self.check = check
        self.description = description

    def __str__(self):
        return f"{self.path}:{self.line} [{self.check}] {self.description}"

    def __repr__(self):
        return self.__str__()


# ────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen — AST
# ────────────────────────────────────────────────────────────────────────


def _extract_rx_mode_value(test_node: ast.expr) -> Optional[str]:
    """Extrahiert den Modus-String aus einem `_rx_mode == "X"`-Vergleich.

    Erkennt:
    - `self._rx_mode == "diversity"` → "diversity"
    - `self._rx_mode == "X" and other_condition` → "X"

    Returns None wenn nicht erkannt.
    """
    if isinstance(test_node, ast.Compare):
        if (
            isinstance(test_node.left, ast.Attribute)
            and test_node.left.attr == "_rx_mode"
            and len(test_node.comparators) == 1
            and isinstance(test_node.comparators[0], ast.Constant)
        ):
            return test_node.comparators[0].value
    elif isinstance(test_node, ast.BoolOp) and isinstance(test_node.op, ast.And):
        for value in test_node.values:
            result = _extract_rx_mode_value(value)
            if result:
                return result
    return None


def _collect_ui_update_calls(node: ast.AST) -> set[str]:
    """Sammelt alle UI-Update-Methoden-Namen (update_*, _refresh_*, show_*)
    aus dem Body eines Nodes — rekursiv via ast.walk.

    Whitelist-Methoden werden NICHT zurückgegeben.
    """
    calls: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            method_name = sub.func.attr
            if any(method_name.startswith(p) for p in UI_UPDATE_PREFIXES):
                if method_name not in WHITELIST_UI_METHODS:
                    calls.add(method_name)
    return calls


def _collect_branches(if_node: ast.If) -> list[tuple[Optional[str], ast.AST]]:
    """Sammelt alle Branches einer if/elif/else-Kaskade rekursiv (R1-F3).

    Beispiel:
        if mode == "X": A
        elif mode == "Y": B
        else: C
    → [("X", body), ("Y", body), (None, else_body)]
    """
    branches: list[tuple[Optional[str], ast.AST]] = []
    mode = _extract_rx_mode_value(if_node.test)
    branches.append((mode, if_node.body))
    if if_node.orelse:
        if len(if_node.orelse) == 1 and isinstance(if_node.orelse[0], ast.If):
            branches.extend(_collect_branches(if_node.orelse[0]))
        else:
            branches.append((None, if_node.orelse))
    return branches


# ────────────────────────────────────────────────────────────────────────
# Check 1: UI-Update-Symmetrie über _rx_mode-Branches
# ────────────────────────────────────────────────────────────────────────


def check_rx_mode_branches(tree: ast.AST, path: str) -> list[Issue]:
    """Findet `if self._rx_mode == "..."`-Kaskaden und vergleicht UI-
    Update-Aufrufe über Branches.

    Asymmetrie = UI-Update-Methode in einem Branch, nicht im anderen.
    """
    issues: list[Issue] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        first_mode = _extract_rx_mode_value(node.test)
        if first_mode is None:
            continue
        branches = _collect_branches(node)
        # Nur Kaskaden mit ≥ 2 erkannten Modes vergleichen
        recognized = [(m, b) for m, b in branches if m is not None]
        if len(recognized) < 2:
            continue
        # Sammle pro Branch die UI-Update-Calls
        per_branch: list[tuple[str, set[str]]] = []
        for mode, body in recognized:
            # body ist eine Liste — Wrap in Module für ast.walk
            calls: set[str] = set()
            for stmt in body:
                calls |= _collect_ui_update_calls(stmt)
            per_branch.append((mode, calls))
        # Vergleich: für jedes Methoden-Vorkommen prüfen ob in allen
        # Modes vorhanden
        all_calls = set()
        for _, calls in per_branch:
            all_calls |= calls
        for call in sorted(all_calls):
            missing_in = [m for m, calls in per_branch if call not in calls]
            if missing_in:
                present_in = [m for m, calls in per_branch if call in calls]
                issues.append(Issue(
                    path=path,
                    line=node.lineno,
                    check="rx_mode_branches",
                    description=(
                        f"UI-Update '{call}' fehlt in Branch(es) "
                        f"{missing_in} (vorhanden in {present_in})"
                    ),
                ))
    return issues


# ────────────────────────────────────────────────────────────────────────
# Check 2: Mode-Handler-Familien
# ────────────────────────────────────────────────────────────────────────


def check_mode_handler_families(
    tree: ast.AST, path: str
) -> list[Issue]:
    """Vergleicht UI-Update-Aufrufe in Mode-Handler-Methoden-Familien.

    R1-F2: Familien sind hardcoded (`MODE_HANDLER_FAMILIES`). Bei neuem
    Empfangsmodus hier ergänzen.
    """
    issues: list[Issue] = []
    # Sammle alle Methoden-Definitionen mit ihren UI-Update-Calls
    method_calls: dict[str, tuple[int, set[str]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            calls = _collect_ui_update_calls(node)
            method_calls[node.name] = (node.lineno, calls)
    # Pro Familie: vergleichen ob jede UI-Update-Methode in allen
    # Familien-Mitgliedern vorkommt
    for family_name, members in MODE_HANDLER_FAMILIES.items():
        # Nur Familien-Mitglieder die existieren
        present_members = [m for m in members if m in method_calls]
        if len(present_members) < 2:
            continue
        # Vereinigung aller Calls
        all_calls: set[str] = set()
        for m in present_members:
            all_calls |= method_calls[m][1]
        # Pro Call: in welchen Mitgliedern fehlt er?
        for call in sorted(all_calls):
            missing_in = [
                m for m in present_members
                if call not in method_calls[m][1]
            ]
            if missing_in:
                present_in = [
                    m for m in present_members
                    if call in method_calls[m][1]
                ]
                # Zeile vom 1. Mitglied das den Call hat
                line = method_calls[present_in[0]][0]
                issues.append(Issue(
                    path=path,
                    line=line,
                    check=f"handler_family[{family_name}]",
                    description=(
                        f"UI-Update '{call}' fehlt in {missing_in} "
                        f"(vorhanden in {present_in})"
                    ),
                ))
    return issues


# ────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────


def check_file(path: Path) -> list[Issue]:
    """Beide Checks auf eine Datei anwenden."""
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    return (
        check_rx_mode_branches(tree, str(path))
        + check_mode_handler_families(tree, str(path))
    )


def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    repo_root = Path(__file__).resolve().parent.parent
    targets_str = argv or ["ui/mw_cycle.py"]
    targets = [repo_root / t if not Path(t).is_absolute() else Path(t)
               for t in targets_str]

    all_issues: list[Issue] = []
    for path in targets:
        if not path.exists():
            print(f"WARN: {path} nicht gefunden", file=sys.stderr)
            continue
        all_issues.extend(check_file(path))

    if not all_issues:
        print("✓ Keine mode-aware Symmetrie-Asymmetrien gefunden.")
        return 0

    print(f"⚠ {len(all_issues)} potentielle Asymmetrien gefunden:\n")
    for issue in all_issues:
        print(f"  {issue}")
    print(
        "\n→ Wenn legitime Asymmetrie: in `WHITELIST_UI_METHODS` "
        "ergänzen oder Familie anpassen.\n"
        "→ Wenn Bug: fixen + Test ergänzen.\n"
        "→ Pattern-Klasse P102/P114/P135/P141.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
