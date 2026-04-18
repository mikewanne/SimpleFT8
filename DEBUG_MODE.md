# SimpleFT8 Debug-Konsole

## Aktivierung

**Methode 1:** `Ctrl+D` (Toggle)
**Methode 2:** Einstellungen → "Debug-Konsole anzeigen"

Die Einstellung wird gespeichert und beim naechsten Start wiederhergestellt.

## Funktionen

| Button | Funktion |
|--------|----------|
| **Filter** | Live-Filterung der Ausgabe (grep-artig, case-insensitive) |
| **Copy** | Gesamten sichtbaren Text in die Zwischenablage kopieren |
| **Clear** | Konsole leeren (alle Zeilen loeschen) |

## Filter-Beispiele

| Eingabe | Zeigt |
|---------|-------|
| `diversity` | Nur Diversity-bezogene Meldungen |
| `cq-freq` | CQ-Frequenz Berechnungen |
| `omni` | OMNI-TX Status und Entscheidungen |
| `err` | Fehlermeldungen |
| `stats` | Statistik-Logger Meldungen |
| `qso` | QSO State Machine Uebergaenge |

## Typische Ausgaben

```
[Diversity] 34 St. | A1>A2: 26 | A2>A1: 8 (24%) | Nur A1: 4 | Nur A2: 2
[CQ-Freq] Median=650Hz | Luecke=500-800Hz (300Hz breit) | TX=650Hz | 3 Luecken
[CQ-Freq] Kollision! 650Hz belegt (4 Stationen) → wechsle auf 825Hz
[OMNI-TX] TX auf Even (B1 [0/4] TX)
[OMNI-TX] RX-Slot → skip CQ (B1 [2/4] RX)
[Stats] Schreibfehler: Permission denied
```

## Technische Details

- **Schrift:** Menlo 11pt
- **Max Zeilen:** 500 (aeltere werden automatisch entfernt)
- **Umleitung:** stdout + stderr werden ins Widget umgeleitet UND auf die Original-Konsole
- **Performance:** Minimaler Overhead — Text wird nur angefuegt wenn sichtbar
