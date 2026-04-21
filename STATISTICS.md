# SimpleFT8 Stations-Statistik

## Uebersicht

SimpleFT8 loggt pro FT8/FT4-Zyklus die Anzahl empfangener Stationen, Durchschnitts-SNR und Band. Die Daten werden als Markdown-Dateien gespeichert und koennen fuer Langzeitanalysen genutzt werden.

## Verzeichnisstruktur

```
SimpleFT8/statistics/
├── Normal/
│   ├── 20m/
│   │   └── FT8/
│   │       ├── 2026-04-18_08.md
│   │       └── 2026-04-18_09.md
│   └── 40m/
│       └── FT8/
├── Diversity_Normal/
│   └── 20m/
│       └── FT8/
└── Diversity_Dx/
    └── 20m/
        └── FT4/
```

## Datei-Format

Jede Stunde erhaelt eine eigene .md Datei:

```markdown
# Statistik 2026-04-18 08:00-08:59 UTC | FT8 | 20m | Normal

| Zeit | Stationen | Ø SNR |
|------|-----------|-------|
| 08:00:15 | 12 | -8 |
| 08:00:30 | 15 | -6 |

## Zusammenfassung
- Zyklen: 240
- Ø Stationen/Zyklus: 13.2
- Max: 28 | Min: 3
```

Im Diversity-Modus wird eine zusaetzliche Spalte "Ant2 Wins" angezeigt:

```markdown
| Zeit | Stationen | Ø SNR | Ant2 Wins |
|------|-----------|-------|-----------|
| 08:00:15 | 34 | -8 | 8 |
```

## Modi

| Modus | Beschreibung | Wann geloggt |
|-------|-------------|-------------|
| Normal | Einzelantenne, Standard-Empfang | Immer (wenn aktiviert) |
| Diversity_Normal | Zwei Antennen, Stationsanzahl-Scoring | Nur in Betriebsphase |
| Diversity_Dx | Zwei Antennen, Schwachsignal-Scoring | Nur in Betriebsphase |

## Auto-Pause bei Tuning

Statistiken werden automatisch pausiert wenn:
- DX Gain-Messung aktiv ist
- Diversity-Einmessung laeuft
- Diversity in der Messphase ist (nicht Betrieb)

Grund: Tuning verfaelscht die Empfangsdaten.

## Ant2 Superiority (nur Diversity)

Pro Zyklus wird gezaehlt wie oft Antenne 2 einen strikt besseren SNR hat als Antenne 1. Dies quantifiziert den Diversity-Gewinn gegenueber Einzelantenne.

- `A2>1`: Ant2 besser (wird gezaehlt)
- `A1>2`: Ant1 besser (wird nicht gezaehlt)
- Gleicher SNR: wird nicht gezaehlt

## Ausschlusskriterien (Exclusion Criteria)

Statistiken werden automatisch pausiert bei:

| Zustand | Grund | Dauer |
|---------|-------|-------|
| **Radio-Suche** | Hardware nicht verbunden | Bis Verbindung steht |
| **Gain-Messung** | DX-Tuning / Antennen-Kalibrierung | Waehrend Messung + 60s |
| **Diversity-Einmessung** | Antennen-Vergleich laeuft | Waehrend Messphase + 60s |
| **Bandwechsel** | Neue Frequenz, Accumulator leer | 60s Settling |
| **Moduswechsel** | Normal ↔ Diversity | 60s Settling |
| **App-Start** | Erste Zyklen unzuverlaessig | 60s Settling |

Die 60s Settling-Phase (Warmup) gilt fuer ALLE Modi gleichermassen — faire Vergleichsbasis zwischen Normal und Diversity.

## Aktivierung

Einstellungen → "Statistik-Erfassung aktivieren"

Nur FT8 und FT4. FT2 wird nicht unterstuetzt.
