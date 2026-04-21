# Auswertungs-Script — Hinweise

## generate_plots.py

**Aufruf:**
```bash
./venv/bin/python3 scripts/generate_plots.py
```

**Output:** `auswertung/stationen_<band>_<proto>.png` und `auswertung/diversity_<band>_<proto>.png`

### Was das Script macht

Liest alle Zeilen aus `statistics/<Modus>/<Band>/<Protokoll>/YYYY-MM-DD_HH.md`
und berechnet pro Stunde: Mittelwert, Min, Max der Stationen-Anzahl.

### Warum kein ## Zusammenfassung Block in den .md-Dateien?

Bei Moduswechsel innerhalb einer Stunde (z.B. von Diversity_Dx → Normal → Diversity_Dx)
werden die internen Zähler in station_stats.py resettet, aber die Datei läuft weiter.
Ergebnis: Der Summary-Block zählt nur die Zyklen der **letzten** Schreib-Session,
nicht die gesamte Stunde. Falsche Zusammenfassungen können nicht korrigiert werden.

**Lösung:** Keine Zusammenfassungen schreiben. Das Script rechnet alles selbst
aus den Rohdaten (Zeile für Zeile, alle Einträge). Das ist immer korrekt.

### Diagramme

| Datei | Inhalt |
|-------|--------|
| `stationen_<band>_<proto>.png` | Zeitverlauf: Ø Stationen/15s-Zyklus (alle Modi, Min–Max-Band) |
| `diversity_<band>_<proto>.png` | ANT2-Wins + Rescue-Events pro Stunde (nur Diversity_Dx) |

Rescue-Event: ANT1 ≤ -24 dB (unter FT8-Decodierschwelle), ANT2 > -24 dB
→ Diese Station wäre mit ANT1 allein verloren gegangen.
