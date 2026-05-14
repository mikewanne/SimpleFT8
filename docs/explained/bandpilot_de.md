# Bandpilot — Stunden-genaue RX-Modus-Empfehlung

> **v0.88, Mai 2026** — Konzept-Refactor. Statt globalem Mittelwert
> jetzt drei direkte Werte pro UTC-Stunde, ohne Aggregation.

## Was macht der Bandpilot?

Beim Bandwechsel prueft der Bandpilot fuer die **aktuelle UTC-Stunde**:
welcher RX-Modus hat in dieser Stunde historisch die meisten Stationen
pro 15-Sekunden-Slot geliefert?

Drei Modi stehen zur Wahl:

- **Normal** — eine Antenne (ANT1)
- **Diversity Standard** — zwei Antennen, die mit den meisten Stationen gewinnt
- **Diversity DX** — zwei Antennen, die mit den schwaecheren DX-Signalen gewinnt

Anders als in v0.87 wird **nicht aggregiert** — die drei Werte werden
direkt verglichen. Begruendung: Diversity Standard und Diversity DX
sind unterschiedliche Grundgesamtheiten (verschiedene
Antennen-Pattern, verschiedene Win-Rate-Logik) — Mittelwerte
zusammenzufuehren erzeugt Bias.

> **Hinweis v0.97.17 (P46, Mai 2026):** Bandpilot kann Normal sowohl
> als aktuellen Modus haben als auch als Empfehlung vorschlagen. In
> v0.95.20–v0.97.16 (P35-Bug-E) war Normal aus dem Pilot-Pool
> ausgeschlossen — Mike's spaetere Vision „ganz oder gar nicht" hat
> diese Einschraenkung zurueckgenommen. Bei Single-Antenna-Setups
> (keine Diversity-Daten) liefert der Recommender weiterhin keine
> Empfehlung (Schwelle nicht erfuellt).

## Datenbasis

Stunden-Markdown-Dateien in `statistics/<Modus>/<Band>/FT8/`. Jede
Datei = eine UTC-Stunde, jede Zeile = ein 15s-Slot mit Anzahl
dekodierter Stationen.

Schwellen pro Stunde + Modus (alle drei muessen erfuellen):

- **mindestens 3 Messtage** in dieser Stunde
- **mindestens 20 Slots** in dieser Stunde

Wenn ein Modus darunter liegt: stille Empfehlung, kein Wechsel,
Statusbar-Hinweis 5 Sekunden ("Bandpilot: nicht genug Daten fuer
40m um 03 UTC").

## Settings — drei Verhaltensmodi

Im Settings-Dialog Tab "FT8 & Diversity":

| Wert | Verhalten |
|---|---|
| **Aus** | Bandpilot reagiert nicht. |
| **Auto (bester Wert)** | Bei Bandwechsel: 3-Sekunden-Toast mittig auf dem Bildschirm zeigt alle drei Werte. App wechselt automatisch zum Top-1 — wenn aktueller Modus innerhalb 5%-Toleranz von Top-1 liegt, kein Wechsel (Pingpong-Schutz). |
| **Manuell (Dialog)** | Bei Bandwechsel: Dialog erscheint **nur** wenn Top-1 != aktueller Modus. Drei Buttons (Top-1 in gruen), User klickt — oder Abbruch. |

## Toleranz-Regel

Auto-Modus wechselt nur wenn der aktuelle Modus **spuerbar schlechter**
als Top-1 ist. Konkret:

```
Toleranz = max(5% von Top-1_Mean, 1 Station/Slot)

if aktueller_Mean >= Top-1_Mean - Toleranz:
    kein Wechsel (Pingpong-Schutz greift)
else:
    Wechsel zu Top-1 (mit Toast)
```

Beispiel 13 UTC auf 40m:

| Modus | Mean |
|---|---:|
| Diversity DX (Top-1) | 50.4 |
| Diversity Standard | 48.0 |
| Normal (aktuell) | 35.0 |

Toleranz = max(2.5, 1) = 2.5. Aktueller Mean (35.0) ist 15.4 unter
Top-1 → spuerbar schlechter → Wechsel zu DX.

Anderes Beispiel:

| Modus | Mean |
|---|---:|
| Diversity DX (Top-1) | 50.4 |
| Diversity Standard (aktuell) | 49.0 |
| Normal | 35.0 |

Toleranz = 2.5. Aktueller Mean (49.0) ist 1.4 unter Top-1 → kein
Wechsel (man bleibt bei Standard).

## TX-Schutz

Wenn beim Bandwechsel gerade ein TX laeuft:

1. Toast erscheint sofort mit Empfehlung
2. Statusbar 5s: "Bandpilot wechselt zu Diversity DX nach TX-Ende"
3. Sobald `tx_finished`-Signal kommt: Modus-Wechsel + kurzer
   Bestaetigungs-Toast 1.5s "Bandpilot: Modus angewendet"

So wird kein QSO mitten im Senden unterbrochen.

## Markdown-Empfehlungs-Datei

Beim App-Start (und beim `scripts/generate_plots.py`-Lauf) wird
`auswertung/Bandpilot-<band>-FT8.md` regeneriert — eine 24-Zeilen-
Tabelle (UTC 00..23) mit allen drei Werten pro Stunde plus Top-1.

So kann man auf einen Blick sehen, wo welcher Modus optimal ist —
auch ohne die App zu wechseln.

## Was es **nicht** macht

- Empfiehlt **kein** anderes Band (kein "wechsle auf 20m, da ist
  mehr los"-Feature). Bandpilot reagiert nur nachdem du das Band
  gewaehlt hast.
- Reagiert **nicht** auf Stundenwechsel waehrend du auf einem Band
  bleibst. Trigger ist immer ein Bandwechsel.
- Hat **keine** Zeit-Hysterese ("nicht zweimal hintereinander
  wechseln") — wird in einer spaeteren Version ergaenzt falls noetig.

## Migration v0.87 → v0.88

Bestehende Settings werden beim ersten App-Start automatisch
migriert:

| Alt | Neu |
|---|---|
| `bandpilot_enabled = false` | `bandpilot_mode = "off"` |
| `bandpilot_enabled = true` | `bandpilot_mode = "auto"` |
| `bandpilot_diversity_pref = ...` | verworfen |

Der alte Cache `~/.simpleft8/bandpilot_summary.json` wird
geloescht. Neuer Cache: `~/.simpleft8/bandpilot_hourly.json`.

## Beispiel-Auswertung

Aus `auswertung/Bandpilot-40m-FT8.md` (Auszug):

```
| UTC | Normal | Div Standard | Div DX | Top-1 |
|---:|---:|---:|---:|:---|
| 13 | 5·45.2 | 4·38.0 | 5·52.7 | Diversity DX |
| 14 | 5·48.1 | 5·40.5 | 5·55.2 | Diversity DX |
| ...
```

Pro Zelle: `<Tage>·<Mean>`. Bei zu wenig Daten in einem Modus:
`—` (Em-Dash) oder Top-1-Spalte zeigt `_zu wenig Daten_`.
