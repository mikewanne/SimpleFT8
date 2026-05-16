# OMNI-CQ — Automatischer Paritäts-Wechsel

## Kurz gesagt

OMNI-CQ ruft in **einer** Slot-Paritaet (Even oder Odd), wechselt nach
einer modus-abhaengigen Zahl von Sendeversuchen automatisch in die
andere Paritaet. Ueber laengere Zeit erreichst du beide Hoerergruppen
statt nur einer — ohne die Slot-Sendezeit zu veraendern.

## Das Problem

Jeder FT8-Operator hoert immer nur den entgegengesetzten Slot. Wer auf
Even sendet, hoert nur Odd — und umgekehrt. Mit normalem CQ erreichst
du pro Zyklus **50%** der aktiven Stationen. Die andere Haelfte hoert
dich nie.

## Wie es funktioniert

OMNI-CQ ist ein **Single-Slot-CQ** in einer Paritaet, mit
automatischem Wechsel der Paritaet nach einer festen Zahl von
Sendeversuchen pro Modus:

| Modus | Sendeversuche pro Paritaet | Dauer (Wallclock) |
|-------|----------------------------|-------------------|
| FT8 | 10 | ~5 Minuten |
| FT4 | 20 | ~5 Minuten |
| FT2 | 40 | ~5 Minuten |

Ein Down-Counter zaehlt von der Maximalzahl runter. Bei 0:
**automatischer Paritaets-Wechsel** + Counter wird auf den
Modus-Wert zurueckgesetzt. Der Counter ist in der TX-Zeile sichtbar
als `↻N`-Suffix.

```
04:30:00 [E] → Sende CQ DA1MHH JO31 ↻10
04:30:30 [E] → Sende CQ DA1MHH JO31 ↻9
...
04:35:00 [E] → Sende CQ DA1MHH JO31 ↻1
04:35:30 [O] → Sende CQ DA1MHH JO31 ↻10   ← Paritaets-Wechsel
```

## Sendeanteil

OMNI-CQ veraendert die Sendezeit pro Slot **nicht**. Es ist Single-
Slot-CQ — also gleicher Sendeanteil wie normales CQ in der jeweiligen
Paritaet. Der Unterschied: die Paritaet wechselt automatisch nach
~5 Min.

## Realistischer Gewinn

Ueber laengere Zeit (1+ Stunde):

- **Belegte Baender:** ~15-25% mehr CQ-Antworten als statisches Single-
  Slot-CQ — du erreichst beide Hoerergruppen.
- **Leere Baender:** Geringer Effekt — wer dich nicht hoert, hoert dich
  auch nicht in der anderen Paritaet.

## QSO-Verhalten

Wenn eine Station antwortet:

1. OMNI pausiert, normaler QSO-Ablauf (State-Machine uebernimmt)
2. Nach QSO-Ende: OMNI resumed in der **gleichen** Paritaet
3. Counter wird auf TARGET zurueckgesetzt (positive Verstaerkung:
   „guter Slot — weiter so")

## Antennen-Mess (Diversity)

Wenn waehrend OMNI eine Diversity-Antennen-Mess startet:

1. OMNI pausiert (kein TX waehrend Mess)
2. Mess laeuft (~90 s)
3. Nach Mess: OMNI resumed, Counter zurueck auf TARGET

## Wechsel-Trigger ausserhalb Counter

- **Bandwechsel:** OMNI stoppt (User entscheidet manuell beim neuen Band)
- **Modus-Wechsel:** OMNI stoppt (Counter waere andere Groesse)

## Diversity-only

OMNI-CQ funktioniert nur im **Diversity-Modus**. Im Normal-Modus ist
der Toggle-Button ausgeblendet.

## Aktivierung

Seit v0.97.30 (P55) ist OMNI-CQ ein **regulaeres, sichtbares Feature**
im Diversity-Modus. Der Button **OMNI CQ** erscheint fest neben dem
CQ-Button, sobald Diversity aktiv ist — kein Klick auf die Versionsnummer
mehr noetig.

- **OMNI CQ-Button**: dunkelrot (inaktiv), gruen (aktiv)
- **Statusbar**: zeigt `Ω CQ=N (E)` oder `Ω CQ=N (O)` mit aktuellem
  Counter und Paritaet

*Historie:* Bis v0.97.29 war OMNI-CQ als Easter Egg versteckt und wurde
durch Klick auf die Versionsnummer aktiviert. In P55 wurde die Easter-
Egg-Logik komplett entfernt — siehe HISTORY-Eintrag v0.97.30.

## QSO-Panel-Anzeige

Bei aktivem OMNI:
- Even-Slots in **leicht dunklerem Orange** (#E09600)
- Odd-Slots in **normalem Orange** (#FFAA00)
- Bei Paritaets-Wechsel: **Leerzeile** zwischen den Bloecken
- Counter-Suffix `↻N` an jeder TX-Zeile

So siehst du auf einen Blick wie weit der aktuelle Paritaets-Block ist
und wann die naechste Phase beginnt.

## Fuer Beobachter im Wasserfall

Eine Frequenz, eine Station, ueblicher CQ-Rhythmus mit gelegentlichem
Paritaets-Wechsel — sieht aus wie ein Operator der zwischen Even- und
Odd-Phase wechselt. Technisch komplett regelkonform: eine TX-Frequenz,
normale Sendezeit pro Slot.

## Historie

Frueheres Konzept (v0.78–v0.96.0) war ein 5-Slot-Pattern mit zwei
konsekutiven TX-Slots pro Block. Wurde mit **P7.OMNI-SIMPLIFY**
(v0.96.4) durch das aktuelle Single-Slot-Pattern ersetzt. Grund:
TX-TX-konsekutiv in 15-s-Slots fuehrte zu Encoder-Races und
Diversity-Konflikten. Aktuelle Loesung ist KISS — eine Paritaet,
ein Wechsel-Counter, Diversity bleibt unangetastet.
