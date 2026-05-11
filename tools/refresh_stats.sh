#!/bin/bash
# SimpleFT8 — Statistik komplett aktualisieren in einem Aufruf.
#
# Aufruf aus dem Repo-Root oder ueberall:
#   tools/refresh_stats.sh
#
# Macht:
#   1. scripts/generate_plots.py   -> Diagramme + PDFs DE/EN
#   2. tools/slot_lueckenliste.py  -> auswertung/Slot-Lueckenliste.md

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/venv/bin/python3"

echo "=== Diagramme + PDFs ==="
"$PY" "$ROOT/scripts/generate_plots.py" | tail -3

echo
echo "=== Slot-Lueckenliste ==="
"$PY" "$ROOT/tools/slot_lueckenliste.py"
