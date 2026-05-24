#!/usr/bin/env bash
# Band-Aktivitäts-Übersicht (P117, v0.98.02) — Mike's Quick-Reference vor Park-Trip.
#
# Generiert auswertung/bandaktivitaet.png (DE) + auswertung/en/band_activity.png (EN)
# aus den aktuellen Stats-Daten. Liniendiagramm: alle Bänder × 24 UTC-Stunden.
#
# Standalone — kein App-Eingriff. n8n-tauglich (analog Solar-Telegram-Trigger).

set -e
cd "$(dirname "$0")"
./venv/bin/python3 scripts/band_activity_summary.py
