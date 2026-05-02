# Bandpilot

> ⚠️ **Im Feldtest** (v0.87, 01.05.2026) — Algorithmus
> implementiert + getestet (28 Unit-Tests gruen), Live-Validierung
> ueber laengere Funkzeit ausstehend.

## Was macht der Bandpilot?

Der Bandpilot waehlt bei einem Bandwechsel automatisch den
Empfangsmodus, der auf diesem Band in der Vergangenheit die meisten
Stationen pro 15-Sekunden-Slot geliefert hat.

Drei Modi stehen zur Wahl:

- **Normal** — eine Antenne (ANT1)
- **Diversity Standard** — zwei Antennen, die mit mehr Stationen gewinnt
- **Diversity DX** — zwei Antennen, die mit den schwaecheren DX-Signalen
  gewinnt

## Datenbasis

Der Bandpilot stuetzt sich auf die Stunden-Markdown-Dateien in
`statistics/<Modus>/<Band>/FT8/`. Jede Datei = eine UTC-Stunde, jede
Zeile = ein 15s-Slot mit der Anzahl dekodierter Stationen.

Mindestbedingung pro Modus: **2 Messtage und 50 Slots**. Darunter gibt
der Bandpilot keine Empfehlung — der manuell gesetzte Modus bleibt.

## Vergleich (Kandidat A)

`Normal` wird gegen den Mittelwert von Diversity_Normal und Diversity_DX
verglichen:

```
diversity_aggregate = (Diversity_Normal_Mean + Diversity_DX_Mean) / 2
```

Wenn `Normal_Mean >= diversity_aggregate` → **Normal**.
Sonst → **Diversity** mit dem gewaehlten Praeferenz-Modus.

## Diversity-Praeferenz

Wenn Diversity gewinnt, entscheidet die Praeferenz-Einstellung welcher
konkrete Modus aktiviert wird:

- **Auto** (Standard) — der Diversity-Modus mit dem hoeheren
  Pooled-Mean wird gewaehlt
- **Standard** — immer Diversity_Normal (mehr Stationen total)
- **DX** — immer Diversity_DX (mehr schwache DX-Signale)

## Manueller Override

Wenn du nach einer Bandpilot-Empfehlung manuell auf einen anderen Modus
schaltest (Klick auf "NORMAL" oder "DIVERSITY"), wird das fuer dieses
Band gemerkt. Der naechste Bandwechsel **zu** diesem Band wird den
Override respektieren — der Bandpilot greift erst beim uebernaechsten
Bandwechsel wieder.

Beispiel:

1. Wechsel auf 40m → Bandpilot empfiehlt Diversity Standard, App wechselt.
2. Du klickst manuell auf "Normal" → Override fuer 40m gesetzt.
3. Wechsel auf 20m → Bandpilot wirkt fuer 20m normal.
4. Wechsel zurueck auf 40m → Bandpilot **wechselt nicht** (Override),
   loescht das Flag.
5. Wechsel auf 20m und wieder zurueck auf 40m → Bandpilot wirkt wieder.

## Cache

Die Aggregation der Stats-Dateien wird pro Band 24 Stunden lang
gecached (`~/.simpleft8/bandpilot_summary.json`). Naechster Aufruf nach
24h re-aggregiert automatisch.

## Voraussetzungen

- Statistik-Erfassung muss aktiv sein (Settings → "Statistik-Erfassung
  aktivieren").
- Mindestens 2 Tage Messzeit pro Modus auf dem Band.
- Aktuell nur FT8 (FT4/FT2 werden vom Stats-Logger uebersprungen).

## Was zeigt die Statusbar?

Wenn der Bandpilot wechselt, erscheint unten kurz:

```
Bandpilot: Diversity Standard fuer 40m
```

(3 Sekunden, dann Standard-Statusbar zurueck.)
